# EW11 진단 스니퍼: TCP로 들어오는 raw 바이트와 NASA 디코딩 결과를 그대로 출력
"""Standalone EW11 sniffer — no Home Assistant needed.

Usage:
    python tools/ew11_sniff.py <host> <port> [seconds]

Shows raw bytes arriving and how they decode as NASA packets, so we can tell
whether (a) data flows at all, (b) it frames as NASA, (c) which addresses/messages.
"""

import socket
import sys
import time

sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "custom_components/samsung_nasa")

import nasa  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python tools/ew11_sniff.py <host> <port> [seconds]")
        sys.exit(2)
    host = sys.argv[1]
    port = int(sys.argv[2])
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0

    print(f"connecting to {host}:{port} ...")
    sock = socket.create_connection((host, port), timeout=5)
    sock.settimeout(1.0)
    print("connected. listening for", duration, "seconds\n")

    buffer = bytearray()
    total_bytes = 0
    total_packets = 0
    seen_addr: dict[str, int] = {}
    deadline = time.time() + duration

    while time.time() < deadline:
        try:
            chunk = sock.recv(512)
        except socket.timeout:
            continue
        if not chunk:
            print("!! connection closed by EW11")
            break
        total_bytes += len(chunk)
        buffer.extend(chunk)
        # show a short hex preview of raw traffic
        print(f"RAW +{len(chunk):3d}B: {chunk[:32].hex(' ')}{' ...' if len(chunk) > 32 else ''}")

        for pkt in nasa.feed(buffer):
            total_packets += 1
            src = pkt.sa.to_string()
            seen_addr[src] = seen_addr.get(src, 0) + 1
            dt = nasa.DataType(pkt.command.data_type).name
            msgs = ", ".join(
                f"{nasa.MessageSetType(m.type).name}:{m.message_number:#06x}={m.value}"
                for m in pkt.messages
            )
            print(f"   PKT s:{src} d:{pkt.da.to_string()} [{dt}] ({len(pkt.messages)}) {msgs}")

    sock.close()
    print("\n===== summary =====")
    print(f"bytes received : {total_bytes}")
    print(f"packets decoded: {total_packets}")
    print(f"leftover buffer: {len(buffer)} bytes (undecoded)")
    print("addresses seen :")
    for addr, count in sorted(seen_addr.items()):
        klass = int(addr.split(".")[0], 16)
        kind = "indoor" if klass == 0x20 else "outdoor" if klass == 0x10 else f"class {klass:#04x}"
        print(f"   {addr}  x{count}  ({kind})")
    if total_bytes == 0:
        print("\n>> NO DATA. Check EW11 serial params (9600/EVEN/8/1), F1-F2 wiring/polarity, and that EW11 is in transparent TCP mode.")
    elif total_packets == 0:
        print("\n>> Bytes arrive but NOTHING decodes as NASA. Likely wrong baud/parity, non-NASA protocol, or EW11 adding framing. Paste the RAW lines above.")


if __name__ == "__main__":
    main()
