from dataclasses import dataclass, fields
from typing import List, Tuple
from pathlib import Path


@dataclass 
class STSPProperties:
    def serialize_fields(self) -> List[str]:
        out: List[str] = []
        for f in fields(self):
            val = getattr(self, f.name)
            # Normalize booleans and common boolean-like strings to 0/1 expected by C
            if isinstance(val, bool):
                out.append(str(1 if val else 0) + "\n")
                continue
            if isinstance(val, str) and val.lower() in ("true", "false"):
                out.append(str(1 if val.lower() == "true" else 0) + "\n")
                continue
            if isinstance(val, (list, tuple)):
                try:
                    out.append(" ".join(str(x) for x in val) + "\n")
                except Exception:
                    out.append(str(val) + "\n")
            else:
                out.append(str(val) + "\n")
        return out




@dataclass
class PlanetProperties(STSPProperties):
    """Orbital and transit properties for a single planet.

    - t0_epoch_days: T0, time of the middle of first transit in days  (Better if this number is closer to zero)
    - period_days: Planet Period      (days)
    - transit_depth: Depth of transit (Rp/Rs)^2         (Rplanet/Rstar)^2
    - duration_days: Duration (days) of transit   (physical duration of transit, not used)
    - impact_parameter: Impact parameter  (0= planet cross over equator, use inclination angle instead)
    - inclination_deg: Inclination angle of orbit (90 deg = planet crosses over equator)
    - lambda_deg: Lambda of orbit (0 deg = orbital axis along z-axis) - angle between spin axis of star and orbital axis of planet
    - ecosw: ecosw
    - esinw: esinw
    """

    t0_epoch_days: float
    period_days: float
    transit_depth: float
    duration_days: float
    impact_parameter: float
    inclination_deg: float
    lambda_deg: float
    ecosw: float
    esinw: float


@dataclass
class StarProperties(STSPProperties):
    """Star properties.

    - mean_stellar_density: Mean Stellar density (Msun/Rsun^3)  (related to a/Rstar)
    - stellar_rotation_period_days: Stellar Rotation period (days)
    - temperature_kelvin: Stellar Temperature  (not used)
    - stellar_metallicity: Stellar metallicity  (not used)
    - rotation_axis_tilt_deg: Tilt of the rotation axis of the star down from z-axis (degrees)
    - limb_darkening: Limb darkening (4 coefficients)
    - num_limb_darkening_rings: number of rings for limb darkening approximation
    """

    mean_stellar_density: float
    stellar_rotation_period_days: float
    temperature_kelvin: float
    stellar_metallicity: float
    rotation_axis_tilt_deg: float
    limb_darkening: Tuple[float, float, float, float]
    num_limb_darkening_rings: int


@dataclass
class SpotProperties(STSPProperties):
    """Global spot configuration parameters.

    - num_spots: number of spots
    - fractional_brightness: fractional brightness of spots (0.0= totally dark, 1.0=brightness of star)
    """

    num_spots: int
    fractional_brightness: float


@dataclass
class FittingProperties(STSPProperties):
    """Description of the observed light curve segment to fit/generate.

    - data_filename: lightcurve data file
    - start_time: start time to start fitting the light curve
    - light_curve_duration_days: duration of light curve to fit (days)
    - light_data_max: real maximum of light curve data (corrected for noise), 0 -> STSP uses simple downfrommax
    - light_curve_flattened: is light curve flattened (to zero) outside of transits?
    """

    data_filename: str
    start_time: float
    light_curve_duration_days: float
    light_data_max: float
    light_curve_flattened: bool


@dataclass
class Action:
    """Top-level STSP configuration container.

    - planets: List of planet property objects
    - star_properties: star properties
    - spot_properties: spot configuration
    - fitting_properties: description of light curve data to fit or generate
    """

    planets: List[PlanetProperties]
    star_properties: StarProperties
    spot_properties: SpotProperties
    fitting_properties: FittingProperties

    def serialize_common(self) -> str:
        lines: List[str] = []
        # PLANET PROPERTIES
        lines.append("#PLANET PROPERTIES\n")
        lines.append(f"{len(self.planets)}\n")
        for p in self.planets:
            lines.extend(p.serialize_fields())
        # STAR PROPERTIES
        lines.append("#STAR PROPERTIES\n")
        lines.extend(self.star_properties.serialize_fields())
        # SPOT PROPERTIES
        lines.append("#SPOT PROPERTIES\n")
        lines.extend(self.spot_properties.serialize_fields())
        # LIGHT CURVE
        lines.append("#LIGHT CURVE\n")
        lines.extend(self.fitting_properties.serialize_fields())
        return "".join(lines)

    def serialize_action(self) -> str:
        raise NotImplementedError

    def expected_output_suffix(self) -> str:
        raise NotImplementedError


@dataclass
class ActionL(Action):
    """STSP configuration for Action-l (generate light curve).

    Extends STSP by adding action-specific parameters.

    - spot_triplets: For each spot, radius, theta (radians), phi (radians).
    - brightness_correction: Brightness correction factor associated with this spot model.
    """

    spot_triplets: List[Tuple[float, float, float]]
    brightness_correction: float = 1.0

    def serialize_action(self) -> str:
        lines: List[str] = ["#ACTION\n", "l\n"]
        for (r, th, ph) in self.spot_triplets:
            lines.append(f"{r}\n")
            lines.append(f"{th}\n")
            lines.append(f"{ph}\n")
        lines.append(f"{self.brightness_correction}\n")
        return "".join(lines)

    def expected_output_suffix(self) -> str:
        return "_lcout.txt"


@dataclass
class ActionM(Action):
    """STSP configuration for affine-invariant MCMC (Action-m/s).

    Unseeded (Action-m): provide the 5 MCMC parameters below and leave the
    seeded options as None. Seeded (Action-s): also provide `sigma_radius`,
    `sigma_angle`, and a single set of spot parameters for all spots.

    - random_seed: Random seed.
    - ascale: MCMC a scale parameter.
    - num_chains: Number of chains (population size).
    - steps_or_time: Number of steps (or time if negative; see C code).
    - calc_brightness_factor: 0 = use downfrommax, 1 = calculate brightness factor.
    - sigma_radius: Optional; required for seeded runs (Action-s).
    - sigma_angle: Optional; required for seeded runs (Action-s).
    - seed_spot_triplets: Optional spot (r, theta, phi) for each spot (Action-s).
    - seed_brightness_correction: Optional brightness factor paired with seeds.
    """

    random_seed: int
    ascale: float
    num_chains: int
    steps_or_time: int
    calc_brightness_factor: int

    sigma_radius: float | None = None
    sigma_angle: float | None = None
    seed_spot_triplets: List[Tuple[float, float, float]] | None = None
    seed_brightness_correction: float | None = None

    def serialize_action(self) -> str:
        seeded = (
            self.sigma_radius is not None
            and self.sigma_angle is not None
            and self.seed_spot_triplets is not None
            and self.seed_brightness_correction is not None
        )
        lines: List[str] = ["#ACTION\n", ("s\n" if seeded else "m\n")]
        basic = [
            self.random_seed,
            self.ascale,
            self.num_chains,
            self.steps_or_time,
            self.calc_brightness_factor,
        ]
        for v in basic:
            lines.append(f"{v}\n")
        if seeded:
            lines.append(f"{self.sigma_radius}\n")
            lines.append(f"{self.sigma_angle}\n")
            assert self.seed_spot_triplets is not None
            for (r, th, ph) in self.seed_spot_triplets:
                lines.append(f"{r}\n")
                lines.append(f"{th}\n")
                lines.append(f"{ph}\n")
            lines.append(f"{self.seed_brightness_correction}\n")
        return "".join(lines)

    def expected_output_suffix(self) -> str:
        return "_finalparam.txt"
