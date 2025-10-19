"""Asyncio WebSocket transports for SIP."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Optional, TYPE_CHECKING

from .base import ClientTransport, Connection, Transport
from ..messaging import SIPParseError, parse_sip_message

try:
    import websockets
except ImportError as exc:  # pragma: no cover - optional dependency
    websockets = None  # type: ignore[assignment]
    _import_error = exc
else:
    _import_error = None

if TYPE_CHECKING:  # pragma: no cover - typing only
    from websockets.legacy.server import (
        WebSocketServerProtocol as _WebSocketServerProtocol,
    )

    WebSocketClient = _WebSocketServerProtocol
else:
    WebSocketClient = Any


class WebSocketServerTransport(Transport):
    """Transport that upgrades HTTP connections to WebSocket for SIP over WS."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5080,
        *,
        path: str = "/sip",
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._path = path
        self._loop = loop or asyncio.get_event_loop()
        self._logger = logger or logging.getLogger(__name__)
        self._server: Optional[websockets.server.Serve] = None  # type: ignore[attr-defined]
        self._client_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        if websockets is None:
            raise RuntimeError(
                "websockets package is required for WebSocketServerTransport"
            ) from _import_error
        self._server = await websockets.serve(self._handle_client, self._host, self._port, path=self._path)  # type: ignore[arg-type]
        self._logger.info(
            "WebSocket server transport listening on %s:%s%s",
            self._host,
            self._port,
            self._path,
        )

    async def stop(self) -> None:
        for task in list(self._client_tasks):
            task.cancel()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        await asyncio.gather(*self._client_tasks, return_exceptions=True)
        self._client_tasks.clear()
        self._logger.info(
            "WebSocket server transport on %s:%s%s stopped",
            self._host,
            self._port,
            self._path,
        )

    async def _handle_client(self, websocket: WebSocketClient, path: str) -> None:  # type: ignore[override]
        connection = Connection(
            transport=self,
            remote_address=_format_remote(websocket, path),
            send_callable=lambda data: self._send(websocket, data),
        )
        task = self._loop.create_task(self._serve_client(connection, websocket))
        self._client_tasks.add(task)
        task.add_done_callback(self._client_tasks.discard)
        await task

    async def _serve_client(
        self, connection: Connection, websocket: WebSocketClient
    ) -> None:
        try:
            async for payload in websocket:
                try:
                    message = parse_sip_message(payload)
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
                "WebSocket task for %s cancelled", connection.remote_address
            )
        except websockets.ConnectionClosed:  # type: ignore[attr-defined]
            self._logger.debug(
                "WebSocket connection %s closed", connection.remote_address
            )

    async def _send(self, websocket: WebSocketClient, data: bytes) -> None:
        await websocket.send(data)


def _format_remote(websocket: WebSocketClient, path: str) -> str:
    peer = getattr(websocket, "remote_address", None)
    if isinstance(peer, tuple) and len(peer) >= 2:
        return f"ws://{peer[0]}:{peer[1]}{path}"
    return f"ws://{peer}{path}"


class WebSocketClientTransport(ClientTransport):
    """WebSocket transport for SIP clients."""

    def __init__(
        self,
        host: str,
        port: int = 5080,
        *,
        path: str = "/sip",
        use_tls: bool = False,
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._path = path
        self._use_tls = use_tls
        self._loop = loop or asyncio.get_event_loop()
        self._logger = logger or logging.getLogger(__name__)
        self._websocket: Any | None = None
        self._reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self.is_connected:
            return
        if websockets is None:
            raise RuntimeError(
                "websockets package is required for WebSocketClientTransport"
            ) from _import_error
        scheme = "wss" if self._use_tls else "ws"
        uri = f"{scheme}://{self._host}:{self._port}{self._path}"
        self._websocket = await websockets.connect(uri)
        connection = Connection(
            transport=self,
            remote_address=uri,
            send_callable=self._send,
        )
        self._set_connection(connection)
        self._reader_task = self._loop.create_task(self._read_loop(connection))
        self._logger.info("WebSocket client transport connected to %s", uri)

    async def stop(self) -> None:
        should_wait = self._reader_task is not None
        if not self.is_connected and not should_wait:
            return
        reader_task = self._reader_task
        if reader_task is not None:
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader_task
        await self._shutdown(log=True)

    async def _read_loop(self, connection: Connection) -> None:
        assert self._websocket is not None
        cancelled = False
        try:
            async for payload in self._websocket:
                try:
                    message = parse_sip_message(payload)
                except SIPParseError as exc:
                    self._logger.warning(
                        "Failed to parse SIP message from %s: %s",
                        connection.remote_address,
                        exc,
                    )
                    continue
                await self.deliver(connection, message)
        except asyncio.CancelledError:
            cancelled = True
            self._logger.debug(
                "WebSocket client read loop for %s cancelled",
                connection.remote_address,
            )
        except websockets.ConnectionClosed as exc:  # type: ignore[attr-defined]
            self._logger.debug(
                "WebSocket connection %s closed (%s)", connection.remote_address, exc
            )
        finally:
            if not cancelled:
                await self._shutdown(log=False)

    async def _send(self, data: bytes) -> None:
        if self._websocket is None:
            raise RuntimeError("WebSocket client not connected")
        await self._websocket.send(data)

    async def _shutdown(self, *, log: bool) -> None:
        if self._websocket is None and not self.is_connected:
            return
        connection = self._connection
        websocket = self._websocket
        self._websocket = None
        self._reader_task = None
        self._set_connection(None)
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()
        if log:
            remote = (
                connection.remote_address
                if connection is not None
                else f"ws://{self._host}:{self._port}{self._path}"
            )
            self._logger.info("WebSocket client transport disconnected from %s", remote)
