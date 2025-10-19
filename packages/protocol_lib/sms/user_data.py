"""User data handling for SMS PDUs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
import math

from ..gsm import (
    bytes_to_bits_lsb,
    bits_to_bytes,
    bits_to_septets,
    decode_gsm7_text,
    encode_gsm7_text,
    septets_to_bits,
)
from .dcs import DataCodingScheme


@dataclass
class UserData:
    payload: Union[str, bytes]
    encoding: str = "gsm7"
    header: Optional[bytes] = None


def encode_user_data(user_data: UserData, dcs: DataCodingScheme) -> Tuple[int, bytes]:
    encoding = (user_data.encoding or dcs.alphabet).lower()
    header = b""
    if user_data.header is not None:
        if len(user_data.header) > 140:
            raise ValueError("User data header too large")
        header = bytes([len(user_data.header)]) + user_data.header
    if encoding in ("gsm7", "7bit"):
        if not isinstance(user_data.payload, str):
            raise TypeError("GSM 7-bit user data expects text input")
        septets = encode_gsm7_text(user_data.payload)
        bits: List[int] = []
        if header:
            bits.extend(bytes_to_bits_lsb(header))
        bits.extend(septets_to_bits(septets))
        ud_bytes = bits_to_bytes(bits)
        header_septets = ((len(header) * 8) + 6) // 7
        udl = len(septets) + header_septets
        if udl > 160:
            raise ValueError("GSM 7-bit payload exceeds 160 septets")
        if len(ud_bytes) > 140:
            raise ValueError("GSM 7-bit payload exceeds 140 octets")
        return udl, ud_bytes
    if encoding == "8bit":
        payload = (
            user_data.payload
            if isinstance(user_data.payload, (bytes, bytearray))
            else str(user_data.payload).encode("latin-1")
        )
        ud_bytes = header + bytes(payload)
        if len(ud_bytes) > 140:
            raise ValueError("8-bit payload exceeds 140 octets")
        return len(ud_bytes), ud_bytes
    if encoding == "ucs2":
        payload_bytes = (
            user_data.payload.encode("utf-16-be")
            if isinstance(user_data.payload, str)
            else bytes(user_data.payload)
        )
        ud_bytes = header + payload_bytes
        if len(ud_bytes) > 140:
            raise ValueError("UCS2 payload exceeds maximum length")
        return len(ud_bytes), ud_bytes
    raise ValueError(f"Unsupported user data encoding {encoding}")


def decode_user_data(
    ud_bytes: bytes, udl: int, dcs: DataCodingScheme, udhi: bool
) -> UserData:
    encoding = dcs.alphabet
    header: Optional[bytes] = None
    payload_bytes = ud_bytes
    if udhi:
        if not ud_bytes:
            raise ValueError("UDHI set but user data absent")
        udhl = ud_bytes[0]
        if len(ud_bytes) < 1 + udhl:
            raise ValueError("UD header length exceeds available user data")
        header = ud_bytes[1 : 1 + udhl]
        if udhl == 0:
            header = None
        payload_bytes = ud_bytes[1 + udhl :]
    if encoding == "gsm7":
        bits = bytes_to_bits_lsb(ud_bytes)
        header_bits = 0
        if udhi:
            header_bits = (len(header or b"") + 1) * 8
        payload_septets = max(udl - ((header_bits + 6) // 7), 0)
        payload_bits_start = header_bits
        payload_bits_end = payload_bits_start + payload_septets * 7
        payload_bits = bits[payload_bits_start:payload_bits_end]
        if len(payload_bits) != payload_septets * 7:
            raise ValueError("Insufficient GSM 7-bit payload bits")
        septets = bits_to_septets(payload_bits)
        text = decode_gsm7_text(septets)
        return UserData(payload=text, encoding="gsm7", header=header)
    if encoding == "8bit":
        return UserData(payload=bytes(payload_bytes), encoding="8bit", header=header)
    if encoding == "ucs2":
        text = payload_bytes.decode("utf-16-be") if payload_bytes else ""
        return UserData(payload=text, encoding="ucs2", header=header)
    return UserData(payload=bytes(payload_bytes), encoding="8bit", header=header)


def extract_user_data_bytes(
    data: bytes, offset: int, udl: int, alphabet: str, udhi: bool
) -> Tuple[bytes, int]:
    if alphabet == "gsm7":
        if udhi:
            if offset >= len(data):
                raise ValueError("Expected UDHL byte but reached end of TPDU")
            udhl = data[offset]
            header_bits = (udhl + 1) * 8
            header_septets = (header_bits + 6) // 7
            payload_septets = max(udl - header_septets, 0)
            total_bits = header_bits + payload_septets * 7
            byte_len = math.ceil(total_bits / 8)
        else:
            byte_len = math.ceil(udl * 7 / 8)
    else:
        byte_len = udl
    if byte_len < 0:
        byte_len = 0
    chunk = data[offset : offset + byte_len]
    return bytes(chunk), offset + byte_len


__all__ = [
    "UserData",
    "encode_user_data",
    "decode_user_data",
    "extract_user_data_bytes",
]
