import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .actions import Action, ActionL, ActionM


class ActionRunner:
    """Base class to assemble common STSP configuration and run an action.

    Subclasses provide the action-specific section via `assemble_action()` and
    can override `input_basename()` to control input/output file roots.
    """

    def __init__(self, config: Action):
        self.config = config

    # ----- Assembly helpers (no side effects) -----
    def assemble_common(self) -> str:
        return self.config.serialize_common()

    def assemble_action(self) -> str:
        """Override in subclass to provide action-specific lines including #ACTION."""
        raise NotImplementedError

    def input_basename(self) -> str:
        """Override to control the input filename base (without extension)."""
        return "pyact"

    # ----- Top-level run (side effects) -----
    def _prepare_and_run(self, workdir: Optional[Path]) -> Tuple[Path, str]:
        """Prepare workdir, ensure inputs, write .in, and invoke stsp.

        Returns (workdir_path, rootname_str) where rootname is the input path without .in.
        """
        # Prepare working directory
        made_temp = False
        if workdir is None:
            tdir = tempfile.TemporaryDirectory()
            made_temp = True
            work = Path(tdir.name)
        else:
            work = Path(workdir)
            work.mkdir(parents=True, exist_ok=True)

        # Validate the light curve file exists at the configured path.
        # If absolute, require it exist. If relative, require it exist under the workdir (stsp runs with cwd=work).
        fit = self.config.fitting_properties
        lc_path = Path(fit.data_filename)
        repo_root = Path(__file__).resolve().parents[1]

        def _ensure_link(src: Path, dst: Path) -> None:
            if dst.exists():
                return
            try:
                dst.symlink_to(src)
            except Exception:
                # Fallback to copy if symlink fails
                dst.write_bytes(src.read_bytes())

        if lc_path.is_absolute():
            if not lc_path.exists():
                raise FileNotFoundError(f"Light curve file not found: {lc_path}")
            # Create a short-name link in workdir and rewrite filename in .in to basename
            local_name = lc_path.name
            _ensure_link(lc_path, work / local_name)
            orig = fit.data_filename
            fit.data_filename = local_name
        else:
            candidate = work / lc_path
            if not candidate.exists():
                # Attempt to link from the repository test directory where a symlink typically exists
                src = repo_root / "test" / lc_path
                if src.exists():
                    _ensure_link(src, candidate)
                else:
                    raise FileNotFoundError(
                        f"Light curve file not found in workdir: {candidate}. "
                        f"Either provide an absolute path, or ensure a copy/symlink exists in the working directory."
                    )

        # Assemble configuration text
        common = self.assemble_common()
        action = self.assemble_action()

        in_path = work / f"{self.input_basename()}.in"
        in_path.write_text(common + action)

        # Run stsp (assumes 'stsp' is available on PATH)
        try:
            subprocess.run(
                ["stsp", in_path.name],
                cwd=str(work),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            rootname = str(in_path).rsplit(".in", 1)[0]
            err_path = Path(f"{rootname}_errstsp.txt")
            err_preview = None
            if err_path.exists():
                try:
                    with err_path.open("r") as f:
                        err_preview = "".join(f.readlines()[:40])
                except Exception:
                    err_preview = None
            msg = [
                f"stsp failed with exit code {e.returncode}",
                f"cmd: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}",
            ]
            if e.stdout:
                msg.append("--- stdout ---\n" + e.stdout)
            if e.stderr:
                msg.append("--- stderr ---\n" + e.stderr)
            if err_preview:
                msg.append(f"--- {err_path.name} (first 40 lines) ---\n" + err_preview)
            raise RuntimeError("\n\n".join(msg))

        rootname = str(in_path).rsplit(".in", 1)[0]
        return work, rootname

    def run(self, workdir: Optional[Path] = None) -> np.ndarray:
        work, rootname = self._prepare_and_run(workdir)

        # Read outputs using expected suffix for this action
        out_path = Path(f"{rootname}{self.config.expected_output_suffix()}")
        if not out_path.exists():
            # Provide helpful diagnostics when expected outputs are missing
            err_path = Path(f"{rootname}_errstsp.txt")
            msg = [f"Expected output not found: {out_path}"]
            if err_path.exists():
                try:
                    with err_path.open("r") as f:
                        err_preview = "".join(f.readlines()[:80])
                    msg.append(f"--- {err_path.name} (first 80 lines) ---\n{err_preview}")
                except Exception:
                    pass
            try:
                files = "\n".join(sorted(p.name for p in Path(work).iterdir()))
                msg.append(f"--- workdir listing ({work}) ---\n{files}")
            except Exception:
                pass
            raise FileNotFoundError("\n\n".join(msg))
        arr = np.loadtxt(out_path)
        return arr


class ActionLRunner(ActionRunner):
    def __init__(self, config: ActionL) -> None:
        super().__init__(config)
        if len(config.spot_triplets) != config.spot_properties.num_spots:
            raise ValueError(
                f"Expected {config.spot_properties.num_spots} spot triplets, got {len(config.spot_triplets)}"
            )

    def input_basename(self) -> str:
        return f"{super().input_basename()}-l"

    def assemble_action(self) -> str:
        return self.config.serialize_action()  # type: ignore[assignment]


class ActionMRunner(ActionRunner):
    def __init__(self, config: ActionM) -> None:
        super().__init__(config)
        seeded_fields = [
            config.sigma_radius,
            config.sigma_angle,
            config.seed_spot_triplets,
            config.seed_brightness_correction,
        ]
        any_seed = any(v is not None for v in seeded_fields)
        all_seed = (
            config.sigma_radius is not None
            and config.sigma_angle is not None
            and config.seed_spot_triplets is not None
            and config.seed_brightness_correction is not None
        )
        if any_seed and not all_seed:
            raise ValueError(
                "Seeded MCMC requires sigma_radius, sigma_angle, seed_spot_triplets, and seed_brightness_correction"
            )
        if all_seed:
            if len(config.seed_spot_triplets) != config.spot_properties.num_spots:  # type: ignore[arg-type]
                raise ValueError(
                    f"Expected {config.spot_properties.num_spots} seed spot triplets, got {len(config.seed_spot_triplets or [])}"
                )
        self._is_seeded = all_seed

    def input_basename(self) -> str:
        return f"{super().input_basename()}-{'s' if self._is_seeded else 'm'}"

    def assemble_action(self) -> str:
        return self.config.serialize_action()  # type: ignore[assignment]

    # No custom run; base class run() handles output lookup via expected_output_suffix
