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
        print("\n사용자 종료 요청. 수신기를 닫습니다.")
    except Exception as e:
        print(f"X 게이트웨이 시리얼 포트 연결 실패: {e}")
        sys.exit(1)
    finally:
        if interface is not None:
            interface.close()


if __name__ == "__main__":
    main()