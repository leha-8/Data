"""
SOAR Integration Configuration Module
Loads settings from environment variables and .env file using Pydantic Settings.
"""

import json
from typing import List, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Webhook Server Settings
    APP_NAME: str = "SOAR Webhook Receiver"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Optional secret token expected in X-Webhook-Secret header")
    DEBUG: bool = False

    # SIEM Severity Thresholds
    WAZUH_MIN_LEVEL: int = Field(default=7, description="Wazuh rule level >= this value triggers SOAR response (7-16)")
    SPLUNK_TRIGGER_SEVERITIES: List[str] = ["high", "critical", "urgent", "fatal"]

    # GitHub Integration
    GITHUB_TOKEN: str = Field(default="", description="Personal Access Token with repo and workflow permissions")
    GITHUB_REPOSITORY: str = Field(default="leha-8/Data", description="Format: owner/repo")
    GITHUB_SOC_ASSIGNEES_INPUT: str = Field(default="leha-8", validation_alias="GITHUB_SOC_ASSIGNEES", description="Comma-separated or JSON list of SOC GitHub usernames")
    GITHUB_WORKFLOW_FILE: str = Field(default="isolate-host.yml", description="Filename of the GitHub Actions workflow")
    GITHUB_WORKFLOW_REF: str = Field(default="main", description="Branch or tag on which to trigger the workflow")

    # Ruijie Switch/Gateway Settings
    RUIJIE_HOST: str = Field(default="192.168.1.2", description="IP address of Ruijie switch/gateway")
    RUIJIE_USERNAME: str = Field(default="admin", description="SSH username for Ruijie")
    RUIJIE_PASSWORD: str = Field(default="", description="SSH password for Ruijie")
    RUIJIE_SECRET: str = Field(default="", description="Enable password for Ruijie privileged EXEC mode")
    RUIJIE_SSH_PORT: int = Field(default=22, description="SSH port for Ruijie")
    RUIJIE_ACL_NAME: str = Field(default="ACL_SOAR_BLOCK", description="Extended ACL name used to block malicious IPs")
    RUIJIE_VLAN_INTERFACE: str = Field(default="GigabitEthernet 0/1", description="Default interface/VLAN where ACL is applied")

    # DrayTek Vigor Router Settings
    DRAYTEK_HOST: str = Field(default="192.168.1.1", description="IP address of DrayTek Vigor router")
    DRAYTEK_USERNAME: str = Field(default="admin", description="SSH username for DrayTek Vigor")
    DRAYTEK_PASSWORD: str = Field(default="", description="SSH password for DrayTek Vigor")
    DRAYTEK_SSH_PORT: int = Field(default=22, description="SSH port for DrayTek Vigor")
    DRAYTEK_FILTER_SET: int = Field(default=2, description="Firewall Filter Set index (default: Set 2)")
    DRAYTEK_FILTER_RULE: int = Field(default=2, description="Firewall Filter Rule index within set")

    # Global Isolation Defaults
    DEFAULT_DEVICE_TARGET: str = Field(default="all", description="Target devices: 'all', 'ruijie', or 'draytek'")
    DRY_RUN: bool = Field(default=False, description="When True, simulate commands without writing to network devices")

    @property
    def GITHUB_SOC_ASSIGNEES(self) -> List[str]:
        raw = self.GITHUB_SOC_ASSIGNEES_INPUT.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
        return [x.strip() for x in raw.split(",") if x.strip()]


settings = Settings()
