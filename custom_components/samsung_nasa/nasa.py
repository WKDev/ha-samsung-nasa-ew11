# 삼성 NASA RS485 프로토콜 코덱 (esphome_samsung_hvac_bus C++ 포팅, HA 비의존 순수 파이썬)
"""Samsung NASA protocol codec.

Ported from esphome_samsung_hvac_bus/components/samsung_ac/protocol_nasa.cpp.
Pure-python and framework independent so it can be unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

# ---------------------------------------------------------------------------
# Enums (mirrors protocol_nasa.h)
# ---------------------------------------------------------------------------


class AddressClass(IntEnum):
    Outdoor = 0x10
    HTU = 0x11
    Indoor = 0x20
    ERV = 0x30
    Diffuser = 0x35
    MCU = 0x38
    RMC = 0x40
    WiredRemote = 0x50
    PIM = 0x58
    SIM = 0x59
    Peak = 0x5A
    PowerDivider = 0x5B
    OnOffController = 0x60
    WiFiKit = 0x62
    CentralController = 0x65
    DMS = 0x6A
    JIGTester = 0x80
    BroadcastSelfLayer = 0xB0
    BroadcastControlLayer = 0xB1
    BroadcastSetLayer = 0xB2
    BroadcastControlAndSetLayer = 0xB3
    BroadcastModuleLayer = 0xB4
    BroadcastCSM = 0xB7
    BroadcastLocalLayer = 0xB8
    BroadcastCSML = 0xBF
    Undefined = 0xFF


class PacketType(IntEnum):
    StandBy = 0
    Normal = 1
    Gathering = 2
    Install = 3
    Download = 4


class DataType(IntEnum):
    Undefined = 0
    Read = 1
    Write = 2
    Request = 3
    Notification = 4
    Response = 5
    Ack = 6
    Nack = 7


class MessageSetType(IntEnum):
    Enum = 0
    Variable = 1
    LongVariable = 2
    Structure = 3


class Mode(IntEnum):
    Unknown = -1
    Auto = 0
    Cool = 1
    Dry = 2
    Fan = 3
    Heat = 4


class FanMode(IntEnum):
    Unknown = -1
    Auto = 0
    Low = 1
    Mid = 2
    High = 3
    Turbo = 4
    Off = 5


# Message numbers we actively map (subset of protocol_nasa.h MessageNumber enum)
class MessageNumber(IntEnum):
    ENUM_in_operation_power = 0x4000
    ENUM_in_operation_mode = 0x4001
    ENUM_in_fan_mode = 0x4006
    ENUM_in_fan_mode_real = 0x4007
    ENUM_in_louver_hl_swing = 0x4011
    ENUM_in_louver_lr_swing = 0x407E
    ENUM_in_state_humidity_percent = 0x4038
    ENUM_in_alt_mode = 0x4060
    VAR_in_temp_target_f = 0x4201
    VAR_in_temp_room_f = 0x4204
    VAR_in_temp_eva_in_f = 0x4205
    VAR_in_temp_eva_out_f = 0x4206
    VAR_out_sensor_airout = 0x8204
    VAR_OUT_SENSOR_CT1 = 0x8217
    VAR_out_error_code = 0x8235
    LVAR_OUT_CONTROL_WATTMETER_1W_1MIN_SUM = 0x8413
    LVAR_OUT_CONTROL_WATTMETER_ALL_UNIT_ACCUM = 0x8414
    LVAR_NM_OUT_SENSOR_VOLTAGE = 0x24FC
    ENUM_out_operation_odu_mode = 0x8001
    ENUM_out_operation_heatcool = 0x8003


# ---------------------------------------------------------------------------
# CRC16 (protocol_nasa.cpp::crc16) — poly 0x1021, init 0
# ---------------------------------------------------------------------------


def crc16(data: bytes, start_index: int, length: int) -> int:
    crc = 0
    for index in range(start_index, start_index + length):
        crc ^= data[index] << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


@dataclass
class Address:
    klass: int = AddressClass.Undefined
    channel: int = 0
    address: int = 0

    @staticmethod
    def parse(text: str) -> "Address":
        # NASA address format MUST be "kk.cc.aa" (hex), e.g. "20.00.00"
        if "." not in text:
            return Address(AddressClass.Undefined, 0, 0)
        klass_s, channel_s, address_s = text.split(".")
        return Address(int(klass_s, 16), int(channel_s, 16), int(address_s, 16))

    @staticmethod
    def my_address() -> "Address":
        # Controller identity = JIGTester, channel 0xFF, address 0
        return Address(AddressClass.JIGTester, 0xFF, 0x00)

    @classmethod
    def decode(cls, data: bytes, index: int) -> "Address":
        return cls(data[index], data[index + 1], data[index + 2])

    def encode(self) -> bytes:
        return bytes((self.klass & 0xFF, self.channel & 0xFF, self.address & 0xFF))

    def to_string(self) -> str:
        return "%02x.%02x.%02x" % (self.klass & 0xFF, self.channel & 0xFF, self.address & 0xFF)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@dataclass
class Command:
    packet_information: bool = True
    protocol_version: int = 2
    retry_count: int = 0
    packet_type: int = PacketType.StandBy
    data_type: int = DataType.Undefined
    packet_number: int = 0

    @classmethod
    def decode(cls, data: bytes, index: int) -> "Command":
        b0 = data[index]
        b1 = data[index + 1]
        return cls(
            packet_information=((b0 & 0x80) >> 7) == 1,
            protocol_version=(b0 & 0x60) >> 5,
            retry_count=(b0 & 0x18) >> 3,
            packet_type=(b1 & 0xF0) >> 4,
            data_type=b1 & 0x0F,
            packet_number=data[index + 2],
        )

    def encode(self) -> bytes:
        b0 = ((1 if self.packet_information else 0) << 7) + (self.protocol_version << 5) + (self.retry_count << 3)
        b1 = (int(self.packet_type) << 4) + int(self.data_type)
        return bytes((b0 & 0xFF, b1 & 0xFF, self.packet_number & 0xFF))


# ---------------------------------------------------------------------------
# MessageSet
# ---------------------------------------------------------------------------


@dataclass
class MessageSet:
    message_number: int
    type: int = MessageSetType.Enum
    value: int = 0
    structure: bytes = b""
    size: int = 2

    def __post_init__(self) -> None:
        # type derived from message number bits 9-10 (mask 0x600)
        self.type = MessageSetType((self.message_number & 0x600) >> 9)

    @staticmethod
    def decode(data: bytes, index: int, capacity: int) -> "MessageSet":
        number = data[index] * 256 + data[index + 1]
        msg = MessageSet(number)
        if msg.type == MessageSetType.Enum:
            msg.value = data[index + 2]
            msg.size = 3
        elif msg.type == MessageSetType.Variable:
            msg.value = (data[index + 2] << 8) | data[index + 3]
            msg.size = 4
        elif msg.type == MessageSetType.LongVariable:
            msg.value = (
                (data[index + 2] << 24)
                | (data[index + 3] << 16)
                | (data[index + 4] << 8)
                | data[index + 5]
            )
            msg.size = 6
        elif msg.type == MessageSetType.Structure:
            # structure messages can only have one message
            msg.size = len(data) - index - 3  # 3 = end bytes
            msg.structure = bytes(data[index + 2 : index + 2 + (msg.size - 2)])
        return msg

    def encode(self) -> bytes:
        out = bytearray()
        out.append((self.message_number >> 8) & 0xFF)
        out.append(self.message_number & 0xFF)
        if self.type == MessageSetType.Enum:
            out.append(self.value & 0xFF)
        elif self.type == MessageSetType.Variable:
            out.append((self.value >> 8) & 0xFF)
            out.append(self.value & 0xFF)
        elif self.type == MessageSetType.LongVariable:
            v = self.value & 0xFFFFFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
            out.append((v >> 16) & 0xFF)
            out.append((v >> 24) & 0xFF)
        elif self.type == MessageSetType.Structure:
            out.extend(self.structure)
        return bytes(out)


# ---------------------------------------------------------------------------
# Packet
# ---------------------------------------------------------------------------

# Streaming decode outcomes (mirrors DecodeResultType)
FILL = "fill"        # need more bytes
DISCARD = "discard"  # drop N bytes and resync
PROCESSED = "processed"


@dataclass
class Packet:
    sa: Address = field(default_factory=Address)
    da: Address = field(default_factory=Address)
    command: Command = field(default_factory=Command)
    messages: list = field(default_factory=list)

    @staticmethod
    def create_partial(da: Address, data_type: int, packet_number: int) -> "Packet":
        cmd = Command(
            packet_information=True,
            packet_type=PacketType.Normal,
            data_type=data_type,
            packet_number=packet_number,
        )
        return Packet(sa=Address.my_address(), da=da, command=cmd, messages=[])

    def encode(self) -> bytes:
        data = bytearray()
        data.append(0x32)
        data.append(0)  # size placeholder
        data.append(0)
        data += self.sa.encode()
        data += self.da.encode()
        data += self.command.encode()
        data.append(len(self.messages) & 0xFF)
        for m in self.messages:
            data += m.encode()

        end_position = len(data) + 1
        data[1] = (end_position >> 8) & 0xFF
        data[2] = end_position & 0xFF

        checksum = crc16(bytes(data), 3, end_position - 4)
        data.append((checksum >> 8) & 0xFF)
        data.append(checksum & 0xFF)
        data.append(0x34)
        return bytes(data)

    def to_string(self) -> str:
        parts = [
            f"#Packet Src:{self.sa.to_string()} Dst:{self.da.to_string()} "
            f"dt:{DataType(self.command.data_type).name} pn:{self.command.packet_number}"
        ]
        for m in self.messages:
            parts.append(f"  > {MessageSetType(m.type).name} {m.message_number:#06x} = {m.value}")
        return "\n".join(parts)


def try_decode_packet(buffer: bytearray) -> tuple[str, int, Optional[Packet]]:
    """Try to decode one NASA packet from the front of *buffer*.

    Returns (result, consumed_bytes, packet). Mirrors Packet::decode.
    """
    data = buffer
    if len(data) < 4:
        return (FILL, 0, None)

    if data[0] != 0x32:
        return (DISCARD, 1, None)

    size = (data[1] << 8) | data[2]
    if size < 14 or size > 1500:
        return (DISCARD, 1, None)

    total_len = size + 2
    if total_len > len(data):
        return (FILL, 0, None)

    pkt = bytes(data[:total_len])

    if pkt[size + 1] != 0x34:
        return (DISCARD, 1, None)

    crc_actual = crc16(pkt, 3, size - 4)
    crc_expected = (pkt[size - 1] << 8) | pkt[size]
    if crc_expected != crc_actual:
        return (DISCARD, total_len, None)

    cursor = 3
    sa = Address.decode(pkt, cursor)
    cursor += 3
    da = Address.decode(pkt, cursor)
    cursor += 3
    command = Command.decode(pkt, cursor)
    cursor += 3
    capacity = pkt[cursor]
    cursor += 1

    messages = []
    for _ in range(capacity):
        msg = MessageSet.decode(pkt, cursor, capacity)
        messages.append(msg)
        cursor += msg.size

    return (PROCESSED, total_len, Packet(sa, da, command, messages))


def feed(buffer: bytearray) -> list[Packet]:
    """Consume as many whole packets as possible from *buffer* (mutated in place)."""
    packets: list[Packet] = []
    while True:
        result, consumed, packet = try_decode_packet(buffer)
        if result == FILL:
            break
        if consumed:
            del buffer[:consumed]
        if result == PROCESSED and packet is not None:
            packets.append(packet)
    return packets


# ---------------------------------------------------------------------------
# Value conversions (mirrors operation_mode_to_mode etc.)
# ---------------------------------------------------------------------------


def _s16(value: int) -> int:
    """Interpret a 16-bit value as signed (for temperatures that can be negative)."""
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def operation_mode_to_mode(value: int) -> Mode:
    return {0: Mode.Auto, 1: Mode.Cool, 2: Mode.Dry, 3: Mode.Fan, 4: Mode.Heat}.get(value, Mode.Unknown)


def mode_to_operation_mode(mode: Mode) -> int:
    return int(mode)


def enum_to_fanmode(value: int) -> FanMode:
    return {0: FanMode.Auto, 1: FanMode.Low, 2: FanMode.Mid, 3: FanMode.High, 4: FanMode.Turbo}.get(
        value, FanMode.Unknown
    )


def fanmode_to_nasa(mode: FanMode) -> int:
    return {FanMode.Low: 1, FanMode.Mid: 2, FanMode.High: 3, FanMode.Turbo: 4, FanMode.Auto: 0}.get(mode, 0)
