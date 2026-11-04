# 📡 게이트웨이 노트북 세팅 및 운용 가이드라인 (Gateway Setup Guide)

> **프로젝트명**: 온-디바이스 이상 감지 기반 조선소 밀폐공간 작업자 안전 관제 시스템 (캡스톤 디자인)  
> **담당 역할**: 게이트웨이 노트북 및 수신 관제 모니터링 (Gateway Receiver Manager)  
> **대상 기기**: ThinkNode M3, SenseCAP Card Tracker T1000-E  
> **주요 문서 목적**: 팀원 및 외부 공유를 위한 게이트웨이 노트북 구축, 패킷 디버깅, 단계별 현장 실측 가이드라인  

---

## 📋 1. 시스템 개요 및 게이트웨이의 역할

본 프로젝트는 두꺼운 강판 격벽으로 Wi-Fi/LTE 통신이 차단되는 조선소 밀폐 블록(이중저, 탱크 등) 내부 작업자의 추락, 장시간 미동, 열 스트레스 등 이상 상황을 **LoRa Mesh 네트워크**를 통해 실시간으로 관제소에 전달하는 시스템입니다.

```
[작업자 노드 (T1000-E / M3)] 
        │ (1차 센서 감지 & 2차 TinyML 검증)
        ▼
[LoRa Mesh Multi-hop 중계 노드]
        │ (개구부 경유 전송)
        ▼
[게이트웨이 M3 (Receiver)] ──(USB Serial)──▶ [게이트웨이 노트북 (관제/디버깅)]
```

### 게이트웨이 담당자의 핵심 임무
1. **게이트웨이 수신 펌웨어/환경 구축**: M3 노드를 노트북에 시리얼로 연결하고, 패킷 수신 및 로그를 자동 수집하는 디버깅 환경 세팅.
2. **노드 식별 및 패킷 해독**: 수신된 5바이트 압축 비트필드 패킷을 해독하여 발신 노드(Node ID)와 비상 상태(추락/미동/열위험 등)를 관제 화면에 시각화.
3. **통신 품질 측정 및 디버깅**: 신호 세기(RSSI), 신호 대 잡음비(SNR), 중계 횟수(Hop Count), 통신 지연시간을 기록하여 실증 데이터 수집.

---

## 🛠️ 2. 게이트웨이 노트북 환경 세팅 (Setup Checklist)

### Step 1: 게이트웨이 하드웨어 연결 및 시리얼 포트 확인
1. **ThinkNode M3** 기기를 USB 케이블로 게이트웨이 노트북에 연결합니다.
2. 장치 관리자(Windows) 또는 터미널(Linux/macOS)에서 시리얼 포트 인식 여부를 확인합니다.
   * **Windows**: `장치 관리자` -> `포트(COM & LPT)` -> `COMx` 확인
   * **Linux/macOS**: `ls /dev/ttyACM*` 또는 `ls /dev/tty.SLAB*` 확인

### Step 2: Python 필수 라이브러리 설치
VS Code 터미널에서 아래 명령어를 실행하여 Meshtastic SDK 및 시리얼 제어 패키지를 설치합니다.
```bash
pip install meshtastic pyserial
```

### Step 3: Meshtastic LoRa 설정 통일
게이트웨이와 모든 노드 간 통신을 위해 아래 설정을 반드시 동일하게 맞춰야 합니다.
* **LoRa Region**: `KR` (Korea 920MHz 대역)
* **Primary Channel PSK**: `AQ==` (기본 암호화 키)
* **Modem Preset**: `LONG_FAST` 또는 프로젝트 표준 설정

---

## 📦 3. 상태 패킷 및 비트필드 구조 (5-Byte Format)

저주파 LoRa 통신의 대역폭 한계를 극복하기 위해 모든 비상 상태 데이터는 **5바이트 고정 패킷**으로 압축 전송됩니다.

| 바이트 Index | 필드명 | 주요 내용 |
| :---: | :--- | :--- |
| **Byte 0–1** | **Node ID** | 발신 작업자 노드 고유 식별자 (65,535개 식별 가능) |
| **Byte 2** | **Sequence No.** | 패킷 고유 번호 (중복 수신 방지 및 유실률 계산) |
| **Byte 3** | **Status Bitfield** | 8개 비트 각각에 이상 상태 플래그 매핑 (하단 참조) |
| **Byte 4** | **Extra Info** | 상위 4비트: 심각도(Severity) / 하위 4비트: 배터리 잔량 |

### Status Bitfield (Byte 3) 상세 매핑
* `Bit 0`: 추락 감지 (Fall)
* `Bit 1`: 장시간 미동 (Immobility)
* `Bit 2`: 열 스트레스 주의 (Heat Caution)
* `Bit 3`: 열 스트레스 위험 (Heat Warning)
* `Bit 4`: 센서 미착용 (Unworn)
* `Bit 5`: 배터리 저전압 (Low Battery)
* `Bit 6`: 수동 비상 SOS (Manual SOS)
* `Bit 7`: 상황 해제 (RESOLVED)

---

## 💻 4. 게이트웨이 수신 & 디버깅 자동화 스크립트

게이트웨이 노트북에서 실행하여 들어오는 모든 패킷을 실시간 해독하고, CSV 디버그 로그 파일로 남기는 공식 파이썬 코드입니다.

### `gateway_receiver.py`
```python
import time
import csv
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# CSV 로그 파일 경로 설정
LOG_FILE = "gateway_rx_log.csv"

# 로그 파일 헤더 초기화
with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Timestamp", "Node_ID", "Seq_Num", "RSSI_dBm", "SNR_dB", "Hop_Limit", "Status_Hex", "Detected_Events"])

print("==================================================")
print(" 📡 캡스톤 디자인 게이트웨이 수신 관제 시스템 가동")
print("==================================================")

def parse_status_bitfield(bitfield_byte):
    """Byte 3 (Status Bitfield) 1비트 단위 해독 함수"""
    events = []
    if bitfield_byte & (1 << 0): events.append("추락(Fall)")
    if bitfield_byte & (1 << 1): events.append("장시간 미동(Immobility)")
    if bitfield_byte & (1 << 2): events.append("열스트레스 주의")
    if bitfield_byte & (1 << 3): events.append("열스트레스 위험")
    if bitfield_byte & (1 << 4): events.append("미착용")
    if bitfield_byte & (1 << 5): events.append("배터리 저전압")
    if bitfield_byte & (1 << 6): events.append("수동 SOS")
    if bitfield_byte & (1 << 7): events.append("해제(RESOLVED)")
    return ", ".join(events) if events else "정상(NORMAL)"

def on_receive_packet(packet, interface):
    """노드로부터 LoRa 패킷 수신 시 콜백"""
    try:
        rx_time = time.strftime('%Y-%m-%d %H:%M:%S')
        from_id = hex(packet.get('fromId', 0))
        rx_snr = packet.get('rxSnr', 0.0)
        rx_rssi = packet.get('rxRssi', 0)
        hop_limit = packet.get('hopLimit', 0)
        
        decoded = packet.get('decoded', {})
        payload = decoded.get('payload', b'')
        
        # 5바이트 파이프라인 패킷 검증 및 분석
        if len(payload) >= 4:
            seq_num = payload[2] if len(payload) > 2 else packet.get('id', 0)
            bitfield = payload[3] if len(payload) > 3 else payload[0]
            event_str = parse_status_bitfield(bitfield)
        else:
            seq_num = packet.get('id', 0)
            bitfield = 0x00
            event_str = "RAW/Telemetry Data"

        # 터미널 디버그 실시간 출력
        print(f"\n[신호 수신 알림 - {rx_time}]")
        print(f" ├─ 발신 노드 ID : {from_id}")
        print(f" ├─ 시퀀스 번호  : {seq_num}")
        print(f" ├─ 수신 품질   : RSSI = {rx_rssi} dBm | SNR = {rx_snr} dB")
        print(f" ├─ Hop Limit   : {hop_limit}")
        print(f" └─ 감지 이벤트  : {event_str}")

        # CSV 파일에 디버깅 데이터 자동 기록
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([rx_time, from_id, seq_num, rx_rssi, rx_snr, hop_limit, hex(bitfield), event_str])

    except Exception as e:
        print(f"[ERROR] 패킷 파싱 오류 발생: {e}")

# 수신 이벤트 구독 및 연결 가동
pub.subscribe(on_receive_packet, "meshtastic.receive")

try:
    # USB 연결된 M3 게이트웨이 자동 연결
    interface = meshtastic.serial_interface.SerialInterface()
    print("✓ 게이트웨이 수신기 연결 성공. 노드 신호 수신 대기 중...\n")
except Exception as e:
    print(f"X 게이트웨이 시리얼 포트 연결 실패: {e}")
```

---

## 🧪 5. 단계별 검증 및 디버깅 시나리오

| 단계 | 테스트 구분 | 주요 검증 내용 | 성공 기준 (Pass Condition) |
| :---: | :--- | :--- | :--- |
| **1단계** | **1:1 기본 통신** | 랩실 환경에서 노드 1대 ➔ 게이트웨이 가상 비상 패킷 발송 | 게이트웨이 콘솔에 Node ID 및 Bitfield 정상 수신, ACK 응답 전송 확인 |
| **2단계** | **Multi-node & Multi-hop** | 노드 여러 대(T1000-E/M3) 동시 억제 및 중계 노드 거쳐 전송 | 1) `fromId`로 노드 개별 식별 가능<br>2) Hop Count 증가 확인 및 중복 패킷 자동 Drop 확인 |
| **3단계** | **실제 배/격벽 실측** | 조선소 밀폐 블록 및 철판 격벽 환경에서 수신 통신 품질 실측 | 1) RSSI ≥ -110dBm, SNR ≥ -7dB 기록<br>2) 3홉 기준 지연시간 **10초 이내** 도달<br>3) 2분 주기 Heartbeat 3회 미수신(6분) 시 통신두절 감지 |

---

## ❓ 6. 트러블슈팅 가이드 (Troubleshooting)

### Q1. 시리얼 포트가 연결되지 않거나 `Permission Denied` 오류가 발생하는 경우
* **Windows**: 다른 프로그램(Meshtastic Web App 또는 Arduino Serial Monitor)이 포트를 점유하고 있는지 확인 후 종료.
* **Linux/Ubuntu**: 시리얼 권한 추가 명령 실행 후 재로그인.
  ```bash
  sudo usermod -aG dialout $USER
  ```

### Q2. 노드에서 패킷을 보냈는데 게이트웨이에 수신되지 않는 경우
1. 노드와 게이트웨이의 **LoRa Region**(KR) 및 **PSK**(`AQ==`) 값이 동일한지 앱에서 확인.
2. M3 게이트웨이의 안테나 결착 상태 확인 및 RSSI/SNR 수신 감도 체크.

---
*가이드라인 관련 문의 및 수정 요청은 저장소 Issue 또는 게이트웨이 담당자에게 전달해 주세요.*
