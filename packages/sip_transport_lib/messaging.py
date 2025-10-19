"""High-level SIP message helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple

CRLF = "\r\n"


class SIPParseError(ValueError):
    """Raised when an incoming datagram cannot be parsed as SIP."""


def _normalize_header_name(name: str) -> str:
    parts = name.split("-")
    return "-".join(part[:1].upper() + part[1:].lower() for part in parts if part)


@dataclass
class SIPMessage:
    start_line: str
    headers: Dict[str, str]
    body: str = ""

    def to_string(self) -> str:
        header_lines = [
            f"{key}: {value}" for key, value in self._with_content_length().items()
        ]
        parts = [self.start_line, *header_lines, ""]
        if self.body:
            parts.append(self.body)
        return CRLF.join(parts)

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    def _with_content_length(self) -> Dict[str, str]:
        headers = {_normalize_header_name(k): v for k, v in self.headers.items()}
        length = len(self.body.encode("utf-8"))
        headers["Content-Length"] = str(length)
        return headers

    @property
    def is_request(self) -> bool:
        return not self.start_line.startswith("SIP/")

    @property
    def is_response(self) -> bool:
        return self.start_line.startswith("SIP/")

    def get_header(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(_normalize_header_name(name), default)

    def set_header(self, name: str, value: str) -> None:
        self.headers[_normalize_header_name(name)] = value

    def remove_header(self, name: str) -> None:
        self.headers.pop(_normalize_header_name(name), None)


@dataclass
class SIPRequest(SIPMessage):
    method: str = ""
    uri: str = ""
    version: str = "SIP/2.0"

    @classmethod
    def build(
        cls,
        method: str,
        uri: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: str = "",
    ) -> "SIPRequest":
        headers_dict = {
            _normalize_header_name(k): v for k, v in (headers or {}).items()
        }
        start_line = f"{method} {uri} SIP/2.0"
        return cls(
            start_line=start_line,
            headers=headers_dict,
            body=body,
            method=method,
            uri=uri,
        )


@dataclass
class SIPResponse(SIPMessage):
    status_code: int = 200
    reason: str = "OK"
    version: str = "SIP/2.0"

    @classmethod
    def build(
        cls,
        status_code: int,
        reason: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: str = "",
    ) -> "SIPResponse":
        headers_dict = {
            _normalize_header_name(k): v for k, v in (headers or {}).items()
        }
        start_line = f"SIP/2.0 {status_code} {reason}"
        return cls(
            start_line=start_line,
            headers=headers_dict,
            body=body,
            status_code=status_code,
            reason=reason,
        )


def parse_sip_message(data: bytes | str | bytearray | memoryview) -> SIPMessage:
    if isinstance(data, memoryview):
        text = bytes(data).decode("utf-8", errors="replace")
    elif isinstance(data, (bytes, bytearray)):
        text = data.decode("utf-8", errors="replace")
    else:
        text = str(data)
    if CRLF * 2 not in text:
        raise SIPParseError("SIP message missing header terminator")
    header_section, body = text.split(CRLF * 2, 1)
    header_lines = [line.strip() for line in header_section.split(CRLF) if line.strip()]
    if not header_lines:
        raise SIPParseError("Empty SIP message")
    start_line = header_lines[0]
    headers = _parse_headers(header_lines[1:])
    if start_line.upper().startswith("SIP/"):
        version, status_code, reason = _parse_status_line(start_line)
        return SIPResponse(
            start_line=start_line,
            headers=headers,
            body=body,
            status_code=status_code,
            reason=reason,
            version=version,
        )
    method, uri, version = _parse_request_line(start_line)
    return SIPRequest(
        start_line=start_line,
        headers=headers,
        body=body,
        method=method,
        uri=uri,
        version=version,
    )


def _parse_headers(lines: Iterable[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    current_name: str | None = None
    for line in lines:
        if line.startswith((" ", "\t")) and current_name:
            headers[current_name] += " " + line.strip()
            continue
        if ":" not in line:
            raise SIPParseError(f"Malformed header line: {line}")
        name, value = line.split(":", 1)
        current_name = _normalize_header_name(name.strip())
        headers[current_name] = value.strip()
    return headers


def _parse_request_line(line: str) -> Tuple[str, str, str]:
    try:
        method, uri, version = line.split(" ", 2)
    except ValueError as exc:
        raise SIPParseError(f"Invalid request line: {line}") from exc
    return method, uri, version


def _parse_status_line(line: str) -> Tuple[str, int, str]:
    parts = line.split(" ")
    if len(parts) < 3:
        raise SIPParseError(f"Invalid status line: {line}")
    version, code, reason = parts[0], parts[1], " ".join(parts[2:])
    try:
        status_code = int(code)
    except ValueError as exc:
        raise SIPParseError(f"Invalid status code: {code}") from exc
    return version, status_code, reason
