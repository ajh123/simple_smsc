"""Timestamp encoding utilities for SMS PDUs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List


def swap_nibbles(value: int) -> int:
    return ((value & 0x0F) << 4) | ((value >> 4) & 0x0F)


def semi_octet_to_int(byte: int) -> int:
    return (byte & 0x0F) * 10 + ((byte >> 4) & 0x0F)


def encode_timestamp(dt: datetime) -> bytes:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    offset_delta = dt.utcoffset() or timedelta()
    offset_minutes = int(offset_delta.total_seconds() // 60)
    quarter_hours = min(63, abs(offset_minutes) // 15)
    digits = [
        dt.year % 100,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second,
    ]
    out = bytearray()
    for value in digits:
        if not 0 <= value <= 99:
            raise ValueError("Timestamp component out of range")
        octet = ((value % 10) << 4) | (value // 10)
        out.append(swap_nibbles(octet))
    tz_octet = ((quarter_hours % 10) << 4) | (quarter_hours // 10)
    tz = swap_nibbles(tz_octet)
    if offset_minutes < 0:
        tz |= 0x08
    out.append(tz)
    return bytes(out)


def decode_timestamp(data: bytes) -> datetime:
    if len(data) != 7:
        raise ValueError("Timestamp must be exactly 7 octets")
    values: List[int] = []
    for i in range(6):
        values.append(semi_octet_to_int(data[i]))
    tz_byte = data[6]
    sign = -1 if tz_byte & 0x08 else 1
    tz_quarters = semi_octet_to_int(tz_byte & 0xF7)
    offset = timezone(sign * timedelta(minutes=tz_quarters * 15))
    year = values[0]
    year += 2000 if year < 70 else 1900
    return datetime(
        year=year,
        month=max(1, min(values[1], 12)),
        day=max(1, min(values[2], 31)),
        hour=min(values[3], 23),
        minute=min(values[4], 59),
        second=min(values[5], 59),
        tzinfo=offset,
    )


__all__ = [
    "encode_timestamp",
    "decode_timestamp",
    "swap_nibbles",
    "semi_octet_to_int",
]
