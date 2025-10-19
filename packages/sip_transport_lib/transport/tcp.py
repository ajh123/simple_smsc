"""Asyncio based TCP transport for SIP."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from .base import Connection, Transport
from ..messaging import SIPParseError, parse_sip_message

_MessageSplit = Tuple[Optional[bytes], bytes]


class TCPTransport(Transport):
    """Minimal TCP transport capable of accepting multiple clients."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5060,
        *,
        max_message_size: int = 65535,
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._loop = loop or asyncio.get_event_loop()
        self._max_message_size = max_message_size
        self._logger = logger or logging.getLogger(__name__)
        self._server: Optional[asyncio.AbstractServer] = None
        self._client_tasks: set[asyncio.Task[None]] = set()

    @property
    def endpoint(self) -> Tuple[str, int]:
        return self._host, self._port

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        self._logger.info("TCP transport listening on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        for task in list(self._client_tasks):
            task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        await asyncio.gather(*self._client_tasks, return_exceptions=True)
        self._client_tasks.clear()
        self._logger.info("TCP transport on %s:%s stopped", self._host, self._port)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        connection = Connection(
            transport=self,
            remote_address=_format_peer(peer),
            send_callable=lambda data: self._send(writer, data),
        )
        task = self._loop.create_task(self._serve_client(connection, reader, writer))
        self._client_tasks.add(task)
        task.add_done_callback(self._client_tasks.discard)

    async def _serve_client(
        self,
        connection: Connection,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        buffer = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buffer += data
                if len(buffer) > self._max_message_size:
                    self._logger.warning(
                        "Closing connection %s: message exceeds max size",
                        connection.remote_address,
                    )
                    break
                while True:
                    message_bytes, buffer = _split_sip_message(buffer)
                    if message_bytes is None:
                        break
                    try:
                        message = parse_sip_message(message_bytes)
                    except SIPParseError as exc:
                        self._logger.warning(
                            "Failed to parse SIP message from %s: %s",
                            connection.remote_address,
                            exc,
                        )
                        continue
                    await self.deliver(connection, message)
        except asyncio.CancelledError:
            self._logger.debug(
                "Connection task for %s cancelled", connection.remote_address
            )
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def _send(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        writer.write(data)
        await writer.drain()


def _split_sip_message(buffer: bytes) -> _MessageSplit:
    delimiter = b"\r\n\r\n"
    if delimiter not in buffer:
        return None, buffer
    header_end = buffer.index(delimiter) + len(delimiter)
    header_block = buffer[:header_end]
    content_length = _content_length_from_headers(header_block)
    total_length = header_end + content_length
    if len(buffer) < total_length:
        return None, buffer
    message_bytes = buffer[:total_length]
    remainder = buffer[total_length:]
    return message_bytes, remainder


def _content_length_from_headers(header_block: bytes) -> int:
    lines = header_block.decode("utf-8", errors="replace").split("\r\n")
    for line in lines:
        if line.lower().startswith("content-length:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def _format_peer(peer: object) -> str:
    if isinstance(peer, tuple) and len(peer) >= 2:
        return f"{peer[0]}:{peer[1]}"
    return str(peer)
