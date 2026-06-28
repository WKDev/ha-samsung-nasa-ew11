# EW11 TCP 소켓 비동기 클라이언트: 수신 패킷 디코딩 + 명령 재전송(ACK 대체) 처리
"""Async TCP client to an EW11 RS485<->TCP bridge carrying the Samsung NASA bus."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from . import nasa
from .const import RECONNECT_INTERVAL, SEND_MAX_RETRIES, SEND_RETRY_INTERVAL

_LOGGER = logging.getLogger(__name__)

PacketHandler = Callable[[nasa.Packet], Awaitable[None]]


class _Pending:
    """A control command awaiting acknowledgment from its target address."""

    def __init__(self, target: str, raw: bytes) -> None:
        self.target = target  # da.to_string()
        self.raw = raw
        self.retries = 0


class SamsungNasaClient:
    """Maintains the TCP connection and the NASA packet stream."""

    def __init__(self, host: str, port: int, on_packet: PacketHandler) -> None:
        self._host = host
        self._port = port
        self._on_packet = on_packet
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._buffer = bytearray()
        self._pending: dict[str, _Pending] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._connection_loop()))
        self._tasks.append(asyncio.create_task(self._retry_loop()))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        await self._close_writer()

    async def _close_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001 - closing best-effort
                pass
            self._writer = None
        self._connected.clear()

    async def _connection_loop(self) -> None:
        while self._running:
            try:
                _LOGGER.debug("Connecting to EW11 %s:%s", self._host, self._port)
                self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
                self._buffer.clear()
                self._connected.set()
                _LOGGER.info("Connected to EW11 %s:%s", self._host, self._port)
                await self._read_loop()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - reconnect on any socket error
                _LOGGER.warning("EW11 connection error: %s", err)
            await self._close_writer()
            if self._running:
                await asyncio.sleep(RECONNECT_INTERVAL)

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while self._running:
            chunk = await self._reader.read(512)
            if not chunk:
                raise ConnectionError("EW11 closed the connection")
            self._buffer.extend(chunk)
            for packet in nasa.feed(self._buffer):
                self._handle_ack(packet)
                try:
                    await self._on_packet(packet)
                except Exception:  # noqa: BLE001 - one bad packet must not kill the loop
                    _LOGGER.exception("Error handling NASA packet")

    def _handle_ack(self, packet: nasa.Packet) -> None:
        # notify-as-ack: any reply originating from a pending command's target
        # counts as acknowledgment, so we stop resending (and the beeping).
        source = packet.sa.to_string()
        if self._pending.pop(source, None) is not None:
            _LOGGER.debug("Command to %s acknowledged by reply", source)

    async def _retry_loop(self) -> None:
        while self._running:
            await asyncio.sleep(SEND_RETRY_INTERVAL)
            if not self.connected or not self._pending:
                continue
            for target, pending in list(self._pending.items()):
                if pending.retries >= SEND_MAX_RETRIES:
                    _LOGGER.warning("Command to %s gave up after %d retries", target, pending.retries)
                    self._pending.pop(target, None)
                    continue
                pending.retries += 1
                _LOGGER.debug("Resending command to %s (try %d)", target, pending.retries)
                await self._write(pending.raw)

    async def _write(self, raw: bytes) -> None:
        if self._writer is None:
            _LOGGER.warning("Cannot send, not connected")
            return
        self._writer.write(raw)
        await self._writer.drain()

    async def send_request(self, da: nasa.Address, messages: list[nasa.MessageSet]) -> None:
        """Send a Request packet to *da* and register it for retry until acked."""
        if not messages:
            return
        packet = nasa.Packet.create_partial(da, nasa.DataType.Request, _next_packet_number())
        packet.messages.extend(messages)
        raw = packet.encode()
        self._pending[da.to_string()] = _Pending(da.to_string(), raw)
        await self._write(raw)


_packet_counter = 0


def _next_packet_number() -> int:
    global _packet_counter
    _packet_counter = (_packet_counter % 255) + 1  # 1..255, skip 0
    return _packet_counter
