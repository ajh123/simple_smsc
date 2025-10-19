"""TP-Data-Coding-Scheme helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class DataCodingScheme:
    raw: int
    alphabet: str = field(init=False)
    message_class: Optional[int] = field(init=False)
    compressed: bool = field(init=False)

    def __post_init__(self) -> None:
        self.alphabet, self.message_class, self.compressed = self._decode(self.raw)

    @staticmethod
    def _decode(dcs: int) -> Tuple[str, Optional[int], bool]:
        top_bits = dcs & 0xC0
        if top_bits in (0x00, 0x40):
            compressed = bool(dcs & 0x20)
            alphabet_selector = (dcs >> 2) & 0x03
            alphabet = {0: "gsm7", 1: "8bit", 2: "ucs2"}.get(alphabet_selector, "gsm7")
            message_class = (dcs & 0x10 and dcs & 0x03) or None
            return alphabet, message_class, compressed
        if (dcs & 0xF0) == 0xE0:
            return "ucs2", None, False
        if (dcs & 0xF0) == 0xF0:
            return "gsm7", dcs & 0x03, False
        if (dcs & 0xF0) == 0xC0:
            return "8bit", None, False
        return "gsm7", None, False

    @classmethod
    def for_alphabet(
        cls,
        alphabet: str = "gsm7",
        message_class: Optional[int] = None,
        compressed: bool = False,
    ) -> "DataCodingScheme":
        base = {"gsm7": 0x00, "8bit": 0x04, "ucs2": 0x08}.get(alphabet)
        if base is None:
            raise ValueError(f"Unsupported alphabet {alphabet}")
        if compressed:
            base |= 0x20
        if message_class is not None:
            base |= 0x10 | (message_class & 0x03)
        return cls(base)


__all__ = ["DataCodingScheme"]
