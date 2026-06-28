# 단일 명령 송신 테스트: 정확히 1패킷(메시지 1개)만 보내고 종료 — 비프 횟수 격리용
"""Send exactly ONE NASA Request packet and exit. No retry, no HA.

Usage: python tools/send_one.py <host> <port> <address> <target_c>
Example: python tools/send_one.py 192.168.0.99 8899 20.00.01 24

Isolates "one packet -> how many beeps?" independent of HA / integration version.
"""

import socket
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "custom_components/samsung_nasa")

import nasa  # noqa: E402


def main() -> None:
    host, port, address, target = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
    da = nasa.Address.parse(address)
    pkt = nasa.Packet.create_partial(da, nasa.DataType.Request, packet_number=1)
    msg = nasa.MessageSet(nasa.MessageNumber.VAR_in_temp_target_f)
    msg.value = int(round(target * 10))
    pkt.messages.append(msg)
    raw = pkt.encode()

    s = socket.create_connection((host, port), timeout=5)
    s.sendall(raw)
    s.close()
    print(f"sent ONE packet to {address}: set target = {target}C")
    print(f"  raw: {raw.hex()}")
    print("  -> count the beeps now.")


if __name__ == "__main__":
    main()
