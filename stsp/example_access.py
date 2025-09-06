import ctypes
import glob
import os
import subprocess
import sys
import sysconfig


def main_ctype():
    site_packages_path = sysconfig.get_paths()["purelib"]
    pattern = os.path.join(site_packages_path, "stsp", "stsp.*.so")
    library_path = glob.glob(pattern)[0]
    c_stsp = ctypes.CDLL(library_path)

    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, sys.argv[1])

    c_stsp.main(2, config_path)
    
def main_bin():
    site_packages_path = sysconfig.get_paths()["purelib"]
    bin_path = os.path.join(site_packages_path, "stsp", "stsp_executable")

    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, sys.argv[1])

    # Run stsp (assumes 'stsp' is available on PATH)
    try:
        proc = subprocess.run(
            [bin_path, sys.argv[1]],
            cwd=current_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        print(proc.stdout)
    except subprocess.CalledProcessError as e:
        msg = [
            f"stsp failed with exit code {e.returncode}",
            f"cmd: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}",
        ]
        if e.stdout:
            msg.append("--- stdout ---\n" + e.stdout)
        if e.stderr:
            msg.append("--- stderr ---\n" + e.stderr)
        raise RuntimeError("\n\n".join(msg))
