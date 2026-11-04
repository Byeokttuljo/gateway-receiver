# 🚢 조선소 밀폐구역 작업자 안전을 위한 온-디바이스 이상 감지 및 LoRa Mesh 비상 경보 시스템

> **조선소 이중저·탱크 등 두꺼운 강판 격벽으로 무선 통신이 차단되는 밀폐공간에서 작업자의 추락, 장시간 미동, 열 스트레스 등 비상 상황을 온-디바이스로 감지하고, 초압축 5바이트 패킷과 LoRa Mesh 다단 중계(Multi-hop)를 통해 외부 게이트웨이로 유실 없이 전달하는 강건한(Robust) 안전 관제 시스템**

---

## 📌 1. 프로젝트 개요 (Overview)

선박 건조 현장의 밀폐구역(이중저, 탱크 내부)은 두꺼운 강판 구조물로 둘러싸여 있어 기존의 Wi-Fi, Bluetooth, LTE/5G 통신망이 완전히 물리적으로 차단됩니다. 이러한 통신 음영 지역에서 작업자가 추락하거나 의식을 잃을 경우, 외부 관제소에서 사고를 즉시 인지하기 어려워 골든타임을 놓칠 위험이 매우 큽니다.

본 프로젝트는 **nRF52840** 기반 상용 오픈 노드(**SenseCAP T1000-E**, **ThinkNode M3**)에 커스텀 펌웨어를 구축하여 다음과 같은 문제를 해결합니다:
1. **온-디바이스(On-device) 센서 처리 및 TinyML 오경보 검증**을 통해 통신에 의존하지 않고 노드 스스로 이상 행동을 판정합니다.
2. 8가지 안전 상태 정보를 **단 5바이트의 비트필드(Bit-field) 패킷으로 극한 압축**하여 저주파 LoRa 대역폭 제약을 극복합니다.
3. 개구부(맨홀, 게이트) 방향으로 노드 간 **LoRa Mesh Multi-hop 릴레이 통신**을 수행하여 외부 게이트웨이까지 10초 이내(3홉 기준)를 목표로 비상 신호를 유실 없이 전달합니다.

---

## 💡 2. 주요 기능 (Key Features)

### ① 1차 규칙 기반(Rule-based) 이상 감지
* **추락 감지 (Fall Detection)**:
  * 가속도 센서 원신호(Raw Data, ±16g 범위) 기반으로 **0.4g 이하 자유낙하(80ms 이상) → 1초 이내 3g 이상 충격** 패턴 감지.
  * **6g 초과 대형 충격** 발생 시 AI 검증을 스킵하고 즉시 비상 경보 발령 (Bypass 특례).
* **장시간 미동 감지 (Immobility)**:
  * 착용 상태에서 1분 단위 가속도 분산(Variance) 모니터링.
  * 2분 미동 시 1차 진동 알림 → 3분 연속 응답 없을 시 정식 비상 경보 진입 (추락 직후에는 1분으로 단축).
* **열 스트레스 감지 (Heat Stress)**:
  * 외기 온습도 열 지수(Heat Index) + 피부 온도 상승 추세 + 활동량을 종합 평가하여 '주의'(진동) 및 '위험'(정식 경보) 단계 분리.
* **미착용 감지**:
  * 피부 온도와 외기 온도 차이 및 미세 움직임 부재 시 미착용으로 판정하여 미동 오경보 방지.

### ② 2차 온-디바이스 TinyML 오경보 검증
* 센서 하드웨어 **FIFO**와 MCU **소프트웨어 링 버퍼(Ring Buffer)**를 결합하여 충격 전후 **최근 2초간의 파형(전 1s + 후 1s)**을 보관.
* 경량 분류 모델(1D-CNN / Random Forest)을 구동하여 망치질, 계단 점프 등 일상 작업 동작으로 인한 오경보를 스크리닝.
* **Fail-safe 철학**: **추락 재현율(Recall) 99% 이상**을 최우선 목표로 설정하며, 판정이 애매할 경우 비상 경보를 울림.

### ③ FSM 기반 현장 경보 및 유예/취소 (RECHECK) 제어
* **위험도별 차등 유예 타이머 (Grace Period)**: 강한 추락(10s), 일반 추락(20s), 미동(15s), 열 위험(30s).
* **오입력 방지 버튼 취소**: 작업자가 단순 오경보 확인 시 **2초 이상 길게 누름(Long Press)** 동작으로 경보 취소.
* **RECHECK (재감시) 모드**: 취소 후 동일 이벤트 알림은 억제하되, 상태 악화(주의 → 위험) 및 타 이상 발생 시 즉시 재경보.

### ④ 5바이트 초압축 비트필드 & LoRa Mesh 통신
* **5바이트 패킷 구조**:
  * `Byte 0–1`: Node ID (애플리케이션 레벨 발신 노드 식별자 — 본 시스템의 식별 기준)
  * `Byte 2`: Sequence Number (중복 수신 제거 및 유실 확인)
  * `Byte 3`: Status Bitfield (추락, 미동, 열주의, 열위험, 미착용, 배터리저전압, SOS, RESOLVED 각 1bit)
  * `Byte 4`: Extra Info (상위 4bit: 심각도, 하위 4bit: 배터리 잔량)
* **노드 식별 체계 (중요)**:
  * **애플리케이션 식별자**는 payload `Byte 0–1`의 Node ID를 **단일 기준**으로 사용합니다.
  * Meshtastic 전송 계층의 `fromId`는 **전송 경로 참조용**으로만 활용하며, 관제 매핑 기준으로 삼지 않습니다. (관련 논의: Issue 참조)
* **Mesh 네트워크 충돌 및 지연 방지**:
  * **Random Backoff** 및 **ACK + 재전송**으로 패킷 충돌 방지.
  * **Sequence No. & Node ID** 기반 중복 패킷 무한 루프(Drop) 차단.
  * RSSI, SNR, Hop Count, 배터리 잔량을 평가하여 **최적 개구부 중계 노드 동적 선정**.

### ⑤ Heartbeat 연결 감시 (침묵 감지)
* 노드는 **2분 주기**로 상태 텔레메트리 패킷 발송.
* 게이트웨이가 **3회 연속(6분) 수신 실패 시 '통신 두절/기기 파손'** 이벤트 즉시 발령.

---

## 🛠️ 3. 하드웨어 스펙 및 아키텍처

| 구분 | 하드웨어 / 사양 | 주요 기능 및 용도 |
| :--- | :--- | :--- |
| **Main MCU** | Nordic nRF52840 (ARM Cortex-M4F @ 64MHz) | Flash 1MB, RAM 256KB, 저전력 슬립 & TinyML 추론 |
| **LoRa RF Module** | Semtech SX1262 / LR1110 (900MHz 대역) | LoRa Mesh Multi-hop 통신, KR920 대역 지원 |
| **Wearable Node** | Seeed Studio SenseCAP T1000-E, ThinkNode M3 | 작업자 착용형 노드 (3축 가속도, 피부온도, 부저/진동 내장) |
| **Gateway Node** | ThinkNode M3 + PC/노트북 (USB Serial) | 개구부 외부 수신기, 실시간 관제 및 디버그 수신 |
| **Sensors** | 3축 가속도계 (±16g), 피부 접촉 온도계, 외기 온습도계 | 충격 포화 방지 raw 데이터 추출 및 열 지수 계산 |

---

## 📁 4. 프로젝트 디렉토리 구조

> ✅ 현재 레포에 포함됨 / 🔜 구현·추가 예정 (아래는 프로젝트 전체 목표 구조)

```text
├── firmware/                        🔜
│   ├── src/
│   │   ├── main.cpp                 # Main FSM 및 태스크 스케줄러
│   │   ├── sensor_manager.cpp       # 가속도 FIFO & 온습도 샘플링
│   │   ├── ring_buffer.cpp          # 2초 윈도우 순환 버퍼 (전 1s + 후 1s)
│   │   ├── tinyml_inference.cpp     # 1D-CNN / INT8 양자화 모델 추론
│   │   ├── fsm_alert.cpp            # ALERTING, RECHECK, 유예 타이머 제어
│   │   └── lora_mesh.cpp            # 5바이트 비트필드 인코딩, ACK & Backoff
│   └── include/
├── tinyml_model/                    🔜
│   ├── train_model.py               # 1D-CNN / Random Forest 학습 스크립트
│   ├── quantize_tflite.py           # INT8 C-array 변환기
│   └── synthetic_dataset/           # 가상 추락, 망치질, 걷기 파형 데이터
├── gateway/
│   ├── gateway_receiver.py          🔜 게이트웨이 노트북 전용 디버깅/수신 스크립트
│   └── GATEWAY_GUIDELINE.md         ✅ 게이트웨이 환경 구축 및 실측 가이드
├── simulation/                      🔜
│   └── mesh_sim.py                  # VS Code 기반 3홉 지연시간 및 중복 Drop 테스트
└── README.md                        ✅ 프로젝트 메인 안내 문서
```

---

## 💻 5. 게이트웨이 노트북 실행 가이드

### 1) 환경 준비 및 패키지 설치
```bash
pip install meshtastic pyserial
```

### 2) M3 게이트웨이 수신 스크립트 실행
게이트웨이 M3 노드를 USB로 노트북에 연결한 후 아래 스크립트를 구동합니다:
```bash
python gateway/gateway_receiver.py
```
* **수신 콘솔 디버그**: Node ID, Sequence No., RSSI(dBm), SNR(dB), Hop Count 및 5바이트 비트필드가 실시간으로 인코딩/디코딩되어 출력됩니다.
* **자동 로그 저장**: 수신된 모든 비상 이벤트는 `gateway_rx_log.csv` 파일에 실시간 기록됩니다.

> 자세한 환경 구축·디버깅·실측 절차는 [`gateway/GATEWAY_GUIDELINE.md`](gateway/GATEWAY_GUIDELINE.md) 참조.

---

## 📊 6. 성능 목표 및 검증 현황 (Targets & Status)

> **상태(Status)** 열은 현재 기준입니다. 측정이 완료된 항목은 `실측 완료 (값)`으로 갱신하세요.

### TinyML 모델 제원 (구조상 확정값)
| 항목 | 값 |
| :--- | :--- |
| 1D-CNN 파라미터 수 | 약 14,691개 |
| INT8 양자화 모델 크기 | 약 14.35 KB (nRF52840 Flash의 약 1.4%) |

### 성능 지표
| 항목 | 목표(Target) | 상태(Status) |
| :--- | :--- | :--- |
| 추락 재현율 (Recall) | ≥ 99% | 학습/모의 기준 — 현장 데이터 검증 예정 |
| nRF52840 추론 지연 | ≤ 3 ms (약 2.94ms 예상) | 벤치마크 기준 — 온-디바이스 실측 예정 |
| 3홉 전송 지연 | < 10초 | 모의 기준 — 현장 실측 예정 |
| 수신 통신 품질 | RSSI ≥ -110 dBm, SNR ≥ -7 dB | 관제 기준 — 현장 실측 예정 |
| 통신 두절 감지 | 2분 주기 Heartbeat 3회 미수신 시 6분 내 통보 | 설계 완료 — 통합 검증 예정 |

---

## 📜 7. 라이선스 및 협력 기관
* **과제구분**: 캡스톤 디자인 (벽뚫조)
* **협력기관**: HD현대중공업 스마트 안전관제 연계
* **License**: MIT License
