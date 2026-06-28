# 원시 바이트 전체를 파일로 캡처 (분석용)
import socket, sys, time
host, port, secs, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
s = socket.create_connection((host, port), timeout=5); s.settimeout(1.0)
buf = bytearray(); dl = time.time() + secs
while time.time() < dl:
    try: c = s.recv(1024)
    except socket.timeout: continue
    if not c: break
    buf += c
s.close()
open(out, "wb").write(buf)
print(f"captured {len(buf)} bytes -> {out}")
