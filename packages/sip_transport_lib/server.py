"""High level orchestration for SIP transports and message dispatch."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Iterable, List, Sequence

from .messaging import SIPMessage
from .transport.base import Connection, Transport

MessageHandler = Callable[[Connection, SIPMessage], Awaitable[None]]


class SIPServer:
    """Coordinates transports and user-defined message handlers."""

    def __init__(
        self,
        transports: Sequence[Transport],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not transports:
            raise ValueError("At least one transport must be provided")
        self._loop = loop or asyncio.get_event_loop()
        self._transports: List[Transport] = list(transports)
        self._handlers: List[MessageHandler] = []
        self._logger = logger or logging.getLogger(__name__)
        self._running = False
        for transport in self._transports:
            transport.bind(self._handle_incoming)

    def register_handler(self, handler: MessageHandler) -> None:
        """Attach a coroutine invoked for every inbound SIP message."""
        self._handlers.append(handler)

    async def start(self) -> None:
        if self._running:
            return
        self._logger.info(
            "Starting SIP server with %s transport(s)", len(self._transports)
        )
        for transport in self._transports:
            await transport.start()
        self._running = True

    async def stop(self) -> None:
        if not self._running:
            return
        self._logger.info("Stopping SIP server")
        for transport in self._transports:
            await transport.stop()
        self._running = False

    async def run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _handle_incoming(
        self, connection: Connection, message: SIPMessage
    ) -> None:
        if not self._handlers:
            self._logger.debug(
                "No handlers registered; dropping message from %s",
                connection.remote_address,
            )
            return
        for handler in list(self._handlers):
            try:
                await handler(connection, message)
            except Exception as exc:  # pragma: no cover - user code
                self._logger.exception("Handler %s failed: %s", handler, exc)

    def add_transport(self, transport: Transport) -> None:
        if self._running:
            raise RuntimeError("Cannot add transports while server is running")
        transport.bind(self._handle_incoming)
        self._transports.append(transport)

    @property
    def transports(self) -> Iterable[Transport]:
        return tuple(self._transports)
