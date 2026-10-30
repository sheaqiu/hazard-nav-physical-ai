"""Convert a ROS LaserScan-like sequence into controller-oriented sectors."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .mission_engine import ScanFrame


def _normalise(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _sector_values(
    ranges: Sequence[float],
    angle_min: float,
    angle_increment: float,
    center_deg: float,
    width_deg: float,
    range_max: float,
) -> list[float]:
    center = math.radians(center_deg)
    half_width = math.radians(width_deg) / 2.0
    values: list[float] = []
    for index, raw in enumerate(ranges):
        angle = _normalise(angle_min + index * angle_increment)
        if abs(_normalise(angle - center)) > half_width:
            continue
        if math.isinf(raw):
            values.append(range_max)
        elif math.isfinite(raw) and raw > 0.0:
            values.append(min(float(raw), range_max))
    return values


def _minimum(values: list[float], range_max: float) -> float:
    return min(values) if values else range_max


def _percentile(values: list[float], quantile: float, range_max: float) -> float:
    if not values:
        return range_max
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def summarize_scan(
    ranges: Sequence[float],
    angle_min: float,
    angle_increment: float,
    range_max: float,
) -> ScanFrame:
    if not ranges or angle_increment <= 0.0:
        raise ValueError("LaserScan contains no usable samples")
    if not math.isfinite(range_max) or range_max <= 0.0:
        range_max = 8.0

    sector = lambda center, width: _sector_values(  # noqa: E731
        ranges, angle_min, angle_increment, center, width, range_max
    )

    left = sector(90.0, 34.0)
    right = sector(-90.0, 34.0)
    return ScanFrame(
        front_m=_minimum(sector(0.0, 22.0), range_max),
        left_m=_percentile(left, 0.25, range_max),
        right_m=_percentile(right, 0.25, range_max),
        front_left_m=_minimum(sector(42.0, 34.0), range_max),
        front_right_m=_minimum(sector(-42.0, 34.0), range_max),
        left_open_m=_percentile(sector(90.0, 70.0), 0.85, range_max),
        right_open_m=_percentile(sector(-90.0, 70.0), 0.85, range_max),
    )

