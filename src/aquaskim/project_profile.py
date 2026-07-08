"""Scientific experiment-profile creation for AquaSkim-Sim.

This module deliberately contains no student, course, university, or report-cover
metadata.  A public GitHub clone should ask only for variables that define an
engineering experiment.  Personal cover metadata is a separate, optional local
step that is enabled only when the final report-delivery release is frozen.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import math

import yaml

from aquaskim.paths import DIRECTORIES

USER_PROFILE_PATH = DIRECTORIES["config"] / "user_profile.yaml"


class ProfileInputError(ValueError):
    """Raised when an experiment profile contains inconsistent physical inputs."""


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_user_profile() -> dict[str, Any] | None:
    if not USER_PROFILE_PATH.exists():
        return None
    with USER_PROFILE_PATH.open("r", encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    if not isinstance(profile, dict) or "overrides" not in profile:
        raise ProfileInputError("config/user_profile.yaml must contain an 'overrides' mapping.")
    if not isinstance(profile["overrides"], dict):
        raise ProfileInputError("config/user_profile.yaml overrides must be a mapping.")
    if "submission_metadata" in profile:
        raise ProfileInputError(
            "The local profile contains legacy submission metadata. Remove it or recreate the profile with scripts\\configure_experiment.bat."
        )
    return profile


def derive_debris_count(*, basin_length_m: float, basin_width_m: float, areal_density_items_m2: float, minimum: int = 3, maximum: int = 120) -> int:
    """Derive a deterministic discrete debris field from a physical areal density.

    Debris count is therefore an internal simulation discretisation, not a
    vehicle-design input and not a mission completion criterion.
    """
    if basin_length_m <= 0.0 or basin_width_m <= 0.0:
        raise ProfileInputError("Basin dimensions must be positive.")
    if areal_density_items_m2 <= 0.0:
        raise ProfileInputError("Debris areal density must be positive.")
    estimated = int(round(basin_length_m * basin_width_m * areal_density_items_m2))
    return max(minimum, min(maximum, estimated))


def _ask_choice(prompt: str, choices: dict[str, str], default: str) -> str:
    print("\n" + prompt)
    for key, label in choices.items():
        marker = " (default)" if key == default else ""
        print(f"  {key}. {label}{marker}")
    while True:
        value = input(f"Choose [{default}]: ").strip() or default
        if value in choices:
            return value
        print("Choose one of: " + ", ".join(choices))


def _ask_text(label: str, default: str) -> str:
    answer = input(f"{label} [{default}]: ").strip()
    return answer or default


def _ask_float(label: str, default: float, *, lower: float | None = None, upper: float | None = None) -> float:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a numeric value.")
            continue
        if lower is not None and value < lower:
            print(f"Value must be >= {lower}.")
            continue
        if upper is not None and value > upper:
            print(f"Value must be <= {upper}.")
            continue
        return value


def _ask_int(label: str, default: int, *, lower: int | None = None, upper: int | None = None) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter an integer value.")
            continue
        if lower is not None and value < lower:
            print(f"Value must be >= {lower}.")
            continue
        if upper is not None and value > upper:
            print(f"Value must be <= {upper}.")
            continue
        return value


def _current_components(magnitude_mps: float, direction_deg: float) -> tuple[float, float]:
    radians = math.radians(direction_deg)
    return magnitude_mps * math.cos(radians), magnitude_mps * math.sin(radians)


def build_experiment_profile(
    *,
    profile_name: str,
    experiment_kind: str,
    base_data: dict[str, Any],
    basin_length_m: float | None = None,
    basin_width_m: float | None = None,
    water_depth_m: float | None = None,
    debris_areal_density_items_m2: float | None = None,
    debris_mean_mass_kg: float | None = None,
    basket_usable_volume_l: float | None = None,
    payload_mass_limit_kg: float | None = None,
    basket_packing_factor: float | None = None,
    battery_capacity_ah: float | None = None,
    initial_soc: float | None = None,
    mission_duration_s: float | None = None,
    current_speed_mps: float | None = None,
    current_direction_deg: float | None = None,
    cruise_speed_mps: float | None = None,
    safety_radius_m: float | None = None,
    monte_carlo_trials: int | None = None,
    animation_frames: int | None = None,
    animation_fps: int | None = None,
) -> dict[str, Any]:
    """Construct a local, Git-ignored scientific profile without personal metadata."""
    env = base_data["mission"]["environment"]
    geometry = base_data["mechanical"]["geometry"]
    energy = base_data["energy"]["battery"]
    autonomy = base_data["autonomy"]
    environment_model = base_data["environment_model"]
    debris = environment_model["debris"]
    validation = base_data.get("validation", {}).get("phase09_2", {})
    visualisation = base_data.get("visualisation", {})

    length = float(basin_length_m if basin_length_m is not None else env["length_m"])
    width = float(basin_width_m if basin_width_m is not None else env["width_m"])
    depth = float(water_depth_m if water_depth_m is not None else env["water_depth_m"])
    density = float(debris_areal_density_items_m2 if debris_areal_density_items_m2 is not None else base_data.get("experiment_model", {}).get("debris_field", {}).get("areal_density_items_m2", 0.25))
    mean_mass = float(debris_mean_mass_kg if debris_mean_mass_kg is not None else sum(map(float, debris["mass_range_kg"])) / 2.0)
    volume_l = float(basket_usable_volume_l if basket_usable_volume_l is not None else geometry["basket_volume_l"])
    mass_limit = float(payload_mass_limit_kg if payload_mass_limit_kg is not None else geometry["design_payload_kg"])
    packing = float(basket_packing_factor if basket_packing_factor is not None else base_data.get("experiment_model", {}).get("hopper", {}).get("packing_factor", 0.62))
    capacity_ah = float(battery_capacity_ah if battery_capacity_ah is not None else energy["capacity_ah"])
    soc = float(initial_soc if initial_soc is not None else autonomy["initial_soc"])
    duration = float(mission_duration_s if mission_duration_s is not None else autonomy["mission_duration_s"])
    current_speed = float(current_speed_mps if current_speed_mps is not None else math.hypot(*map(float, autonomy["current_earth_mps"])))
    current_direction = float(current_direction_deg if current_direction_deg is not None else 0.0)
    current_x, current_y = _current_components(current_speed, current_direction)
    cruise = float(cruise_speed_mps if cruise_speed_mps is not None else autonomy["cruise_speed_mps"])
    radius = float(safety_radius_m if safety_radius_m is not None else environment_model["robot_safety_radius_m"])
    trials = int(monte_carlo_trials if monte_carlo_trials is not None else validation.get("monte_carlo_trials", 24))
    frames = int(animation_frames if animation_frames is not None else visualisation.get("mission_animation_frames", 84))
    fps = int(animation_fps if animation_fps is not None else visualisation.get("mission_animation_fps", 10))

    if not 0.20 <= depth <= 5.0:
        raise ProfileInputError("Water depth must be in [0.20, 5.0] m.")
    if not 0.0 <= current_speed <= 0.30:
        raise ProfileInputError("Current speed must be in [0.00, 0.30] m/s.")
    if not 0.19 <= soc <= 1.0:
        raise ProfileInputError("Initial SOC must be in [0.19, 1.00].")
    if not 0.30 <= volume_l <= 20.0 or not 0.05 <= mass_limit <= 5.0:
        raise ProfileInputError("Hopper capacity values lie outside the supported model scope.")
    if not 0.30 <= packing <= 0.90:
        raise ProfileInputError("Packing factor must be in [0.30, 0.90].")

    debris_count = derive_debris_count(
        basin_length_m=length,
        basin_width_m=width,
        areal_density_items_m2=density,
    )
    mass_low = max(0.001, mean_mass * 0.55)
    mass_high = max(mass_low + 0.001, mean_mass * 1.45)

    overrides = {
        "mission": {"environment": {"length_m": length, "width_m": width, "water_depth_m": depth}},
        "mechanical": {"geometry": {"basket_volume_l": volume_l, "design_payload_kg": mass_limit}},
        "energy": {"battery": {"capacity_ah": capacity_ah, "nominal_energy_wh": capacity_ah * float(energy["nominal_voltage_v"])}},
        "environment_model": {
            "robot_safety_radius_m": radius,
            "debris": {"count": debris_count, "mass_range_kg": [mass_low, mass_high]},
        },
        "autonomy": {
            "current_earth_mps": [current_x, current_y],
            "initial_soc": soc,
            "mission_duration_s": duration,
            "cruise_speed_mps": cruise,
        },
        "validation": {"phase09_2": {"monte_carlo_trials": trials}},
        "visualisation": {"mission_animation_frames": frames, "mission_animation_fps": fps},
        "experiment_model": {
            "debris_field": {
                "areal_density_items_m2": density,
                "derived_discrete_item_count": debris_count,
                "mean_item_mass_kg": mean_mass,
                "interpretation": "Areal density generates a discrete stochastic field; item count is not a vehicle-design input.",
            },
            "hopper": {
                "usable_volume_l": volume_l,
                "payload_mass_limit_kg": mass_limit,
                "packing_factor": packing,
                "termination_policy": "Return when either mass or occupied-volume capacity is reached; item count is a reported outcome only.",
            },
        },
    }
    return {
        "profile": {
            "name": profile_name,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "schema_version": "3.0",
            "experiment_kind": experiment_kind,
            "notes": "Local scientific experiment profile. No personal or report-cover metadata is stored here.",
        },
        "overrides": overrides,
    }


def create_interactive_profile(base_data: dict[str, Any]) -> Path:
    """Create an engineering experiment profile using only physically meaningful inputs."""
    print("\nAquaSkim-Sim scientific experiment configuration")
    print("No personal/student data are requested or written by this workflow.")
    print("Press Enter to retain a documented engineering default.")
    print("A debris item count is derived from debris surface density and basin area; it is not asked as a mission objective.")
    print("The vehicle returns because of payload capacity, energy reserve, mission time, or safety logic—not a fixed collection quota.\n")
    profile_name = _ask_text("Experiment profile identifier", "local_experiment")
    kind = _ask_choice(
        "Select an experiment family:",
        {
            "1": "Reference configuration — documented nominal model, no parameter changes",
            "2": "Debris-field loading — vary debris surface density and particle mass",
            "3": "Hopper capacity — vary usable volume, payload mass limit and packing factor",
            "4": "Energy endurance — vary battery capacity, SOC and mission duration",
            "5": "Current robustness — vary current magnitude and direction",
            "6": "Advanced guided scenario — combine selected research variables",
        },
        "1",
    )
    env = base_data["mission"]["environment"]
    geo = base_data["mechanical"]["geometry"]
    autonomy = base_data["autonomy"]
    debris = base_data["environment_model"]["debris"]
    battery = base_data["energy"]["battery"]
    default_density = float(base_data.get("experiment_model", {}).get("debris_field", {}).get("areal_density_items_m2", 0.25))
    default_mass = sum(map(float, debris["mass_range_kg"])) / 2.0
    values: dict[str, Any] = {}

    if kind in {"2", "6"}:
        print("\n[Debris-field loading]")
        values["debris_areal_density_items_m2"] = _ask_float("Debris areal density [items/m^2]", default_density, lower=0.02, upper=1.20)
        values["debris_mean_mass_kg"] = _ask_float("Mean equivalent debris mass [kg/item]", default_mass, lower=0.002, upper=0.20)
    if kind in {"3", "6"}:
        print("\n[Hopper capacity]")
        values["basket_usable_volume_l"] = _ask_float("Usable hopper volume [L]", float(geo["basket_volume_l"]), lower=0.30, upper=20.0)
        values["payload_mass_limit_kg"] = _ask_float("Payload mass limit [kg]", float(geo["design_payload_kg"]), lower=0.05, upper=5.0)
        values["basket_packing_factor"] = _ask_float("Packing factor [-]", float(base_data.get("experiment_model", {}).get("hopper", {}).get("packing_factor", 0.62)), lower=0.30, upper=0.90)
    if kind in {"4", "6"}:
        print("\n[Energy endurance]")
        values["battery_capacity_ah"] = _ask_float("Battery capacity [Ah]", float(battery["capacity_ah"]), lower=1.0, upper=30.0)
        values["initial_soc"] = _ask_float("Initial usable SOC [0..1]", float(autonomy["initial_soc"]), lower=0.19, upper=1.0)
        values["mission_duration_s"] = _ask_float("Mission time limit [s]", float(autonomy["mission_duration_s"]), lower=60.0, upper=1800.0)
    if kind in {"5", "6"}:
        print("\n[Current robustness]")
        values["current_speed_mps"] = _ask_float("Current magnitude [m/s]", 0.0, lower=0.0, upper=0.30)
        values["current_direction_deg"] = _ask_float("Current direction [deg, 0=East, 90=North]", 0.0, lower=-360.0, upper=360.0)
    if kind == "6":
        print("\n[Experimental basin and visualisation]")
        values["basin_length_m"] = _ask_float("Basin length [m]", float(env["length_m"]), lower=6.0, upper=60.0)
        values["basin_width_m"] = _ask_float("Basin width [m]", float(env["width_m"]), lower=4.0, upper=40.0)
        values["water_depth_m"] = _ask_float("Water depth [m]", float(env["water_depth_m"]), lower=0.20, upper=5.0)
        values["cruise_speed_mps"] = _ask_float("Cruise speed [m/s]", float(autonomy["cruise_speed_mps"]), lower=0.05, upper=0.60)
        values["safety_radius_m"] = _ask_float("Robot safety radius [m]", float(base_data["environment_model"]["robot_safety_radius_m"]), lower=0.10, upper=1.00)
        values["monte_carlo_trials"] = _ask_int("Monte Carlo trials", int(base_data.get("validation", {}).get("phase09_2", {}).get("monte_carlo_trials", 24)), lower=8, upper=200)
        values["animation_frames"] = _ask_int("Frames per mission replay", int(base_data.get("visualisation", {}).get("mission_animation_frames", 84)), lower=24, upper=240)
        values["animation_fps"] = _ask_int("Replay frames per second", int(base_data.get("visualisation", {}).get("mission_animation_fps", 10)), lower=4, upper=30)

    profile = build_experiment_profile(
        profile_name=profile_name,
        experiment_kind={"1":"reference","2":"debris_loading","3":"hopper_capacity","4":"energy_endurance","5":"current_robustness","6":"advanced"}[kind],
        base_data=base_data,
        **values,
    )
    USER_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_PROFILE_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(profile, handle, allow_unicode=True, sort_keys=False)
    return USER_PROFILE_PATH
