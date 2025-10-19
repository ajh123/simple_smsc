"""High-level SIP client orchestration."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Iterable, List

from .messaging import SIPMessage
from .transport.base import ClientTransport, Connection, PayloadInput

MessageHandler = Callable[[Connection, SIPMessage], Awaitable[None]]


class SIPClient:
    """Coordinates a client transport and user-provided message handlers."""

    def __init__(
        self,
        transport: ClientTransport,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._transport = transport
        self._transport.bind(self._handle_incoming)
        self._handlers: List[MessageHandler] = []
        self._logger = logger or logging.getLogger(__name__)

    async def connect(self) -> Connection:
        await self._transport.start()
        return self._transport.connection

    async def disconnect(self) -> None:
        await self._transport.stop()

    async def send(self, message: PayloadInput) -> None:
        await self._transport.send(message)

    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    @property
    def transport(self) -> ClientTransport:
        return self._transport

    @property
    def connection(self) -> Connection:
        return self._transport.connection

    @property
    def connected(self) -> bool:
        return self._transport.is_connected

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
                self._logger.exception("Client handler %s failed: %s", handler, exc)

    @property
    def handlers(self) -> Iterable[MessageHandler]:
        return tuple(self._handlers)
