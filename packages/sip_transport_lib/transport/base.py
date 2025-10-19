"""Transport primitives used by the SIP server runtime."""

from __future__ import annotations

import abc
from typing import Awaitable, Callable, Optional, Union, cast

from ..messaging import SIPMessage

MessageCallback = Callable[["Connection", SIPMessage], Awaitable[None]]
PayloadInput = Union[SIPMessage, str, bytes, bytearray, memoryview]


def _coerce_to_bytes(data: PayloadInput) -> bytes:
    if isinstance(data, SIPMessage):
        message = cast(SIPMessage, data)
        return message.to_bytes()
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    return str(data).encode("utf-8")


class Connection:
    """Wraps a transport-specific connection and exposes a uniform API."""

    def __init__(
        self,
        *,
        transport: "Transport",
        remote_address: str,
        send_callable: Callable[[bytes], Awaitable[None]],
    ):
        self._transport = transport
        self._remote_address = remote_address
        self._send = send_callable

    @property
    def transport(self) -> "Transport":
        return self._transport

    @property
    def remote_address(self) -> str:
        return self._remote_address

    async def send(self, message: PayloadInput) -> None:
        await self._send(_coerce_to_bytes(message))


class Transport(abc.ABC):
    """Abstract base class for concrete SIP transports."""

    def __init__(self) -> None:
        self._callback: Optional[MessageCallback] = None

    def bind(self, callback: MessageCallback) -> None:
        """Register the coroutine invoked when a message arrives."""
        self._callback = callback

    @property
    def callback(self) -> MessageCallback:
        if self._callback is None:
            raise RuntimeError("Transport callback has not been bound")
        return self._callback

    @abc.abstractmethod
    async def start(self) -> None:
        """Start accepting connections."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release resources."""

    async def deliver(self, connection: Connection, message: SIPMessage) -> None:
        await self.callback(connection, message)


class ClientTransport(Transport):
    """Base class shared by client-side transport implementations."""

    def __init__(self) -> None:
        super().__init__()
        self._connection: Connection | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def connection(self) -> Connection:
        if self._connection is None:
            raise RuntimeError("Client transport not connected")
        return self._connection

    async def send(self, message: PayloadInput) -> None:
        await self.connection.send(message)

    def _set_connection(self, connection: Connection | None) -> None:
        self._connection = connection
