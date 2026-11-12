# 📡 [벽뚫조] 5바이트 비상 패킷 구조 명세서 (Node ➔ Gateway)

## 1. 개요 및 목적
* **개발 배경**: 선박 건조 현장 이중저·탱크 내부 등 철판으로 둘러싸인 밀폐구역은 무선통신 환경이 열악합니다.
* **압축 목적**: LoRa 통신의 저대역폭 제약 환경에서 공중 전송 시간(Airtime)을 최소화하여 전파 충돌을 방지하고 전송 성공률을 극대화합니다.
* **패킷 크기**: **고정 5바이트 (Fixed 5 Bytes Payload)**

---

## 2. 전체 패킷 레이아웃 (Packet Layout)

| Byte 위치 | 필드명 (Field Name) | 데이터 타입 | 설명 |
| :---: | :--- | :---: | :--- |
| **Byte 0 ~ 1** | **Node ID** | `uint16_t` | 최초 발신 노드 식별 번호 (2바이트 Big-Endian) |
| **Byte 2** | **Sequence No.** | `uint8_t` | 패킷 순서 번호 (0~255 순환, 중복 제거 및 유실 확인용) |
| **Byte 3** | **Status Bitfield** | `uint8_t` | 8가지 비상 상태 스위치 (비트 플래그) |
| **Byte 4** | **Severity & Battery**| `uint8_t` | 상위 4비트: 심각도 / 하위 4비트: 배터리 잔량 단계 |

---

## 3. Byte 3: Status Bitfield 상세 (비트 맵)

각 비트(Bit)가 `1`이면 해당 이벤트가 활성화(ON)된 상태입니다.

| Bit 위치 | Hex 마스크 | 이벤트 명칭 | 비고 및 감지 조건 |
| :---: | :---: | :--- | :--- |
| **Bit 0** | `0x01` | **추락 (Fall)** | 자유낙하 → 충격 감지 시 활성화 |
| **Bit 1** | `0x02` | **장시간 미동 (Immobility)** | 활동량 저하 상태 지속 시 활성화 |
| **Bit 2** | `0x04` | **열스트레스 주의 (Heat Caution)** | 열 지수 기준 초과 |
| **Bit 3** | `0x08` | **열스트레스 위험 (Heat Warning)** | 열 지수 + 피부온도 상승 추세 |
| **Bit 4** | `0x10` | **미착용 (Unworn)** | 피부온도 차이 미미 + 미세동작 없음 |
| **Bit 5** | `0x20` | **배터리 부족 (Low Battery)** | 배터리 전압 임계값 이하 |
| **Bit 6** | `0x40` | **수동 SOS (Manual SOS)** | 작업자 버튼 입력 (짧게 3회) |
| **Bit 7** | `0x80` | **해제 (RESOLVED)** | 비상 상황 종료 및 작업자 해제 요청 |

> 💡 **Hex 비트 연산 예시**
> * `0x01` : 추락 단독 발생
> * `0x41` : 추락 + 수동 SOS 동시 발생 (`0x01` | `0x40`)
> * `0x80` : 상황 해제 패킷

---

## 4. Byte 4: Severity & Battery 상세

* **상위 4비트 (Bit 7~4)**: **경보 심각도 (Severity Level 0 ~ 15)**
* **하위 4비트 (Bit 3~0)**: **배터리 잔량 단계 (Battery Level 0 ~ 15)**

$$\text{Byte 4} = ((\text{Severity} \ \& \ 0x0F) \ll 4) \ | \ (\text{Battery} \ \& \ 0x0F)$$

---

## 5. 💻 C/C++ 노드 펌웨어 전송 예시 코드

노드 담당자가 nRF52840 펌웨어(C/C++)에서 5바이트 페이로드를 생성하고 전송할 때 참고할 수 있는 구조입니다.

```cpp
#include <stdint.h>

// 5바이트 패킷 구성 및 LoRa 전송 예시 함수
void send_emergency_packet(uint16_t node_id, uint8_t status_bitfield, uint8_t severity, uint8_t battery_lvl) {
    static uint8_t seq_num = 0;
    uint8_t payload[5];

    // Byte 0-1: Node ID (Big-Endian)
    payload[0] = (node_id >> 8) & 0xFF;
    payload[1] = node_id & 0xFF;

    // Byte 2: Sequence Number
    payload[2] = seq_num++;

    // Byte 3: Status Bitfield
    payload[3] = status_bitfield;

    // Byte 4: Severity(상위 4비트) | Battery(하위 4비트)
    payload[4] = ((severity & 0x0F) << 4) | (battery_lvl & 0x0F);

    // Meshtastic 전송 API 호출 (5바이트 페이로드 공중 발사)
    service.sendPayload(payload, sizeof(payload));
}
```

---

## 6. 📡 게이트웨이 파이썬 디코딩 구조

게이트웨이(`gateway_receiver.py`) 수신 시 5바이트 페이로드가 아래 로직을 통해 해독됩니다.

```python
def parse_bitfield_payload(payload_bytes):
    if len(payload_bytes) < 5:
        return None
    
    app_node_id = (payload_bytes[0] << 8) | payload_bytes[1]
    seq_num = payload_bytes[2]
    bitfield = payload_bytes[3]
    
    events = []
    if bitfield & (1 << 0): events.append("추락(Fall)")
    if bitfield & (1 << 1): events.append("장시간 미동(Immobility)")
    if bitfield & (1 << 2): events.append("열스트레스 주의")
    if bitfield & (1 << 3): events.append("열스트레스 위험")
    if bitfield & (1 << 4): events.append("미착용(Unworn)")
    if bitfield & (1 << 5): events.append("배터리 부족")
    if bitfield & (1 << 6): events.append("수동 SOS")
    if bitfield & (1 << 7): events.append("해제(RESOLVED)")
    
    return {
        "app_node_id": f"0x{app_node_id:04X}",
        "seq_num": seq_num,
        "bitfield_hex": f"0x{bitfield:02X}",
        "events": ", ".join(events) if events else "정상(NORMAL)"
    }
```
