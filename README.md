# Samsung A/C (NASA over EW11) — Home Assistant

삼성 시스템에어컨의 **NASA 프로토콜** RS485 버스를 **EW11**(RS485↔TCP 브리지)을 통해
Home Assistant에 네이티브로 붙이는 HACS 커스텀 통합입니다.

ESP32 + ESPHome(`esphome_samsung_hvac_bus`) 없이, EW11 하나만으로 실내기 제어와
실외기 모니터링을 합니다. NASA 파서는 `esphome_samsung_hvac_bus`의 C++ 구현을
Python으로 포팅했습니다.

> 비-NASA(구형) 프로토콜, 급탕(water heater), ERV는 현재 범위 밖입니다.

## 동작 개요

```
삼성 실내기/실외기 ──RS485(F1/F2)── EW11 ──TCP── Home Assistant (이 통합)
```

- 실내기(주소 `20.xx.xx`) → `climate` 엔티티 (전원/모드/설정온도/현재온도/팬/스윙)
- 실외기(주소 `10.xx.xx`) → 센서 (실외온도/순시전력/누적에너지/에러코드)
- 디바이스는 버스 트래픽에서 **자동 발견**됩니다.

## 배선 (EW11)

| 삼성 RS485 | EW11 |
|---|---|
| F1 | A (RS485+) |
| F2 | B (RS485-) |

- 통신 파라미터: **9600 bps, EVEN parity, 8 data, 1 stop**
- EW11은 **TCP Server / transparent** 모드, 기본 포트 `8899`.
- 극성(F1/F2 ↔ A/B)이 반대면 통신이 안 되니 바꿔 꽂아 보세요.

## 설치 (HACS)

1. HACS → Integrations → 우측 상단 메뉴 → Custom repositories
2. 이 저장소 URL 추가, 카테고리 `Integration`
3. "Samsung A/C (NASA over EW11)" 설치 후 HA 재시작
4. 설정 → 기기 및 서비스 → 통합 추가 → Samsung A/C → EW11 host/port 입력

## 제어와 재전송 (중요)

삼성 실내기는 컨트롤러에 `Ack`를 보내지 않고 상태 `Notification`만 브로드캐스트합니다.
그래서 명령은 **대상 주소에서 응답이 올 때까지 재전송**합니다(최대 `SEND_MAX_RETRIES`회,
`SEND_RETRY_INTERVAL`초 간격). 응답을 ACK로 간주하면 재전송을 멈춥니다 — ESPHome
포크의 `notify-as-ack` 동작과 동일합니다.

## 개발 / 테스트

프로토콜 코덱은 HA 비의존이라 단독 테스트됩니다.

```bash
python tests/test_nasa.py
```

## 문제 해결

**기기/엔티티가 안 뜬다 → 거의 항상 EW11 시리얼 설정 문제입니다.**

`tools/ew11_sniff.py <host> <port>` 로 버스를 직접 들여다보세요.

- **바이트 0** → 배선(F1·F2)/극성, EW11가 TCP Server(transparent) 모드인지 확인.
- **바이트는 오는데 패킷 0**, 그리고 `0xfd 0xf7` 같은 0xfX 노이즈가 섞이고 같은 패킷이
  읽을 때마다 바이트 정렬이 달라진다 → **패리티 불일치**입니다. EW11를
  **9600 / 8 / EVEN / 1**로 맞추세요(esphome `parity: EVEN`과 동일). 패리티가 NONE이면
  프레이밍 에러로 바이트가 간헐적으로 깨집니다.
- `0xf7 … 0xee` 프레이밍이 보이면 그건 삼성 NASA가 아니라 **월패드 같은 다른 버스**입니다.
  EW11 IP를 잘못 짚은 것이니 에어컨 버스에 연결된 EW11 주소를 확인하세요.

## 한계 / 알려진 이슈

- EW11의 TCP 버퍼링이 제어 타이밍에 영향을 줄 수 있어 재전송 파라미터 튜닝이 필요할 수 있습니다.
- RS485 버스 충돌 회피는 1차 버전에서 단순 재전송에 의존합니다.
- 실내기 주소 자동발견은 버스 트래픽에 의존하므로 부팅 직후 일부가 늦게 잡힐 수 있습니다.
