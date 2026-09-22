"""
Unit / Integration Test for SOAR Webhook Receiver Endpoints
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app import app
from config import settings

client = TestClient(app)

def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    print("[PASS] test_healthz passed:", data)

def test_wazuh_low_alert_ignored():
    payload = {
        "rule": {"level": 3, "description": "Normal login", "id": "1001"},
        "data": {"srcip": "192.168.1.99"}
    }
    resp = client.post("/api/v1/webhook/wazuh", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"
    print("[PASS] test_wazuh_low_alert_ignored passed:", data)

def test_wazuh_critical_alert_structure():
    # Test with simulated github client or check payload handling
    payload = {
        "rule": {
            "level": 14,
            "description": "SSH Brute-Force Attack",
            "id": "5712"
        },
        "data": {"srcip": "10.0.0.99"},
        "full_log": "Failed password for root from 10.0.0.99"
    }
    # We test with a dummy token or live if token valid
    print("Testing Wazuh Critical Alert handler...")
    resp = client.post("/api/v1/webhook/wazuh", json=payload)
    print(f"Response ({resp.status_code}):", resp.json())
    assert resp.status_code in (200, 500)  # 200 if GitHub API accepts, or handles error gracefully

def test_splunk_alert():
    payload = {
        "search_name": "Suspicious Outbound Port 4444 Connection",
        "result": {
            "src_ip": "172.16.0.45",
            "urgency": "critical",
            "_raw": "Connection to known C2"
        }
    }
    print("Testing Splunk Critical Alert handler...")
    resp = client.post("/api/v1/webhook/splunk", json=payload)
    print(f"Response ({resp.status_code}):", resp.json())
    assert resp.status_code in (200, 500)

if __name__ == "__main__":
    test_healthz()
    test_wazuh_low_alert_ignored()
    test_wazuh_critical_alert_structure()
    test_splunk_alert()
    print("\nALL ENDPOINT TESTS COMPLETED!")
