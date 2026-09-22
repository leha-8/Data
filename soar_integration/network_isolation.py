"""
Network Isolation Script for SOAR Incident Response
Supports Ruijie Switch/Gateway and DrayTek Vigor Routers via SSH (Netmiko).
Can be executed as a CLI command or imported as a Python module.
"""

import sys
import os
import argparse
import logging
import asyncio
from typing import Dict, Any, List, Optional

# Ensure current directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("soar.isolation")


def block_ip_ruijie(
    target_ip: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    secret: Optional[str] = None,
    port: Optional[int] = None,
    acl_name: Optional[str] = None,
    interface: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Connects to Ruijie Switch/Gateway via SSH and applies ACL rule to block target IP.
    """
    host = host or settings.RUIJIE_HOST
    username = username or settings.RUIJIE_USERNAME
    password = password or settings.RUIJIE_PASSWORD
    secret = secret or settings.RUIJIE_SECRET
    port = port or settings.RUIJIE_SSH_PORT
    acl_name = acl_name or settings.RUIJIE_ACL_NAME
    interface = interface or settings.RUIJIE_VLAN_INTERFACE

    result = {
        "device": "Ruijie Switch/Gateway",
        "host": host,
        "target_ip": target_ip,
        "success": False,
        "logs": []
    }

    # Configuration commands sequence for Ruijie RGOS
    # 1. Define extended ACL with deny rule for source host
    # 2. Permit all other traffic to avoid blocking legitimate communication
    # 3. Apply ACL on target interface in inbound direction
    # 4. Save running-config to startup-config
    commands = [
        f"ip access-list extended {acl_name}",
        f"deny ip host {target_ip} any",
        "permit ip any any",
        "exit",
        f"interface {interface}",
        f"ip access-group {acl_name} in",
        "exit",
        "write memory"
    ]

    result["logs"].append(f"Targeting Ruijie device at {host}:{port} with ACL '{acl_name}' on interface '{interface}'")

    if dry_run or settings.DRY_RUN:
        result["logs"].append("[DRY-RUN] Simulating Ruijie configuration commands:")
        for cmd in commands:
            result["logs"].append(f"  > {cmd}")
        result["success"] = True
        result["dry_run"] = True
        logger.info(f"[Ruijie DRY-RUN] Would block {target_ip} on {host}")
        return result

    try:
        from netmiko import ConnectHandler
    except ImportError:
        err = "netmiko library is not installed. Please run: pip install netmiko"
        result["logs"].append(f"Error: {err}")
        logger.error(err)
        return result

    device_params = {
        "device_type": "ruijie_os",
        "host": host,
        "username": username,
        "password": password,
        "secret": secret,
        "port": port,
        "timeout": 20,
        "global_delay_factor": 1.5
    }

    try:
        logger.info(f"Connecting to Ruijie device at {host}:{port}...")
        with ConnectHandler(**device_params) as net_connect:
            if secret:
                net_connect.enable()

            result["logs"].append(f"Successfully connected to Ruijie prompt: {net_connect.find_prompt()}")
            
            output = net_connect.send_config_set(commands)
            result["logs"].append("CLI Output:\n" + output)

            result["success"] = True
            logger.info(f"Successfully blocked {target_ip} on Ruijie {host}")

    except Exception as e:
        error_msg = f"Failed to configure Ruijie device: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result["logs"].append(error_msg)
        result["success"] = False

    return result


def block_ip_draytek(
    target_ip: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    port: Optional[int] = None,
    filter_set: Optional[int] = None,
    filter_rule: Optional[int] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Connects to DrayTek Vigor Router via SSH and configures Firewall IP Filter rule.
    """
    host = host or settings.DRAYTEK_HOST
    username = username or settings.DRAYTEK_USERNAME
    password = password or settings.DRAYTEK_PASSWORD
    port = port or settings.DRAYTEK_SSH_PORT
    f_set = filter_set or settings.DRAYTEK_FILTER_SET
    f_rule = filter_rule or settings.DRAYTEK_FILTER_RULE

    result = {
        "device": "DrayTek Vigor Router",
        "host": host,
        "target_ip": target_ip,
        "success": False,
        "logs": []
    }

    # DrayTek Vigor CLI syntax for IP Filter Rule configuration:
    # 'ip filter <set_index> <rule_index> [options]'
    commands = [
        f"ip filter {f_set} {f_rule} enable",
        f"ip filter {f_set} {f_rule} name SOAR_BLOCK_{target_ip.replace('.', '_')}",
        f"ip filter {f_set} {f_rule} action block",
        f"ip filter {f_set} {f_rule} dir in",
        f"ip filter {f_set} {f_rule} srcip {target_ip}",
        f"ip filter {f_set} {f_rule} dstip any",
        "sys commit"
    ]

    result["logs"].append(f"Targeting DrayTek Vigor device at {host}:{port} on Filter Set {f_set}, Rule {f_rule}")

    if dry_run or settings.DRY_RUN:
        result["logs"].append("[DRY-RUN] Simulating DrayTek Vigor configuration commands:")
        for cmd in commands:
            result["logs"].append(f"  > {cmd}")
        result["success"] = True
        result["dry_run"] = True
        logger.info(f"[DrayTek DRY-RUN] Would block {target_ip} on {host}")
        return result

    try:
        from netmiko import ConnectHandler
    except ImportError:
        err = "netmiko library is not installed. Please run: pip install netmiko"
        result["logs"].append(f"Error: {err}")
        logger.error(err)
        return result

    # DrayTek Vigor supports SSH shell
    device_params = {
        "device_type": "draytek_vigor",
        "host": host,
        "username": username,
        "password": password,
        "port": port,
        "timeout": 20,
        "global_delay_factor": 1.5
    }

    try:
        logger.info(f"Connecting to DrayTek Vigor router at {host}:{port}...")
        with ConnectHandler(**device_params) as net_connect:
            result["logs"].append(f"Successfully connected to DrayTek prompt: {net_connect.find_prompt()}")
            
            for cmd in commands:
                out = net_connect.send_command(cmd)
                result["logs"].append(f"{cmd} -> {out}")

            result["success"] = True
            logger.info(f"Successfully blocked {target_ip} on DrayTek {host}")

    except Exception as e:
        error_msg = f"Failed to configure DrayTek device: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result["logs"].append(error_msg)
        result["success"] = False

    return result


def unblock_ip_ruijie(
    target_ip: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    secret: Optional[str] = None,
    port: Optional[int] = None,
    acl_name: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Removes the deny rule for target IP from Ruijie ACL.
    """
    host = host or settings.RUIJIE_HOST
    username = username or settings.RUIJIE_USERNAME
    password = password or settings.RUIJIE_PASSWORD
    secret = secret or settings.RUIJIE_SECRET
    port = port or settings.RUIJIE_SSH_PORT
    acl_name = acl_name or settings.RUIJIE_ACL_NAME

    commands = [
        f"ip access-list extended {acl_name}",
        f"no deny ip host {target_ip} any",
        "exit",
        "write memory"
    ]

    result = {
        "device": "Ruijie Switch/Gateway",
        "action": "unblock",
        "target_ip": target_ip,
        "success": False,
        "logs": []
    }

    if dry_run or settings.DRY_RUN:
        result["logs"].append("[DRY-RUN] Simulating Ruijie unblock commands:")
        for cmd in commands:
            result["logs"].append(f"  > {cmd}")
        result["success"] = True
        return result

    from netmiko import ConnectHandler
    device_params = {
        "device_type": "ruijie_os",
        "host": host,
        "username": username,
        "password": password,
        "secret": secret,
        "port": port,
        "timeout": 20
    }

    try:
        with ConnectHandler(**device_params) as net_connect:
            if secret:
                net_connect.enable()
            output = net_connect.send_config_set(commands)
            result["logs"].append("CLI Output:\n" + output)
            result["success"] = True
    except Exception as e:
        result["logs"].append(str(e))
        result["success"] = False

    return result


def execute_isolation(
    target_ip: str,
    device_target: str = "all",
    reason: str = "SOAR Automated Incident Remediation",
    issue_number: Optional[int] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Orchestrates the isolation on requested device targets.
    """
    logger.info(f"Initiating network isolation for IP: {target_ip} (Target: {device_target}, Reason: {reason})")
    results = {}

    if device_target in ("all", "ruijie"):
        results["ruijie"] = block_ip_ruijie(target_ip=target_ip, dry_run=dry_run)

    if device_target in ("all", "draytek"):
        results["draytek"] = block_ip_draytek(target_ip=target_ip, dry_run=dry_run)

    # If an issue_number was provided, post a comment with execution results
    if issue_number and settings.GITHUB_TOKEN:
        try:
            from github_client import github_client
            
            status_emoji = "✅" if all(r.get("success") for r in results.values()) else "⚠️"
            comment_lines = [
                f"### {status_emoji} Kết Quả Thực Thi Kịch Bản Cô Lập Mạng (SOAR Isolation)",
                f"- **Mục tiêu cô lập (Target IP)**: `{target_ip}`",
                f"- **Lý do**: {reason}",
                f"- **Chế độ**: `{'DRY-RUN (Mô phỏng)' if dry_run else 'Thực thi thực tế'}`",
                f"- **Thời gian**: `{settings.APP_NAME}`",
                "",
                "#### Chi tiết thiết bị:"
            ]

            for dev_key, dev_res in results.items():
                dev_status = "Thành công ✅" if dev_res.get("success") else "Thất bại ❌"
                comment_lines.append(f"##### 🖥️ {dev_res.get('device')} ({dev_res.get('host')}): {dev_status}")
                comment_lines.append("```text")
                comment_lines.extend(dev_res.get("logs", []))
                comment_lines.append("```")

            comment_body = "\n".join(comment_lines)
            asyncio.run(github_client.add_issue_comment(issue_number, comment_body))
            logger.info(f"Posted execution comment to GitHub Issue #{issue_number}")
        except Exception as e:
            logger.error(f"Failed to post result comment to GitHub Issue #{issue_number}: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="SOAR Network Isolation CLI Tool (Ruijie & DrayTek)")
    parser.add_argument("--ip", required=True, help="Malicious or compromised IP address to isolate")
    parser.add_argument(
        "--target",
        choices=["all", "ruijie", "draytek"],
        default="all",
        help="Device targets to apply isolation rules to (default: all)"
    )
    parser.add_argument("--reason", default="SOAR Automated Remediation", help="Reason for isolation")
    parser.add_argument("--issue", type=int, default=None, help="GitHub Issue number to comment results on")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without sending changes to hardware")
    parser.add_argument("--unblock", action="store_true", help="Remove isolation block rule instead of applying")

    args = parser.parse_args()

    if args.unblock:
        logger.info(f"Unblocking IP: {args.ip}")
        if args.target in ("all", "ruijie"):
            res = unblock_ip_ruijie(args.ip, dry_run=args.dry_run)
            print("Ruijie Unblock Result:", res)
    else:
        results = execute_isolation(
            target_ip=args.ip,
            device_target=args.target,
            reason=args.reason,
            issue_number=args.issue,
            dry_run=args.dry_run
        )
        print("\n=== ISOLATION EXECUTION SUMMARY ===")
        for key, val in results.items():
            print(f"[{key.upper()}] Success: {val.get('success')}")
            for log_line in val.get("logs", []):
                print(f"  {log_line}")


if __name__ == "__main__":
    main()
