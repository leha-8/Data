"""
Alert Simulation Script for SOAR Webhook Testing
Simulates incoming security alerts from Wazuh SIEM and Splunk to verify end-to-end automation.
"""

import argparse
import json
import httpx
from datetime import datetime, timezone


def send_wazuh_critical(base_url: str, secret: str = ""):
    print("\n[+] Đang gửi cảnh báo WAZUH MỨC ĐỘ CRITICAL (Rule level 14 - Phát hiện tấn công Brute-force)...")
    url = f"{base_url}/api/v1/webhook/wazuh"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "level": 14,
            "description": "SSHD brute-force attack detected (multiple failed logins followed by success)",
            "id": "5712",
            "firedtimes": 25
        },
        "agent": {
            "id": "003",
            "name": "Production-Database-Server",
            "ip": "192.168.1.100"
        },
        "data": {
            "srcip": "192.168.10.150",
            "srcuser": "root",
            "dstport": "22",
            "protocol": "tcp"
        },
        "full_log": "Sep 22 14:30:00 prod-db sshd[4921]: Failed password for root from 192.168.10.150 port 54321 ssh2\n[ALERT TRIGGERED: 25 attempts in 60s]"
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        print("Response:", json.dumps(resp.json(), indent=2, ensure_ascii=False))


def send_wazuh_low(base_url: str, secret: str = ""):
    print("\n[+] Đang gửi cảnh báo WAZUH MỨC ĐỘ LOW (Rule level 3 - Đăng nhập bình thường)...")
    url = f"{base_url}/api/v1/webhook/wazuh"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "level": 3,
            "description": "Successful SSH login by authorized user",
            "id": "5715"
        },
        "data": {
            "srcip": "192.168.1.50"
        },
        "full_log": "Accepted publickey for user admin from 192.168.1.50 port 50123"
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        print("Response:", json.dumps(resp.json(), indent=2, ensure_ascii=False))


def send_splunk_high(base_url: str, secret: str = ""):
    print("\n[+] Đang gửi cảnh báo SPLUNK MỨC ĐỘ HIGH (Phát hiện kết nối C2 / Rò rỉ dữ liệu)...")
    url = f"{base_url}/api/v1/webhook/splunk"
    payload = {
        "sid": "scheduler__admin__search__RNDS5829104_1727000000.12",
        "search_name": "Potential Data Exfiltration / Cobalt Strike C2 Traffic Detected",
        "severity": "high",
        "result": {
            "_time": datetime.now(timezone.utc).isoformat(),
            "src_ip": "10.10.5.88",
            "dest_ip": "198.51.100.4",
            "bytes_out": "154000000",
            "urgency": "high",
            "_raw": "2026-09-22 14:30:15 src=10.10.5.88 dst=198.51.100.4 bytes_sent=154MB proto=TCP/443 alert=DNS_Tunneling_Exfil"
        }
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        print("Response:", json.dumps(resp.json(), indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="SOAR Alert Simulator for Wazuh and Splunk")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of SOAR Webhook Receiver")
    parser.add_argument("--type", choices=["all", "wazuh-crit", "wazuh-low", "splunk-high"], default="all")
    parser.add_argument("--secret", default="", help="Optional Webhook Secret header")

    args = parser.parse_args()

    if args.type in ("all", "wazuh-low"):
        send_wazuh_low(args.url, args.secret)

    if args.type in ("all", "wazuh-crit"):
        send_wazuh_critical(args.url, args.secret)

    if args.type in ("all", "splunk-high"):
        send_splunk_high(args.url, args.secret)


if __name__ == "__main__":
    main()
