"""Validity period encoding helpers."""

from __future__ import annotations

from datetime import timedelta


def encode_relative_validity(delta: timedelta) -> int:
    minutes = int(max(delta.total_seconds(), 0) // 60)
    if minutes <= 12 * 60:
        units = max(1, (minutes + 4) // 5)
        return min(units, 144) - 1
    if minutes <= 24 * 60:
        half_hours = max(1, (minutes - 12 * 60 + 29) // 30)
        return min(half_hours, 24) + 143
    days = (minutes + 1439) // 1440
    if minutes <= 30 * 24 * 60:
        days = max(2, min(days, 30))
        return days + 166
    weeks = (minutes + 10079) // (7 * 24 * 60)
    weeks = max(5, min(weeks, 63))
    return weeks + 192


def decode_relative_validity(value: int) -> timedelta:
    if value <= 143:
        minutes = (value + 1) * 5
    elif value <= 167:
        minutes = 12 * 60 + (value - 143) * 30
    elif value <= 196:
        minutes = (value - 166) * 24 * 60
    else:
        minutes = (value - 192) * 7 * 24 * 60
    return timedelta(minutes=minutes)


__all__ = ["encode_relative_validity", "decode_relative_validity"]
