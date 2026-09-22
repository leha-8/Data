"""
SOAR Webhook Receiver Application
FastAPI service listening for security alerts from Wazuh SIEM, Splunk, or custom security tools.
Automates GitHub Incident Issue creation, SOC team assignment, and GitHub Actions isolation workflow dispatch.
"""

import sys
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from github_client import github_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("soar.webhook")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated Incident Response Webhook Receiver for Wazuh, Splunk, and Network Hardware (Ruijie & DrayTek)"
)


class GenericAlertModel(BaseModel):
    title: str = Field(..., example="Brute Force SSH Attack Detected")
    severity: str = Field(..., example="critical", description="low, medium, high, or critical")
    source_ip: str = Field(..., example="192.168.10.150")
    source_system: str = Field(default="Generic SIEM", example="Wazuh / Splunk")
    rule_id: Optional[str] = Field(default=None, example="5710")
    description: Optional[str] = Field(default=None, example="Multiple failed SSH login attempts from host")
    raw_log: Optional[str] = Field(default=None, example="Failed password for invalid user root from 192.168.10.150 port 43210 ssh2")


def verify_webhook_token(x_webhook_secret: Optional[str]):
    """Validates incoming webhook secret token if configured."""
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook request: invalid or missing X-Webhook-Secret header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Secret header."
        )


def build_issue_body(
    alert_title: str,
    severity: str,
    source_ip: str,
    source_system: str,
    rule_id: Optional[str],
    description: Optional[str],
    timestamp: str,
    raw_log: Optional[str]
) -> str:
    """Formats a structured, professional Markdown document for the GitHub Issue."""
    severity_upper = severity.upper()
    severity_badge = "🔴 CRITICAL" if "CRIT" in severity_upper else "🟠 HIGH" if "HIGH" in severity_upper else f"🟡 {severity_upper}"

    body = f"""## 🚨 BÁO CÁO SỰ CỐ BẢO MẬT (SECURITY INCIDENT ALERT)

> **Tự động khởi tạo bởi SOAR Webhook Automation**  
> **Thời gian tiếp nhận**: `{timestamp}`

---

### 📋 Tóm Tắt Sự Cố

| Thông số | Giá trị |
| :--- | :--- |
| **Tên sự cố** | **{alert_title}** |
| **Mức độ nghiêm trọng (Severity)** | **{severity_badge}** |
| **IP Nguồn Nghi Vấn (Compromised/Attacker IP)** | ` {source_ip} ` |
| **Hệ thống cảnh báo (SIEM)** | `{source_system}` |
| **Rule / Alert ID** | `{rule_id or 'N/A'}` |
| **Phụ trách xử lý (SOC Assignee)** | `{', '.join(settings.GITHUB_SOC_ASSIGNEES)}` |

---

### 📝 Chi Tiết Sự Cố
{description or 'Không có mô tả chi tiết từ hệ thống cảnh báo.'}

---

### 🛡️ Hành Động Ứng Phó Tự Động (SOAR Automation Action)
- [x] Đã tạo GitHub Issue theo dõi sự cố.
- [x] Đã gán phân công cho đội ngũ SOC ({', '.join(settings.GITHUB_SOC_ASSIGNEES)}).
- [x] Đã kích hoạt workflow GitHub Actions `isolate-host.yml` để cấu hình cô lập IP trên:
  - **Ruijie Switch/Gateway**: Thêm Access-List (ACL) chặn IP ` {source_ip} `.
  - **DrayTek Vigor Router**: Cấu hình Firewall IP Filter chặn IP ` {source_ip} `.

---

### 🔍 Nhật Ký Cảnh Báo Gốc (Raw SIEM Log)
<details>
<summary><b>Nhấn vào đây để xem chi tiết Raw Log</b></summary>

```json
{raw_log or 'Không có thông tin raw log đính kèm.'}
```
</details>

---
*Ghi chú: Vui lòng theo dõi các comment tự động tiếp theo bên dưới để kiểm tra trạng thái cô lập mạng từ GitHub Actions.*
"""
    return body


async def process_high_severity_incident(
    alert_title: str,
    severity: str,
    source_ip: str,
    source_system: str,
    rule_id: Optional[str],
    description: Optional[str],
    timestamp: str,
    raw_log: Optional[str]
) -> Dict[str, Any]:
    """
    Executes the SOAR pipeline for High/Critical incidents:
    1. Creates GitHub Issue
    2. Dispatches GitHub Actions Workflow `isolate-host.yml`
    """
    issue_title = f"[INCIDENT] - {alert_title}"
    labels = ["incident", "security", f"severity:{severity.lower()}", "soar-automated"]

    issue_body = build_issue_body(
        alert_title=alert_title,
        severity=severity,
        source_ip=source_ip,
        source_system=source_system,
        rule_id=rule_id,
        description=description,
        timestamp=timestamp,
        raw_log=raw_log
    )

    # 1. Create GitHub Issue
    issue_data = await github_client.create_incident_issue(
        title=issue_title,
        body=issue_body,
        labels=labels,
        assignees=settings.GITHUB_SOC_ASSIGNEES
    )

    issue_number = issue_data.get("number")
    issue_url = issue_data.get("html_url")

    # 2. Trigger GitHub Actions Workflow `isolate-host.yml`
    workflow_triggered = False
    try:
        workflow_inputs = {
            "target_ip": source_ip,
            "reason": f"Incident #{issue_number}: {alert_title}",
            "issue_number": str(issue_number),
            "device_target": settings.DEFAULT_DEVICE_TARGET
        }
        workflow_triggered = await github_client.trigger_workflow_dispatch(
            workflow_id=settings.GITHUB_WORKFLOW_FILE,
            ref=settings.GITHUB_WORKFLOW_REF,
            inputs=workflow_inputs
        )
    except Exception as e:
        logger.error(f"Error triggering GitHub Actions workflow: {e}")

    return {
        "status": "incident_created",
        "action_taken": "issue_created_and_isolation_triggered" if workflow_triggered else "issue_created_workflow_failed",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "workflow_triggered": workflow_triggered,
        "isolated_ip": source_ip
    }


@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "repository": settings.GITHUB_REPOSITORY,
        "soc_assignees": settings.GITHUB_SOC_ASSIGNEES,
        "dry_run_mode": settings.DRY_RUN
    }


@app.post("/api/v1/webhook/wazuh")
async def receive_wazuh_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Endpoint receiving alert payloads from Wazuh SIEM Webhook integration.
    """
    verify_webhook_token(x_webhook_secret)
    payload = await request.json()

    # Extract Wazuh alert data
    # Standard Wazuh alert structure: rule, data, agent, timestamp
    rule = payload.get("rule", {})
    rule_level = rule.get("level", 0)
    rule_description = rule.get("description", "Cảnh báo an ninh từ Wazuh")
    rule_id = str(rule.get("id", ""))
    
    # Try finding source IP from common Wazuh locations
    data_section = payload.get("data", {})
    source_ip = (
        data_section.get("srcip")
        or data_section.get("src_ip")
        or data_section.get("win", {}).get("eventdata", {}).get("ipAddress")
        or data_section.get("win", {}).get("eventdata", {}).get("sourceIp")
        or payload.get("agent", {}).get("ip")
        or "0.0.0.0"
    )

    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
    raw_log = payload.get("full_log") or str(payload)

    logger.info(f"Received Wazuh alert: Level={rule_level}, Rule={rule_id} ({rule_description}), IP={source_ip}")

    # Determine severity based on Wazuh rule level
    # Levels 0-3: informational/low; 4-6: medium; 7-11: high; 12+: critical
    if rule_level >= 12:
        severity = "critical"
    elif rule_level >= settings.WAZUH_MIN_LEVEL:
        severity = "high"
    elif rule_level >= 4:
        severity = "medium"
    else:
        severity = "low"

    # Only trigger SOAR automation for High or Critical
    if severity in ("high", "critical"):
        logger.warning(f"High severity Wazuh alert detected (Level {rule_level}). Triggering SOAR incident handling...")
        result = await process_high_severity_incident(
            alert_title=rule_description,
            severity=severity,
            source_ip=source_ip,
            source_system="Wazuh SIEM",
            rule_id=rule_id,
            description=f"Wazuh phát hiện sự cố mức độ {rule_level} (Quy tắc ID {rule_id}): {rule_description}",
            timestamp=timestamp,
            raw_log=raw_log
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    return {
        "status": "ignored",
        "reason": f"Wazuh rule level {rule_level} is below threshold {settings.WAZUH_MIN_LEVEL}",
        "severity": severity
    }


@app.post("/api/v1/webhook/splunk")
async def receive_splunk_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Endpoint receiving alert payloads from Splunk Webhook Alert Action.
    """
    verify_webhook_token(x_webhook_secret)
    payload = await request.json()

    search_name = payload.get("search_name", "Splunk Security Alert")
    result_data = payload.get("result", {})
    
    source_ip = (
        result_data.get("src_ip")
        or result_data.get("client_ip")
        or result_data.get("src")
        or result_data.get("dest_ip")
        or "0.0.0.0"
    )

    severity = (
        result_data.get("urgency")
        or result_data.get("severity")
        or payload.get("severity")
        or "high"
    ).lower()

    timestamp = result_data.get("_time") or datetime.now(timezone.utc).isoformat()
    raw_log = result_data.get("_raw") or str(payload)

    logger.info(f"Received Splunk alert: Search='{search_name}', Severity={severity}, IP={source_ip}")

    if any(s in severity for s in settings.SPLUNK_TRIGGER_SEVERITIES):
        logger.warning(f"High/Critical Splunk alert detected ({severity}). Triggering SOAR incident handling...")
        res = await process_high_severity_incident(
            alert_title=search_name,
            severity=severity,
            source_ip=source_ip,
            source_system="Splunk SIEM",
            rule_id=payload.get("sid", "Splunk Alert"),
            description=f"Splunk phát hiện cảnh báo tương quan bảo mật: {search_name}",
            timestamp=timestamp,
            raw_log=raw_log
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=res)

    return {
        "status": "ignored",
        "reason": f"Splunk severity '{severity}' is not in trigger list",
        "severity": severity
    }


@app.post("/api/v1/webhook/generic")
async def receive_generic_webhook(
    alert: GenericAlertModel,
    x_webhook_secret: Optional[str] = Header(None)
):
    """
    Generic webhook endpoint for custom security tools, honeypots, or testing.
    """
    verify_webhook_token(x_webhook_secret)

    severity = alert.severity.lower()
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"Received generic alert: '{alert.title}', Severity={severity}, IP={alert.source_ip}")

    if severity in ("high", "critical", "urgent"):
        res = await process_high_severity_incident(
            alert_title=alert.title,
            severity=severity,
            source_ip=alert.source_ip,
            source_system=alert.source_system,
            rule_id=alert.rule_id,
            description=alert.description,
            timestamp=timestamp,
            raw_log=alert.raw_log
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=res)

    return {
        "status": "ignored",
        "reason": f"Severity '{severity}' does not meet high/critical requirement",
        "severity": severity
    }


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="SOAR Webhook Receiver Server")
    parser.add_argument("--host", default=settings.HOST, help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"[*] Starting {settings.APP_NAME} on http://{args.host}:{args.port}")
    print(f"[*] Swagger UI documentation at http://{args.host}:{args.port}/docs")
    if args.reload:
        uvicorn.run("app:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)

