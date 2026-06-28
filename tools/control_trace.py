# 제어 추적: 우리 컨트롤러(80.ff.00) 명령 패킷과 실내기 응답을 타임스탬프로 출력
"""Trace control commands and replies on the bus.

Usage: python tools/control_trace.py <host> <port> [seconds]
Issue ONE command from HA while this runs. It shows every packet our controller
(80.ff.00) transmits and every reply, with millisecond deltas, so we can see
whether one HA action sends 1 or 2 command packets and how fast the unit replies.
"""

import socket
import sys
import time

sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "custom_components/samsung_nasa")

import nasa  # noqa: E402

ME = "80.ff.00"  # our controller (JIGTester)


def main() -> None:
    host, port = sys.argv[1], int(sys.argv[2])
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    s = socket.create_connection((host, port), timeout=5)
    s.settimeout(1.0)
    print(f"tracing {host}:{port} for {secs}s — issue ONE command in HA now.\n")
    buf = bytearray()
    t0 = time.time()
    last = t0
    cmd_count = 0
    pending_since = None
    while time.time() - t0 < secs:
        try:
            chunk = s.recv(512)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf.extend(chunk)
        for pkt in nasa.feed(buf):
            src, dst = pkt.sa.to_string(), pkt.da.to_string()
            now = time.time()
            dt = nasa.DataType(pkt.command.data_type).name
            rel = (now - t0) * 1000
            delta = (now - last) * 1000
            last = now
            if src == ME:
                cmd_count += 1
                pending_since = now
                msgs = ", ".join(f"{m.message_number:#06x}={m.value}" for m in pkt.messages)
                print(f"[{rel:7.0f}ms +{delta:5.0f}] >>> CMD #{cmd_count} -> {dst} pn={pkt.command.packet_number} [{dt}] {msgs}")
            elif dst == ME or src.startswith("20.") or src.startswith("10."):
                ack = ""
                if pending_since is not None and src != ME:
                    ack = f"  (<-{(now - pending_since) * 1000:.0f}ms after last CMD)"
                    pending_since = None
                print(f"[{rel:7.0f}ms +{delta:5.0f}]      reply s:{src} d:{dst} [{dt}]{ack}")
    s.close()
    print(f"\n=== {cmd_count} command packet(s) from {ME} observed ===")


if __name__ == "__main__":
    main()
