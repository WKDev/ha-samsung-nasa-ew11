# checklist — samsung_nasa (EW11 → HA)

## 1. 프로토콜 코덱 (nasa.py) — 검증 가능 단위
- [ ] CRC16(poly 0x1021, init 0) 포팅 + 알려진 패킷으로 검증
- [ ] Address / Command / MessageSet decode·encode 포팅
- [ ] Packet.decode (프레이밍 0x32 … CRC … 0x34, size+2, resync) 포팅
- [ ] Packet.encode (Request 패킷 생성)
- [ ] 스트림 버퍼 feed() → 패킷 리스트 (Fill/Discard/Processed)
- [ ] 메시지번호 → 상태 매핑 (room/target temp, power, mode, fan, swing, 실외 센서)
- [ ] tests/test_nasa.py: encode→decode 라운드트립, CRC, 실측 덤프 파싱 → pytest 통과

## 2. EW11 TCP 클라이언트 (client.py)
- [ ] asyncio 소켓 연결/재연결
- [ ] 수신 바이트 버퍼링 → feed() → 패킷 콜백
- [ ] 송신: Request 인코딩 후 전송
- [ ] 재전송 루프: 대상 주소에서 Notification 올 때까지 N회/간격 재시도 (ACK 대체)

## 3. 상태 모델 / 코디네이터 (coordinator.py)
- [ ] 주소 자동 등록 (버스 트래픽에서 실내기 발견)
- [ ] 디바이스별 상태 보관 + HA dispatcher 통지

## 4. HA 통합
- [ ] manifest.json / const.py / __init__.py (config entry setup)
- [ ] config_flow.py (host/port 입력 + 연결 테스트)
- [ ] climate.py (실내기)
- [ ] sensor.py (실외/온도/에너지/에러)
- [ ] strings.json + translations/en,ko

## 5. HACS 패키징
- [ ] hacs.json
- [ ] README.md (배선/EW11 설정/설치)
- [ ] manifest version, iot_class=local_push

## 6. 검증
- [ ] 코덱 pytest 통과
- [ ] (현장) EW11 연결 → 엔티티 생성 확인
- [ ] (현장) 제어 명령 1회 → 실내기 반응 + 재전송 멈춤 확인
