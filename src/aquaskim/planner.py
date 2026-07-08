"""Grid-based planning utilities for AquaSkim-Sim Phase 08.

The planner consumes the inflated occupancy grid generated in Phase 07.  It is
intentionally deterministic: 8-connected A* uses a fixed neighbour order and
an admissible Euclidean heuristic.  This makes every route reproducible from
one configuration file and one debris map.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Iterable

import numpy as np

from aquaskim.environment import GridMap


class PlannerError(ValueError):
    """Raised when a requested grid route cannot be constructed."""


GridIndex = tuple[int, int]  # (ix, iy)


@dataclass(frozen=True)
class PlannedPath:
    start_m: tuple[float, float]
    goal_m: tuple[float, float]
    grid_indices: tuple[GridIndex, ...]
    waypoints_m: tuple[tuple[float, float], ...]
    length_m: float
    expanded_nodes: int

    def as_row(self, *, route_id: str, mission_leg: str) -> list[dict[str, object]]:
        return [
            {
                "route_id": route_id,
                "mission_leg": mission_leg,
                "waypoint_index": index,
                "x_m": point[0],
                "y_m": point[1],
                "cumulative_length_m": cumulative_polyline_length(self.waypoints_m[: index + 1]),
            }
            for index, point in enumerate(self.waypoints_m)
        ]


def cumulative_polyline_length(points: Iterable[tuple[float, float]]) -> float:
    items = list(points)
    return float(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(items[:-1], items[1:])))


class AStarPlanner:
    """8-connected A* planner on a Phase 07 configuration-space grid."""

    _NEIGHBOURS: tuple[tuple[int, int], ...] = (
        (1, 0), (0, 1), (-1, 0), (0, -1),
        (1, 1), (-1, 1), (-1, -1), (1, -1),
    )

    def __init__(self, grid: GridMap) -> None:
        self.grid = grid
        if grid.occupied.ndim != 2:
            raise PlannerError("Occupancy grid must be two-dimensional.")

    @property
    def width(self) -> int:
        return int(self.grid.occupied.shape[1])

    @property
    def height(self) -> int:
        return int(self.grid.occupied.shape[0])

    def in_bounds(self, cell: GridIndex) -> bool:
        ix, iy = cell
        return 0 <= ix < self.width and 0 <= iy < self.height

    def occupied(self, cell: GridIndex) -> bool:
        ix, iy = cell
        return bool(self.grid.occupied[iy, ix])

    def nearest_cell(self, point_m: tuple[float, float]) -> GridIndex:
        x, y = point_m
        ix = int(np.argmin(np.abs(self.grid.x_centers_m - x)))
        iy = int(np.argmin(np.abs(self.grid.y_centers_m - y)))
        return ix, iy

    def cell_center(self, cell: GridIndex) -> tuple[float, float]:
        ix, iy = cell
        if not self.in_bounds(cell):
            raise PlannerError(f"Cell outside grid: {cell}")
        return float(self.grid.x_centers_m[ix]), float(self.grid.y_centers_m[iy])

    def nearest_free_cell(self, cell: GridIndex, *, max_radius_cells: int = 12) -> GridIndex:
        if self.in_bounds(cell) and not self.occupied(cell):
            return cell
        ix0, iy0 = cell
        candidates: list[tuple[float, GridIndex]] = []
        for radius in range(1, max_radius_cells + 1):
            for iy in range(iy0 - radius, iy0 + radius + 1):
                for ix in range(ix0 - radius, ix0 + radius + 1):
                    candidate = (ix, iy)
                    if not self.in_bounds(candidate) or self.occupied(candidate):
                        continue
                    distance = math.hypot(ix - ix0, iy - iy0)
                    candidates.append((distance, candidate))
            if candidates:
                return min(candidates, key=lambda item: (item[0], item[1][1], item[1][0]))[1]
        raise PlannerError(f"No free cell within {max_radius_cells} cells of {cell}.")

    @staticmethod
    def _heuristic(a: GridIndex, b: GridIndex) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _valid_transition(self, current: GridIndex, nxt: GridIndex) -> bool:
        if not self.in_bounds(nxt) or self.occupied(nxt):
            return False
        dx, dy = nxt[0] - current[0], nxt[1] - current[1]
        # Prevent diagonal corner-cutting through two occupied orthogonal cells.
        if abs(dx) == 1 and abs(dy) == 1:
            if self.occupied((current[0] + dx, current[1])) and self.occupied((current[0], current[1] + dy)):
                return False
        return True

    def plan(self, start_m: tuple[float, float], goal_m: tuple[float, float]) -> PlannedPath:
        start = self.nearest_free_cell(self.nearest_cell(start_m))
        goal = self.nearest_free_cell(self.nearest_cell(goal_m))
        open_heap: list[tuple[float, float, int, GridIndex]] = []
        serial = 0
        heapq.heappush(open_heap, (self._heuristic(start, goal), 0.0, serial, start))
        came_from: dict[GridIndex, GridIndex] = {}
        g_score: dict[GridIndex, float] = {start: 0.0}
        expanded = 0
        closed: set[GridIndex] = set()

        while open_heap:
            _, cost, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            expanded += 1
            if current == goal:
                break
            for dx, dy in self._NEIGHBOURS:
                neighbour = (current[0] + dx, current[1] + dy)
                if not self._valid_transition(current, neighbour):
                    continue
                step = math.sqrt(2.0) if dx != 0 and dy != 0 else 1.0
                tentative = cost + step
                if tentative + 1e-12 < g_score.get(neighbour, float("inf")):
                    came_from[neighbour] = current
                    g_score[neighbour] = tentative
                    serial += 1
                    score = tentative + self._heuristic(neighbour, goal)
                    heapq.heappush(open_heap, (score, tentative, serial, neighbour))
        else:
            raise PlannerError(f"No A* route exists from {start_m} to {goal_m}.")

        if goal not in closed:
            raise PlannerError(f"A* did not reach goal from {start_m} to {goal_m}.")

        path_indices = [goal]
        while path_indices[-1] != start:
            path_indices.append(came_from[path_indices[-1]])
        path_indices.reverse()
        points = [self.cell_center(cell) for cell in path_indices]
        simplified = simplify_polyline(points, self)
        # Route simplification is constrained by the inflated grid; each retained
        # segment has a configuration-space line-of-sight check.
        return PlannedPath(
            start_m=start_m,
            goal_m=goal_m,
            grid_indices=tuple(path_indices),
            waypoints_m=tuple(simplified),
            length_m=cumulative_polyline_length(simplified),
            expanded_nodes=expanded,
        )

    def line_is_free(self, start_m: tuple[float, float], end_m: tuple[float, float]) -> bool:
        length = math.hypot(end_m[0] - start_m[0], end_m[1] - start_m[1])
        count = max(2, int(math.ceil(length / (0.45 * self.grid.resolution_m))))
        for fraction in np.linspace(0.0, 1.0, count):
            x = start_m[0] + float(fraction) * (end_m[0] - start_m[0])
            y = start_m[1] + float(fraction) * (end_m[1] - start_m[1])
            cell = self.nearest_cell((x, y))
            if not self.in_bounds(cell) or self.occupied(cell):
                return False
        return True


def simplify_polyline(points: list[tuple[float, float]], planner: AStarPlanner) -> list[tuple[float, float]]:
    """Line-of-sight simplify a safe grid path without crossing occupied cells."""
    if len(points) <= 2:
        return points.copy()
    simplified = [points[0]]
    anchor = 0
    while anchor < len(points) - 1:
        candidate = len(points) - 1
        while candidate > anchor + 1 and not planner.line_is_free(points[anchor], points[candidate]):
            candidate -= 1
        simplified.append(points[candidate])
        anchor = candidate
    return simplified
