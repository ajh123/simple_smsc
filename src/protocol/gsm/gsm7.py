"""GSM 03.38 7-bit alphabet utilities."""

from __future__ import annotations

from typing import Iterable, List

GSM7_BASIC_TABLE = (
    "@\u00a3$\u00a5\u00e8\u00e9\u00f9\u00ec\u00f2\u00c7\n\u00d8\u00f8\r\u00c5\u00e5\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e"
    "\x1b\u00c6\u00e6\u00df\u00c9 \u0021\"#\u00a4%&'()*+,-./0123456789:;<=>?\u00a1"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7\u00bfabcdefghijklmnopqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0"
)

GSM7_EXTENDED_TABLE = {
    0x0A: "\u000c",
    0x14: "^",
    0x28: "{",
    0x29: "}",
    0x2F: "\\",
    0x3C: "[",
    0x3D: "~",
    0x3E: "]",
    0x40: "|",
    0x65: "\u20ac",
}

GSM7_BASIC_MAP = {ch: idx for idx, ch in enumerate(GSM7_BASIC_TABLE)}
GSM7_EXTENDED_REVERSE = {v: k for k, v in GSM7_EXTENDED_TABLE.items()}


def encode_gsm7_text(text: str) -> List[int]:
    """Return a list of septet values representing *text* in GSM 7-bit alphabet."""

    septets: List[int] = []
    for char in text:
        if char in GSM7_BASIC_MAP:
            septets.append(GSM7_BASIC_MAP[char])
        elif char in GSM7_EXTENDED_REVERSE:
            septets.append(0x1B)
            septets.append(GSM7_EXTENDED_REVERSE[char])
        else:
            raise ValueError(f"Character {char!r} not supported in GSM 7-bit alphabet")
    return septets


def decode_gsm7_text(septets: Iterable[int]) -> str:
    """Decode a sequence of septets into text using the GSM 7-bit alphabet."""

    chars: List[str] = []
    iterator = iter(septets)
    for value in iterator:
        if value == 0x1B:
            ext_val = next(iterator, None)
            if ext_val is None:
                break
            chars.append(GSM7_EXTENDED_TABLE.get(ext_val, " "))
        else:
            if value >= len(GSM7_BASIC_TABLE):
                chars.append(" ")
            else:
                chars.append(GSM7_BASIC_TABLE[value])
    return "".join(chars)


def septets_to_bits(septets: Iterable[int]) -> List[int]:
    """Convert septets to a least-significant-bit-first bit stream."""

    bits: List[int] = []
    for septet in septets:
        for bit in range(7):
            bits.append((septet >> bit) & 0x01)
    return bits


def bits_to_septets(bits: List[int]) -> List[int]:
    """Convert a bit stream back into septet values."""

    septets: List[int] = []
    for i in range(0, len(bits), 7):
        value = 0
        segment = bits[i : i + 7]
        for idx, bit in enumerate(segment):
            value |= (bit & 0x01) << idx
        septets.append(value)
    return septets


def bytes_to_bits_lsb(data: bytes) -> List[int]:
    """Return a least-significant-bit-first bit stream for *data*."""

    bits: List[int] = []
    for byte in data:
        for bit in range(8):
            bits.append((byte >> bit) & 0x01)
    return bits


def bits_to_bytes(bits: List[int]) -> bytes:
    """Pack a bit stream (lsb-first) into bytes."""

    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit_index in range(8):
            if i + bit_index >= len(bits):
                break
            byte |= (bits[i + bit_index] & 0x01) << bit_index
        out.append(byte)
    return bytes(out)


__all__ = [
    "GSM7_BASIC_TABLE",
    "GSM7_EXTENDED_TABLE",
    "GSM7_BASIC_MAP",
    "GSM7_EXTENDED_REVERSE",
    "encode_gsm7_text",
    "decode_gsm7_text",
    "septets_to_bits",
    "bits_to_septets",
    "bytes_to_bits_lsb",
    "bits_to_bytes",
]
