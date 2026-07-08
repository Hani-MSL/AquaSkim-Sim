"""Phase 07 environment, occupancy, debris and virtual-sensor models.

This module adds the operational world around the Phase 06 vessel model.  The
model remains deliberately transparent: all obstacles are analytic circles or
axis-aligned rectangles, occupancy is derived from a documented grid resolution,
and virtual sensors are deterministic when their random seed is fixed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

import numpy as np


class EnvironmentError(ValueError):
    """Raised when a world, object or sensor configuration is invalid."""


@dataclass(frozen=True)
class CircleObstacle:
    identifier: str
    center_m: tuple[float, float]
    radius_m: float
    kind: str = "circle"

    def signed_distance_m(self, x_m: float, y_m: float) -> float:
        return math.hypot(x_m - self.center_m[0], y_m - self.center_m[1]) - self.radius_m


@dataclass(frozen=True)
class RectangleObstacle:
    identifier: str
    center_m: tuple[float, float]
    size_m: tuple[float, float]
    kind: str = "rectangle"

    @property
    def half_x_m(self) -> float:
        return self.size_m[0] / 2.0

    @property
    def half_y_m(self) -> float:
        return self.size_m[1] / 2.0

    def signed_distance_m(self, x_m: float, y_m: float) -> float:
        """Signed Euclidean distance from a point to an axis-aligned rectangle."""
        dx = abs(x_m - self.center_m[0]) - self.half_x_m
        dy = abs(y_m - self.center_m[1]) - self.half_y_m
        outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
        inside = min(max(dx, dy), 0.0)
        return outside + inside


Obstacle = CircleObstacle | RectangleObstacle


@dataclass(frozen=True)
class DebrisObject:
    identifier: str
    position_m: tuple[float, float]
    radius_m: float
    mass_kg: float
    kind: str


@dataclass(frozen=True)
class GridMap:
    resolution_m: float
    x_centers_m: np.ndarray
    y_centers_m: np.ndarray
    occupied: np.ndarray
    clearance_m: float

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(int(value) for value in self.occupied.shape)

    @property
    def occupied_fraction(self) -> float:
        return float(np.mean(self.occupied))

    def occupancy_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for iy, y_m in enumerate(self.y_centers_m):
            for ix, x_m in enumerate(self.x_centers_m):
                rows.append(
                    {
                        "ix": ix,
                        "iy": iy,
                        "x_center_m": float(x_m),
                        "y_center_m": float(y_m),
                        "occupied": int(bool(self.occupied[iy, ix])),
                    }
                )
        return rows


@dataclass(frozen=True)
class SensorSpecification:
    name: str
    update_hz: float
    range_m: float | None
    field_of_view_deg: float | None
    position_std_m: float | None
    heading_std_deg: float | None
    detection_probability_at_zero_range: float | None
    notes: str

    def as_row(self) -> dict[str, object]:
        return {
            "sensor": self.name,
            "update_hz": self.update_hz,
            "range_m": self.range_m if self.range_m is not None else "",
            "field_of_view_deg": self.field_of_view_deg if self.field_of_view_deg is not None else "",
            "position_std_m": self.position_std_m if self.position_std_m is not None else "",
            "heading_std_deg": self.heading_std_deg if self.heading_std_deg is not None else "",
            "detection_probability_at_zero_range": (
                self.detection_probability_at_zero_range
                if self.detection_probability_at_zero_range is not None
                else ""
            ),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SensorSettings:
    gps_position_std_m: float
    compass_heading_std_deg: float
    range_sensor_max_range_m: float
    range_sensor_fov_deg: float
    range_sensor_beam_count: int
    range_sensor_step_m: float
    debris_detection_range_m: float
    debris_detection_fov_deg: float
    debris_detection_probability_at_zero_range: float
    debris_detection_min_probability: float
    demo_duration_s: float
    demo_sample_period_s: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "SensorSettings":
        section = data["sensors"]
        return cls(
            gps_position_std_m=float(section["gps"]["position_std_m"]),
            compass_heading_std_deg=float(section["compass"]["heading_std_deg"]),
            range_sensor_max_range_m=float(section["range_sensor"]["max_range_m"]),
            range_sensor_fov_deg=float(section["range_sensor"]["field_of_view_deg"]),
            range_sensor_beam_count=int(section["range_sensor"]["beam_count"]),
            range_sensor_step_m=float(section["range_sensor"]["ray_step_m"]),
            debris_detection_range_m=float(section["debris_detector"]["max_range_m"]),
            debris_detection_fov_deg=float(section["debris_detector"]["field_of_view_deg"]),
            debris_detection_probability_at_zero_range=float(section["debris_detector"]["probability_at_zero_range"]),
            debris_detection_min_probability=float(section["debris_detector"]["minimum_probability"]),
            demo_duration_s=float(section["demo"]["duration_s"]),
            demo_sample_period_s=float(section["demo"]["sample_period_s"]),
        )

    def validate(self) -> None:
        numeric_values = {
            "gps_position_std_m": self.gps_position_std_m,
            "compass_heading_std_deg": self.compass_heading_std_deg,
            "range_sensor_max_range_m": self.range_sensor_max_range_m,
            "range_sensor_fov_deg": self.range_sensor_fov_deg,
            "range_sensor_step_m": self.range_sensor_step_m,
            "debris_detection_range_m": self.debris_detection_range_m,
            "debris_detection_fov_deg": self.debris_detection_fov_deg,
            "demo_duration_s": self.demo_duration_s,
            "demo_sample_period_s": self.demo_sample_period_s,
        }
        for name, value in numeric_values.items():
            if value <= 0.0:
                raise EnvironmentError(f"{name} must be positive.")
        if self.range_sensor_beam_count < 1:
            raise EnvironmentError("range_sensor_beam_count must be at least 1.")
        for name, value in {
            "debris_detection_probability_at_zero_range": self.debris_detection_probability_at_zero_range,
            "debris_detection_min_probability": self.debris_detection_min_probability,
        }.items():
            if not 0.0 <= value <= 1.0:
                raise EnvironmentError(f"{name} must be between 0 and 1.")

    def specifications(self) -> list[SensorSpecification]:
        return [
            SensorSpecification(
                name="GNSS / UWB position surrogate",
                update_hz=1.0 / self.demo_sample_period_s,
                range_m=None,
                field_of_view_deg=None,
                position_std_m=self.gps_position_std_m,
                heading_std_deg=None,
                detection_probability_at_zero_range=None,
                notes="Gaussian planar position perturbation; deterministic seed in the demo.",
            ),
            SensorSpecification(
                name="Compass / yaw surrogate",
                update_hz=1.0 / self.demo_sample_period_s,
                range_m=None,
                field_of_view_deg=None,
                position_std_m=None,
                heading_std_deg=self.compass_heading_std_deg,
                detection_probability_at_zero_range=None,
                notes="Gaussian heading perturbation; wrapped to [-180, 180) degrees.",
            ),
            SensorSpecification(
                name="Forward multi-beam range sensor",
                update_hz=1.0 / self.demo_sample_period_s,
                range_m=self.range_sensor_max_range_m,
                field_of_view_deg=self.range_sensor_fov_deg,
                position_std_m=None,
                heading_std_deg=None,
                detection_probability_at_zero_range=None,
                notes=f"{self.range_sensor_beam_count} analytic ray casts with {self.range_sensor_step_m:.3f} m step.",
            ),
            SensorSpecification(
                name="Floating-debris detector surrogate",
                update_hz=1.0 / self.demo_sample_period_s,
                range_m=self.debris_detection_range_m,
                field_of_view_deg=self.debris_detection_fov_deg,
                position_std_m=None,
                heading_std_deg=None,
                detection_probability_at_zero_range=self.debris_detection_probability_at_zero_range,
                notes="Range-decaying probability with seeded Bernoulli detection outcome.",
            ),
        ]


@dataclass(frozen=True)
class EnvironmentSettings:
    length_m: float
    width_m: float
    water_depth_m: float
    home_position_m: tuple[float, float]
    occupancy_resolution_m: float
    robot_safety_radius_m: float
    debris_count: int
    debris_radius_range_m: tuple[float, float]
    debris_mass_range_kg: tuple[float, float]
    debris_seed: int
    debris_clearance_m: float
    obstacles: tuple[Obstacle, ...]

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "EnvironmentSettings":
        mission_environment = data["mission"]["environment"]
        section = data["environment_model"]
        obstacle_items = tuple(_obstacle_from_mapping(item) for item in section["obstacles"])
        result = cls(
            length_m=float(mission_environment["length_m"]),
            width_m=float(mission_environment["width_m"]),
            water_depth_m=float(mission_environment["water_depth_m"]),
            home_position_m=(
                float(mission_environment["home_position_m"][0]),
                float(mission_environment["home_position_m"][1]),
            ),
            occupancy_resolution_m=float(section["occupancy_grid_resolution_m"]),
            robot_safety_radius_m=float(section["robot_safety_radius_m"]),
            debris_count=int(section["debris"]["count"]),
            debris_radius_range_m=(
                float(section["debris"]["radius_range_m"][0]),
                float(section["debris"]["radius_range_m"][1]),
            ),
            debris_mass_range_kg=(
                float(section["debris"]["mass_range_kg"][0]),
                float(section["debris"]["mass_range_kg"][1]),
            ),
            debris_seed=int(section["debris"]["seed"]),
            debris_clearance_m=float(section["debris"]["clearance_m"]),
            obstacles=obstacle_items,
        )
        result.validate()
        return result

    def validate(self) -> None:
        for name, value in {
            "length_m": self.length_m,
            "width_m": self.width_m,
            "water_depth_m": self.water_depth_m,
            "occupancy_resolution_m": self.occupancy_resolution_m,
            "robot_safety_radius_m": self.robot_safety_radius_m,
            "debris_clearance_m": self.debris_clearance_m,
        }.items():
            if value <= 0.0:
                raise EnvironmentError(f"{name} must be positive.")
        if self.debris_count < 1:
            raise EnvironmentError("debris_count must be at least one.")
        if self.debris_radius_range_m[0] <= 0.0 or self.debris_radius_range_m[0] > self.debris_radius_range_m[1]:
            raise EnvironmentError("debris radius range is invalid.")
        if self.debris_mass_range_kg[0] <= 0.0 or self.debris_mass_range_kg[0] > self.debris_mass_range_kg[1]:
            raise EnvironmentError("debris mass range is invalid.")
        if not self.is_inside_bounds(*self.home_position_m, clearance_m=self.robot_safety_radius_m):
            raise EnvironmentError("home_position_m is not inside the safe operational boundary.")
        for obstacle in self.obstacles:
            if not self.is_inside_bounds(*_obstacle_center(obstacle), clearance_m=0.0):
                raise EnvironmentError(f"Obstacle {obstacle.identifier} center is outside the environment.")

    def is_inside_bounds(self, x_m: float, y_m: float, *, clearance_m: float = 0.0) -> bool:
        return (
            clearance_m <= x_m <= self.length_m - clearance_m
            and clearance_m <= y_m <= self.width_m - clearance_m
        )

    def signed_distance_to_bounds_m(self, x_m: float, y_m: float) -> float:
        return min(x_m, self.length_m - x_m, y_m, self.width_m - y_m)

    def point_is_navigable(self, x_m: float, y_m: float, *, clearance_m: float = 0.0) -> bool:
        if not self.is_inside_bounds(x_m, y_m, clearance_m=clearance_m):
            return False
        return all(obstacle.signed_distance_m(x_m, y_m) >= clearance_m for obstacle in self.obstacles)

    def signed_distance_to_nearest_hazard_m(self, x_m: float, y_m: float) -> float:
        distances = [self.signed_distance_to_bounds_m(x_m, y_m)]
        distances.extend(obstacle.signed_distance_m(x_m, y_m) for obstacle in self.obstacles)
        return min(distances)

    def occupancy_grid(self, *, clearance_m: float | None = None) -> GridMap:
        clearance = self.robot_safety_radius_m if clearance_m is None else clearance_m
        x_centers = np.arange(self.occupancy_resolution_m / 2.0, self.length_m, self.occupancy_resolution_m)
        y_centers = np.arange(self.occupancy_resolution_m / 2.0, self.width_m, self.occupancy_resolution_m)
        occupied = np.zeros((len(y_centers), len(x_centers)), dtype=bool)
        for iy, y_m in enumerate(y_centers):
            for ix, x_m in enumerate(x_centers):
                occupied[iy, ix] = not self.point_is_navigable(float(x_m), float(y_m), clearance_m=clearance)
        return GridMap(
            resolution_m=self.occupancy_resolution_m,
            x_centers_m=x_centers,
            y_centers_m=y_centers,
            occupied=occupied,
            clearance_m=clearance,
        )

    def generate_debris(self) -> list[DebrisObject]:
        rng = np.random.default_rng(self.debris_seed)
        debris: list[DebrisObject] = []
        maximum_attempts = self.debris_count * 2000
        attempts = 0
        while len(debris) < self.debris_count and attempts < maximum_attempts:
            attempts += 1
            radius = float(rng.uniform(*self.debris_radius_range_m))
            x_m = float(rng.uniform(self.debris_clearance_m + radius, self.length_m - self.debris_clearance_m - radius))
            y_m = float(rng.uniform(self.debris_clearance_m + radius, self.width_m - self.debris_clearance_m - radius))
            clearance = self.debris_clearance_m + radius
            if not self.point_is_navigable(x_m, y_m, clearance_m=clearance):
                continue
            if math.hypot(x_m - self.home_position_m[0], y_m - self.home_position_m[1]) < 2.0 * clearance:
                continue
            if any(math.hypot(x_m - item.position_m[0], y_m - item.position_m[1]) < radius + item.radius_m + self.debris_clearance_m for item in debris):
                continue
            mass = float(rng.uniform(*self.debris_mass_range_kg))
            debris.append(
                DebrisObject(
                    identifier=f"debris_{len(debris)+1:02d}",
                    position_m=(x_m, y_m),
                    radius_m=radius,
                    mass_kg=mass,
                    kind="floating_litter",
                )
            )
        if len(debris) != self.debris_count:
            raise EnvironmentError("Could not place all debris objects without violating clearances.")
        return debris

    def object_rows(self, debris: Iterable[DebrisObject]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = [
            {
                "identifier": "home_station",
                "object_type": "home",
                "geometry_type": "point",
                "x_m": self.home_position_m[0],
                "y_m": self.home_position_m[1],
                "size_x_or_radius_m": 0.0,
                "size_y_m": 0.0,
                "mass_kg": 0.0,
            }
        ]
        for obstacle in self.obstacles:
            if isinstance(obstacle, CircleObstacle):
                rows.append({
                    "identifier": obstacle.identifier,
                    "object_type": "obstacle",
                    "geometry_type": "circle",
                    "x_m": obstacle.center_m[0],
                    "y_m": obstacle.center_m[1],
                    "size_x_or_radius_m": obstacle.radius_m,
                    "size_y_m": 0.0,
                    "mass_kg": 0.0,
                })
            else:
                rows.append({
                    "identifier": obstacle.identifier,
                    "object_type": "obstacle",
                    "geometry_type": "rectangle",
                    "x_m": obstacle.center_m[0],
                    "y_m": obstacle.center_m[1],
                    "size_x_or_radius_m": obstacle.size_m[0],
                    "size_y_m": obstacle.size_m[1],
                    "mass_kg": 0.0,
                })
        for item in debris:
            rows.append({
                "identifier": item.identifier,
                "object_type": "debris",
                "geometry_type": "circle",
                "x_m": item.position_m[0],
                "y_m": item.position_m[1],
                "size_x_or_radius_m": item.radius_m,
                "size_y_m": 0.0,
                "mass_kg": item.mass_kg,
            })
        return rows


def _obstacle_from_mapping(data: dict[str, Any]) -> Obstacle:
    kind = str(data["type"])
    center = (float(data["center_m"][0]), float(data["center_m"][1]))
    identifier = str(data["id"])
    if kind == "circle":
        return CircleObstacle(identifier=identifier, center_m=center, radius_m=float(data["radius_m"]))
    if kind == "rectangle":
        return RectangleObstacle(
            identifier=identifier,
            center_m=center,
            size_m=(float(data["size_m"][0]), float(data["size_m"][1])),
        )
    raise EnvironmentError(f"Unsupported obstacle type: {kind}")


def _obstacle_center(obstacle: Obstacle) -> tuple[float, float]:
    return obstacle.center_m


def wrap_angle_deg(value_deg: float) -> float:
    return (value_deg + 180.0) % 360.0 - 180.0


def interpolate_polyline(waypoints_m: list[tuple[float, float]], speed_mps: float, duration_s: float, sample_period_s: float) -> list[dict[str, float]]:
    """Return a deterministic constant-speed time history along a waypoint polyline."""
    if len(waypoints_m) < 2:
        raise EnvironmentError("At least two demo waypoints are required.")
    if speed_mps <= 0.0 or duration_s <= 0.0 or sample_period_s <= 0.0:
        raise EnvironmentError("Speed, duration and sample period must be positive.")

    segments: list[tuple[tuple[float, float], tuple[float, float], float, float]] = []
    for start, end in zip(waypoints_m[:-1], waypoints_m[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            continue
        heading = math.atan2(dy, dx)
        segments.append((start, end, length, heading))
    if not segments:
        raise EnvironmentError("Demo path has no non-zero segments.")

    total_length = sum(item[2] for item in segments)
    times = np.arange(0.0, duration_s + 1e-12, sample_period_s)
    rows: list[dict[str, float]] = []
    for time_s in times:
        distance = min(float(time_s * speed_mps), total_length)
        remaining = distance
        chosen = segments[-1]
        for segment in segments:
            if remaining <= segment[2]:
                chosen = segment
                break
            remaining -= segment[2]
        start, end, length, heading = chosen
        fraction = min(remaining / length, 1.0)
        x_m = start[0] + fraction * (end[0] - start[0])
        y_m = start[1] + fraction * (end[1] - start[1])
        rows.append({
            "time_s": float(time_s),
            "truth_x_m": x_m,
            "truth_y_m": y_m,
            "truth_heading_deg": math.degrees(heading),
            "truth_speed_mps": speed_mps if distance < total_length else 0.0,
        })
    return rows


def raycast_distance_m(
    environment: EnvironmentSettings,
    x_m: float,
    y_m: float,
    heading_rad: float,
    *,
    max_range_m: float,
    step_m: float,
) -> float:
    """Analytic-world ray marcher used by the virtual range sensor."""
    if max_range_m <= 0.0 or step_m <= 0.0:
        raise EnvironmentError("Raycast max_range_m and step_m must be positive.")
    distance = 0.0
    while distance <= max_range_m + 1e-12:
        probe_x = x_m + distance * math.cos(heading_rad)
        probe_y = y_m + distance * math.sin(heading_rad)
        if not environment.point_is_navigable(probe_x, probe_y, clearance_m=0.0):
            return float(distance)
        distance += step_m
    return float(max_range_m)


def forward_range_measurements(
    environment: EnvironmentSettings,
    x_m: float,
    y_m: float,
    heading_rad: float,
    settings: SensorSettings,
) -> list[tuple[float, float]]:
    beam_offsets_deg = np.linspace(
        -settings.range_sensor_fov_deg / 2.0,
        settings.range_sensor_fov_deg / 2.0,
        settings.range_sensor_beam_count,
    )
    return [
        (
            float(offset),
            raycast_distance_m(
                environment,
                x_m,
                y_m,
                heading_rad + math.radians(float(offset)),
                max_range_m=settings.range_sensor_max_range_m,
                step_m=settings.range_sensor_step_m,
            ),
        )
        for offset in beam_offsets_deg
    ]


def debris_detection_probability(distance_m: float, settings: SensorSettings) -> float:
    if distance_m > settings.debris_detection_range_m:
        return 0.0
    normalized = max(0.0, 1.0 - distance_m / settings.debris_detection_range_m)
    value = settings.debris_detection_min_probability + (
        settings.debris_detection_probability_at_zero_range - settings.debris_detection_min_probability
    ) * normalized
    return float(np.clip(value, 0.0, 1.0))


def is_inside_fov(relative_bearing_deg: float, field_of_view_deg: float) -> bool:
    return abs(wrap_angle_deg(relative_bearing_deg)) <= field_of_view_deg / 2.0


def simulate_sensor_demo(
    environment: EnvironmentSettings,
    sensor_settings: SensorSettings,
    debris: list[DebrisObject],
    *,
    cruise_speed_mps: float,
    random_seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, float]]]:
    """Create a recorded synthetic survey for downstream autonomy work.

    The route is intentionally clear of obstacles.  It is not yet an autonomous
    path; it provides repeatable truth/sensor pairs and detections for Phase 08.
    """
    sensor_settings.validate()
    margin = max(0.85, environment.robot_safety_radius_m + 0.35)
    waypoints = [
        environment.home_position_m,
        (environment.length_m - margin, margin),
        (environment.length_m - margin, environment.width_m - margin),
        (margin, environment.width_m - margin),
        (margin, margin),
    ]
    truth_rows = interpolate_polyline(
        waypoints,
        speed_mps=cruise_speed_mps,
        duration_s=sensor_settings.demo_duration_s,
        sample_period_s=sensor_settings.demo_sample_period_s,
    )
    rng = np.random.default_rng(random_seed)
    sensor_rows: list[dict[str, object]] = []
    detection_rows: list[dict[str, object]] = []
    for row in truth_rows:
        heading_rad = math.radians(row["truth_heading_deg"])
        gps_x = row["truth_x_m"] + float(rng.normal(0.0, sensor_settings.gps_position_std_m))
        gps_y = row["truth_y_m"] + float(rng.normal(0.0, sensor_settings.gps_position_std_m))
        heading_measured = wrap_angle_deg(row["truth_heading_deg"] + float(rng.normal(0.0, sensor_settings.compass_heading_std_deg)))
        ranges = forward_range_measurements(environment, row["truth_x_m"], row["truth_y_m"], heading_rad, sensor_settings)
        sensor_record: dict[str, object] = {
            **row,
            "gps_x_m": gps_x,
            "gps_y_m": gps_y,
            "compass_heading_deg": heading_measured,
        }
        for index, (offset_deg, distance_m) in enumerate(ranges):
            sensor_record[f"range_beam_{index}_offset_deg"] = offset_deg
            sensor_record[f"range_beam_{index}_m"] = distance_m
        sensor_rows.append(sensor_record)

        for item in debris:
            dx = item.position_m[0] - row["truth_x_m"]
            dy = item.position_m[1] - row["truth_y_m"]
            distance_m = math.hypot(dx, dy)
            bearing_deg = wrap_angle_deg(math.degrees(math.atan2(dy, dx) - heading_rad))
            in_fov = is_inside_fov(bearing_deg, sensor_settings.debris_detection_fov_deg)
            probability = debris_detection_probability(distance_m, sensor_settings) if in_fov else 0.0
            detected = bool(rng.random() < probability)
            detection_rows.append(
                {
                    "time_s": row["time_s"],
                    "debris_id": item.identifier,
                    "truth_distance_m": distance_m,
                    "relative_bearing_deg": bearing_deg,
                    "in_fov": int(in_fov),
                    "detection_probability": probability,
                    "detected": int(detected),
                }
            )
    return sensor_rows, detection_rows, truth_rows
