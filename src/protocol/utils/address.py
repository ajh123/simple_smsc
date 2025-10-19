"""Address handling helpers for SMS PDUs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import math

_BCD_SYMBOLS = {
    "0": 0x0,
    "1": 0x1,
    "2": 0x2,
    "3": 0x3,
    "4": 0x4,
    "5": 0x5,
    "6": 0x6,
    "7": 0x7,
    "8": 0x8,
    "9": 0x9,
    "*": 0xA,
    "#": 0xB,
    "A": 0xC,
    "a": 0xC,
    "B": 0xD,
    "b": 0xD,
    "C": 0xE,
    "c": 0xE,
    "F": 0xF,
    "f": 0xF,
}

_BCD_DECODE = {
    0x0: "0",
    0x1: "1",
    0x2: "2",
    0x3: "3",
    0x4: "4",
    0x5: "5",
    0x6: "6",
    0x7: "7",
    0x8: "8",
    0x9: "9",
    0xA: "*",
    0xB: "#",
    0xC: "A",
    0xD: "B",
    0xE: "C",
    0xF: "F",
}


@dataclass
class Address:
    digits: str
    type_of_number: int = 1
    numbering_plan: int = 1

    @staticmethod
    def from_string(number: str) -> "Address":
        digits = number.lstrip("+")
        ton = 1 if number.startswith("+") else 0
        return Address(digits=digits, type_of_number=ton, numbering_plan=1)

    def requires_international_prefix(self) -> bool:
        return self.type_of_number == 1


def encode_bcd_digits(digits: str) -> bytes:
    clean = digits.replace(" ", "")
    if not clean:
        return b""
    values: List[int] = []
    for ch in clean:
        if ch not in _BCD_SYMBOLS:
            upper = ch.upper()
            if upper not in _BCD_SYMBOLS:
                raise ValueError(f"Unsupported BCD digit {ch!r}")
            values.append(_BCD_SYMBOLS[upper])
        else:
            values.append(_BCD_SYMBOLS[ch])
    if len(values) % 2:
        values.append(0x0F)
    out = bytearray()
    for i in range(0, len(values), 2):
        low = values[i]
        high = values[i + 1]
        out.append((low & 0x0F) | ((high & 0x0F) << 4))
    return bytes(out)


def decode_bcd_digits(data: bytes, digits_len: int) -> str:
    chars: List[str] = []
    for byte in data:
        low = byte & 0x0F
        high = (byte >> 4) & 0x0F
        chars.append(_BCD_DECODE.get(low, "F"))
        chars.append(_BCD_DECODE.get(high, "F"))
    number = "".join(chars)[:digits_len]
    return number.replace("F", "")


def encode_address(address: Address) -> bytes:
    digits = address.digits
    toa = (
        0x80 | ((address.type_of_number & 0x07) << 4) | (address.numbering_plan & 0x0F)
    )
    encoded_digits = encode_bcd_digits(digits)
    return bytes([len(digits), toa]) + encoded_digits


def decode_address(data: bytes, offset: int) -> Tuple[Address, int]:
    length = data[offset]
    toa = data[offset + 1]
    digits_octets = math.ceil(length / 2)
    digits = decode_bcd_digits(data[offset + 2 : offset + 2 + digits_octets], length)
    addr = Address(
        digits=digits, type_of_number=((toa >> 4) & 0x07), numbering_plan=toa & 0x0F
    )
    return addr, offset + 2 + digits_octets


def encode_smsc(address: Optional[Address]) -> bytes:
    if address is None:
        return b"\x00"
    body = bytearray()
    toa = (
        0x80 | ((address.type_of_number & 0x07) << 4) | (address.numbering_plan & 0x0F)
    )
    body.append(toa)
    body.extend(encode_bcd_digits(address.digits))
    return bytes([len(body)]) + bytes(body)


def decode_smsc(data: bytes, offset: int) -> Tuple[Optional[Address], int]:
    length = data[offset]
    offset += 1
    if length == 0:
        return None, offset
    body = data[offset : offset + length]
    if not body:
        raise ValueError("Invalid SMSC section")
    toa = body[0]
    digits = decode_bcd_digits(body[1:], (len(body) - 1) * 2)
    ton = (toa >> 4) & 0x07
    npi = toa & 0x0F
    addr = Address(digits=digits, type_of_number=ton, numbering_plan=npi)
    return addr, offset + length


__all__ = [
    "Address",
    "encode_bcd_digits",
    "decode_bcd_digits",
    "encode_address",
    "decode_address",
    "encode_smsc",
    "decode_smsc",
]
