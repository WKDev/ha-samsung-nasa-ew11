# context-notes — samsung_nasa

작업하며 내린 결정과 근거를 계속 덧붙인다.

## 배경
- 기존: ESP32 + ESPHome `samsung_ac`(WKDev/esphome_samsung_hvac_bus@notify-as-ack)로 삼성 시스템에어컨 제어 중.
- ESP32는 월패드 MITM 전용으로 차출되어 여력 없음 → EW11(RS485↔TCP 브리지)로 HA 네이티브 통합 전환.
- 프로토콜: **삼성 NASA** 확정 (주소 `20.00.01`, `10.00.00` 형식 / 9600 / EVEN).

## 참조 구현
- C++ 원본: `esphome_samsung_hvac_bus/components/samsung_ac/`
  - `protocol_nasa.cpp/.h` = 코덱 본체 (이걸 Python 포팅)
  - `protocol.h` = MessageTarget 인터페이스 / ProtocolRequest
- 포팅 정확도 기준: C++ 비트 연산을 그대로 재현 (uint16 wrap은 `& 0xFFFF`).

## 핵심 프로토콜 사실 (C++에서 추출)
- 프레임: `0x32` | size(2B, BE) | payload | CRC16(2B) | `0x34`. **total_len = size + 2**.
  - CRC 범위: `crc16(pkt, start=3, length=size-4)`. CRC 바이트 위치 = pkt[size-1],pkt[size]. end byte = pkt[size+1].
  - size 유효범위 14~1500. 어긋나면 1바이트 버리고 resync.
- payload(커서 3부터): SA(3) DA(3) Command(3) capacity(1) 그리고 MessageSet×capacity.
- Command byte0: bit7=packetInformation, bit6-5=protocolVersion, bit4-3=retryCount. byte1: bit7-4=packetType, bit3-0=dataType. byte2=packetNumber.
- MessageSet type = `(messageNumber & 0x600) >> 9`: 0=Enum(3B),1=Variable(4B),2=LongVariable(6B),3=Structure.
- 내 주소(컨트롤러) = JIGTester `0x80`, channel `0xFF`, addr `0x00` → 송신 시 SA.

## 제어 / ACK (중요)
- 삼성 실내기는 컨트롤러에 **DataType::Ack를 안 줌**. 상태 Notification만 브로드캐스트.
- 그래서 "명령 보내면 여러 번 보내더라" = ACK 없으니 재전송 루프가 계속 도는 것.
- fork의 `notify-as-ack` 패치: **명령 대상 주소(da)에서 어떤 응답이 오면 그걸 ack로 간주** → 재전송 중단 + 실내기 확인음(삐) 반복 방지. (`ack_data_from_source`)
- Python 포팅에서도 동일 전략: 명령 전송 후 da 주소발 패킷 수신 시 pending 해제.

## 결정
- 도메인 `samsung_nasa`, 새 레포 `ha-samsung-nasa-ew11`.
- 코덱은 PyPI 분리 없이 `nasa.py`로 번들 (imazu의 wp-imazu 방식과 달리 릴리스 마찰 제거).
- iot_class = `local_push` (버스 Notification 푸시 기반).
- MVP: climate(실내기) + sensor(실외/온도/에너지/에러). non-NASA·급탕(water heater)·ERV는 범위 외(추후).

## 미해결 / 현장 확인 필요
- EW11 TCP 버퍼링이 제어 타이밍에 주는 영향 — 재전송 간격 튜닝 필요할 수 있음.
- RS485 버스 충돌(송신 시점) — 1차는 단순 재전송, 문제 시 버스 idle gap 감지 추가.
- 실내기 주소 자동발견은 버스 트래픽 의존 — 부팅 직후 일부 누락 가능.
