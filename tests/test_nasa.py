# NASA 코덱 검증: 인코딩→디코딩 라운드트립, CRC, 메시지 타입/값 변환
"""Unit tests for the NASA codec. Runs under pytest or as a plain script."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "samsung_nasa"))

import nasa  # noqa: E402
from nasa import (  # noqa: E402
    Address,
    AddressClass,
    Command,
    DataType,
    MessageNumber,
    MessageSet,
    MessageSetType,
    Packet,
    crc16,
    feed,
)


def test_message_type_from_number():
    # type = (number & 0x600) >> 9
    assert MessageSet(MessageNumber.ENUM_in_operation_power).type == MessageSetType.Enum  # 0x4000
    assert MessageSet(MessageNumber.VAR_in_temp_room_f).type == MessageSetType.Variable  # 0x4204
    assert MessageSet(MessageNumber.LVAR_OUT_CONTROL_WATTMETER_1W_1MIN_SUM).type == MessageSetType.LongVariable  # 0x8413


def test_address_roundtrip():
    a = Address.parse("20.00.01")
    assert a.klass == AddressClass.Indoor and a.channel == 0 and a.address == 1
    assert a.to_string() == "20.00.01"
    assert Address.decode(a.encode(), 0).to_string() == "20.00.01"


def test_my_address():
    me = Address.my_address()
    assert me.to_string() == "80.ff.00"


def test_enum_request_roundtrip():
    # Build a power-on Request to 20.00.01 and decode it back.
    da = Address.parse("20.00.01")
    pkt = Packet.create_partial(da, DataType.Request, packet_number=7)
    power = MessageSet(MessageNumber.ENUM_in_operation_power)
    power.value = 1
    pkt.messages.append(power)

    raw = pkt.encode()
    assert raw[0] == 0x32 and raw[-1] == 0x34

    buf = bytearray(raw)
    decoded = feed(buf)
    assert len(buf) == 0  # fully consumed
    assert len(decoded) == 1
    d = decoded[0]
    assert d.sa.to_string() == "80.ff.00"
    assert d.da.to_string() == "20.00.01"
    assert d.command.data_type == DataType.Request
    assert d.command.packet_number == 7
    assert len(d.messages) == 1
    assert d.messages[0].message_number == MessageNumber.ENUM_in_operation_power
    assert d.messages[0].value == 1


def test_variable_request_roundtrip():
    # Target temp 24.0C -> value 240 (x10), Variable type.
    da = Address.parse("20.00.02")
    pkt = Packet.create_partial(da, DataType.Request, packet_number=255)
    temp = MessageSet(MessageNumber.VAR_in_temp_target_f)
    temp.value = 240
    pkt.messages.append(temp)

    decoded = feed(bytearray(pkt.encode()))
    assert len(decoded) == 1
    m = decoded[0].messages[0]
    assert m.type == MessageSetType.Variable
    assert m.value == 240


def test_multi_message_and_back_to_back():
    da = Address.parse("20.00.01")
    p1 = Packet.create_partial(da, DataType.Request, 1)
    m_mode = MessageSet(MessageNumber.ENUM_in_operation_mode)
    m_mode.value = 1  # Cool
    m_temp = MessageSet(MessageNumber.VAR_in_temp_target_f)
    m_temp.value = 215
    p1.messages += [m_mode, m_temp]

    p2 = Packet.create_partial(Address.parse("20.00.02"), DataType.Request, 2)
    m_pow = MessageSet(MessageNumber.ENUM_in_operation_power)
    m_pow.value = 0
    p2.messages.append(m_pow)

    # Two packets concatenated in one buffer + a trailing partial fragment.
    buf = bytearray(p1.encode() + p2.encode() + b"\x32\x00")
    decoded = feed(buf)
    assert len(decoded) == 2
    assert len(decoded[0].messages) == 2
    assert decoded[0].messages[0].value == 1
    assert decoded[0].messages[1].value == 215
    assert decoded[1].messages[0].value == 0
    # trailing fragment kept for next read
    assert bytes(buf) == b"\x32\x00"


def test_resync_on_garbage_prefix():
    da = Address.parse("20.00.01")
    pkt = Packet.create_partial(da, DataType.Request, 9)
    m = MessageSet(MessageNumber.ENUM_in_operation_power)
    m.value = 1
    pkt.messages.append(m)
    buf = bytearray(b"\xff\x00\xaa" + pkt.encode())  # garbage before start byte
    decoded = feed(buf)
    assert len(decoded) == 1
    assert decoded[0].command.packet_number == 9


def test_crc_rejects_corruption():
    da = Address.parse("20.00.01")
    pkt = Packet.create_partial(da, DataType.Request, 3)
    m = MessageSet(MessageNumber.ENUM_in_operation_power)
    m.value = 1
    pkt.messages.append(m)
    raw = bytearray(pkt.encode())
    # flip a payload byte (not start/size) -> CRC must fail -> whole packet discarded
    raw[8] ^= 0xFF
    decoded = feed(raw)
    assert decoded == []


def test_crc16_known_vector():
    # crc over an all-zero region is 0
    assert crc16(bytes(10), 0, 10) == 0


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if failed else 0)
