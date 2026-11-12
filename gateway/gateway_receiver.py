
import time
import sys
import csv
import os
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# 로깅 파일 설정 (이슈 #6)
LOG_FILE = "gateway_rx_log.csv"
CSV_HEADERS = [
    "Timestamp", "App_Node_ID", "From_Id", "Seq_Num",
    "RSSI_dBm", "SNR_dB", "Hop_Limit", "Status_Hex", "Content_Details"
]

def init_csv_log():
    """CSV 로그 파일 생성 및 헤더 초기화"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        print(f"✓ [{LOG_FILE}] 로그 파일이 새로 생성되었습니다.")

def parse_bitfield_payload(payload_bytes):
    """5바이트 압축 비트필드 패킷 디코더 (이슈 #5, node_packet_spec.md 기준)"""
    if len(payload_bytes) < 5:
        return None

    # Byte 0-1: Node ID (2byte Big-Endian)
    app_node_id = (payload_bytes[0] << 8) | payload_bytes[1]

    # Byte 2: Sequence Number (0~255 순환)
    seq_num = payload_bytes[2]

    # Byte 3: Status Bitfield (8개 비트 플래그)
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

    event_str = ", ".join(events) if events else "정상(NORMAL)"

    # Byte 4: Severity(상위 4비트) | Battery(하위 4비트)
    byte4 = payload_bytes[4]
    severity      = (byte4 >> 4) & 0x0F
    battery_level = byte4 & 0x0F

    return {
        "app_node_id":   f"0x{app_node_id:04X}",
        "seq_num":       seq_num,
        "bitfield_hex":  f"0x{bitfield:02X}",
        "events":        event_str,
        "severity":      severity,
        "battery_level": battery_level,
    }

def on_receive_packet(packet, interface):
    """M3 수신기 전파 수신 이벤트 콜백 함수 (5바이트 비상 패킷 전용)"""
    try:
        rx_time = time.strftime('%Y-%m-%d %H:%M:%S')

        # 발신 메쉬 노드 ID 획득
        from_id_str = packet.get('fromId')
        from_num    = packet.get('from')
        from_id     = from_id_str if from_id_str else (f"!{from_num:08x}" if from_num is not None else "Unknown")

        rx_snr    = packet.get('rxSnr', 0.0)
        rx_rssi   = packet.get('rxRssi', 0)
        hop_limit = packet.get('hopLimit', 0)

        # 수신 데이터 파싱
        decoded_data = packet.get('decoded', {})
        portnum      = decoded_data.get('portnum', 'UNKNOWN')
        payload      = decoded_data.get('payload')

        app_id_val     = "N/A"
        seq_val        = "N/A"
        hex_val        = "N/A"
        content_detail = "ROUTING_PACKET"

        print(f"\n[🚨 무선 신호 수신 - {rx_time}]")
        print(f" ├─ 발신 메쉬 ID : {from_id}")

        # 커스텀 5바이트 비상 상태 패킷 처리 (node_packet_spec.md 기준)
        if isinstance(payload, bytes) and len(payload) >= 5:
            decoded_info = parse_bitfield_payload(payload)
            if decoded_info:
                app_id_val     = decoded_info['app_node_id']
                seq_val        = decoded_info['seq_num']
                hex_val        = decoded_info['bitfield_hex']
                content_detail = f"EVENT: {decoded_info['events']}"

                print(f" ├─ 발신 노드 앱 ID : {app_id_val} (Seq #{seq_val})")
                print(f" ├─ 상태 비트필드   : {hex_val}")
                print(f" ├─ 비상 감지 이벤트: {decoded_info['events']}")
                print(f" ├─ 심각도 레벨     : {decoded_info['severity']} / 배터리 단계: {decoded_info['battery_level']}")
        else:
            # 5바이트 미만이거나 페이로드 없음 → 네트워크 관리/라우팅 패킷으로 분류
            print(f" ├─ 데이터 구분    : 네트워크 관리/라우팅 패킷 ({portnum})")

        print(f" └─ 수신 통신 품질 : RSSI = {rx_rssi} dBm | SNR = {rx_snr} dB | Hop = {hop_limit}")

        # CSV 파일 로깅 (이슈 #6)
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                rx_time, app_id_val, from_id, seq_val,
                rx_rssi, rx_snr, hop_limit, hex_val, content_detail
            ])

    except Exception as e:
        print(f"[ERROR] 패킷 파싱 중 오류 발생: {e}")

# meshtastic.receive 이벤트 구독
pub.subscribe(on_receive_packet, "meshtastic.receive")

if __name__ == "__main__":
    print("==================================================")
    print(" 📡 캡스톤 디자인 게이트웨이 수신 관제 시스템 (M2)")
    print("==================================================")

    init_csv_log()

    try:
        interface = meshtastic.serial_interface.SerialInterface(devPath='COM6')
        print("✓ M3 게이트웨이 수신기 연결 성공! 실시간 노드 수신 대기 중... (종료: Ctrl+C)\n")

=======
"""
gateway_receiver.py — 게이트웨이 수신 스크립트

[Issue #2] 시리얼 연결 확인 단계 (뼈대)
  다음 이슈에서 확장:
    #4 수신 콜백  /  #5 비트필드 디코더  /  #6 CSV 로깅  /  #7 중복 Drop

사용법:
    python gateway_receiver.py            # 포트 자동 탐지
    python gateway_receiver.py COM6       # 포트 직접 지정 (Windows)
    python gateway_receiver.py /dev/ttyACM0   # (Linux)
"""
import sys
import time

import meshtastic
import meshtastic.serial_interface


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    interface = None

    print("==================================================")
    print(" 📡 캡스톤 디자인 게이트웨이 수신 관제 시스템 가동")
    print("==================================================")

    try:
        # USB 연결된 게이트웨이 노드 자동/지정 연결
        interface = meshtastic.serial_interface.SerialInterface(devPath=port)

        node_num = getattr(getattr(interface, "myInfo", None), "my_node_num", "N/A")
        print(f"✓ 게이트웨이 수신기 연결 성공  (myNodeNum: {node_num})")
        print("  노드 신호 수신 대기 중... (종료: Ctrl + C)\n")

        # 수신 대기 루프 — 없으면 프로그램이 즉시 종료됨

        while True:
            time.sleep(1)

    except KeyboardInterrupt:


