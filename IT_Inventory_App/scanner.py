# -*- coding: utf-8 -*-
import multiprocessing
import re
import socket
import ipaddress
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Đặt ngay dưới các câu lệnh import ở đầu file scanner.py
if __name__ == "__main__":
    multiprocessing.freeze_support()

# Danh mục các cơ sở / chi nhánh cấu hình sẵn
PRECONFIGURED_SITES = [
    {
        "name": "Trụ sở chính (Bình Hưng)",
        "subnet": "192.168.1.0/24",
        "description": "Văn phòng trung tâm, tòa nhà điều hành chính"
    },
    {
        "name": "Dãy IP BH",
        "subnet": "192.168.2.0/24",
        "description": "Trung tâm R&D & Phòng Lab thiết bị thử nghiệm"
    },
    {
        "name": "Dãy IP BH",
        "subnet": "192.168.3.0/24",
        "description": "Văn phòng đại diện miền Trung"
    },
    {
        "name": "Dãy IP BH",
        "subnet": "192.168.1.0/24",
        "description": "Chi nhánh miền Nam & Kho trung chuyển"
    },
    {
        "name": "Data Center / Server Room",
        "subnet": "10.10.0.0/24",
        "description": "Hạ tầng Core Switch, Firewall & Server vật lý"
    }
]

# Bảng tra cứu Vendor phổ biến qua MAC prefix (OUI)
OUI_VENDOR_MAP = {
    "00-50-7f": "DrayTek Corp",
    "14-49-bc": "Huawei Technologies",
    "00-1d-aa": "Ruijie Networks",
    "70-a8-e3": "Ruijie Networks",
    "2c-fd-ab": "Ruijie Networks",
    "4e-7e-c8": "Realtek / Network NIC",
    "7c-01-3e": "Espressif IoT / Smart Device",
    "60-1a-c7": "Espressif IoT",
    "00-08-e3": "Cisco Systems",
    "00-1b-d4": "Cisco Systems",
    "00-24-97": "Cisco Systems",
    "f4-0f-1b": "Cisco Systems",
    "00-09-0f": "Fortinet Inc",
    "70-4c-a5": "Fortinet Inc",
    "04-18-d6": "Ubiquiti Networks (UniFi)",
    "24-a4-3c": "Ubiquiti Networks (UniFi)",
    "b4-fb-e4": "Ubiquiti Networks (UniFi)",
    "00-0c-42": "MikroTik RouterBOARD",
    "48-8f-5a": "MikroTik",
    "00-1e-58": "D-Link Systems",
    "14-d6-4d": "D-Link Systems",
    "00-26-88": "TP-Link Technologies",
    "50-c7-bf": "TP-Link Technologies",
    "c0-06-c3": "TP-Link Technologies",
    "00-11-32": "Synology NAS",
    "00-1d-72": "QNAP Systems",
    "b8-27-eb": "Raspberry Pi",
    "dc-a6-32": "Raspberry Pi",
    "e4-5f-01": "Raspberry Pi",
    "00-0c-29": "VMware Virtual Platform",
    "00-15-5d": "Microsoft Hyper-V / Virtual",
    "d8-bb-c1": "Apple Inc",
    "f0-18-98": "Apple Inc",
    "3c-22-fb": "Apple Inc",
    "a4-83-e7": "Apple Inc"
}

COMMON_PORTS = [
    (80, "HTTP"),
    (443, "HTTPS"),
    (22, "SSH"),
    (23, "Telnet"),
    (8080, "HTTP-Alt"),
    (445, "SMB")
]

def get_local_ip():
    """Lấy địa chỉ IP card mạng đang kết nối Internet/LAN của máy tính."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_network_info():
    """Tự động phát hiện dải Card Wi-Fi cho mục a và dải tổng cho mục b."""
    current_ip = get_local_ip()
    
    # Mục a: Tự động tính Subnet thực tế của Card mạng/Wi-Fi đang kết nối (/24)
    try:
        if current_ip != "127.0.0.1":
            net = ipaddress.ip_network(f"{current_ip}/255.255.255.0", strict=False)
            suggested_subnet = str(net)
        else:
            suggested_subnet = "192.168.1.0/24"
    except Exception:
        suggested_subnet = "192.168.1.0/24"

    # Mục b: Chọn duy nhất tùy chọn Quét Toàn Bộ Mạng (192.168.0.0/20)
    preconfigured_sites = [
        {"name": "Toàn hệ thống mạng (192.168.0.0/20)", "subnet": "192.168.0.0/20"}
    ]

    return {
        "current_ip": current_ip,
        "suggested_subnet": suggested_subnet,
        "preconfigured_sites": preconfigured_sites
    }

    return {
        "current_ip": current_ip,
        "suggested_subnet": suggested_subnet,
        "preconfigured_sites": preconfigured_sites
    }

def get_vendor_from_mac(mac):
    """Tra cứu nhà sản xuất từ địa chỉ MAC."""
    if not mac:
        return "Không xác định"
    mac_clean = mac.lower().replace(":", "-")
    prefix = mac_clean[:8]
    return OUI_VENDOR_MAP.get(prefix, "Thiết bị mạng (Chưa nhận dạng hãng)")

def infer_device_type(vendor, open_ports, hostname=""):
    """Dự đoán loại thiết bị dựa vào Vendor, cổng mở và Hostname."""
    vendor_lower = vendor.lower()
    host_lower = hostname.lower()

    if "draytek" in vendor_lower or "draytek" in host_lower:
        return "Router Gateway"
    if "ruijie" in vendor_lower:
        if 23 in open_ports or 22 in open_ports:
            return "Core Switch"
        return "Wi-Fi Access Point"
    if "fortinet" in vendor_lower or "fortigate" in host_lower:
        return "Tường lửa (Firewall)"
    if "cisco" in vendor_lower:
        return "Core Switch"
    if "unifi" in vendor_lower or "ubiquiti" in vendor_lower:
        return "Wi-Fi Access Point"
    if "mikrotik" in vendor_lower:
        return "Router Gateway"
    if "synology" in vendor_lower or "qnap" in vendor_lower:
        return "Máy chủ / NAS"
    if 445 in open_ports:
        return "Máy tính / Máy chủ"
    if 80 in open_ports or 443 in open_ports or 8080 in open_ports:
        if 22 in open_ports or 23 in open_ports:
            return "Router / Switch Quản lý"
        return "Thiết bị Web / Router / Camera"
    
    return "Thiết bị mạng LAN"

def ping_host(ip, timeout_ms=200):
    """Ping kiểm tra 1 IP trên hệ thống Windows."""
    try:
        res = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return (str(ip), res.returncode == 0)
    except Exception:
        return (str(ip), False)

def scan_ports(ip, timeout_s=0.12):
    """Quét nhanh các cổng dịch vụ quản trị cơ bản."""
    open_ports = []
    for port, name in COMMON_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_s)
        try:
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
        except Exception:
            pass
        finally:
            s.close()
    return open_ports

def read_arp_table():
    """Đọc bảng ARP cache trên Windows để lấy cặp IP -> MAC."""
    arp_map = {}
    try:
        # Chạy trực tiếp qua danh sách tham số để không thông qua shell CMD
        out_bytes = subprocess.check_output(["arp", "-a"], stderr=subprocess.DEVNULL)
        out = out_bytes.decode("utf-8", errors="ignore")
        matches = re.findall(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s+([0-9a-fA-F\-]{17})\s+dynamic", out)
        for ip, mac in matches:
            arp_map[ip] = mac.upper()
    except Exception:
        pass
    return arp_map

def inspect_single_host(ip, arp_map, inv_map_by_sn, inventory_items, local_ip):
    """Kiểm tra chi tiết cổng dịch vụ, loại thiết bị và đối chiếu kho cho 1 IP."""
    mac = arp_map.get(ip, "")
    vendor = get_vendor_from_mac(mac)
    open_ports = scan_ports(ip)
    
    hostname = ""
    if ip == local_ip:
        hostname = socket.gethostname()

    suggested_type = infer_device_type(vendor, open_ports, hostname)

    # Đối chiếu xem thiết bị này đã có trong kho chưa
    in_inventory = False
    matched_item = None

    if mac and mac in inv_map_by_sn:
        in_inventory = True
        matched_item = inv_map_by_sn[mac]
    elif mac and mac.replace("-", ":") in inv_map_by_sn:
        in_inventory = True
        matched_item = inv_map_by_sn[mac.replace("-", ":")]
    
    if not in_inventory and inventory_items:
        for it in inventory_items:
            notes = (it.get("notes") or "").lower()
            sn = (it.get("serial_number") or "").lower()
            if ip.lower() in notes or ip.lower() in sn:
                in_inventory = True
                matched_item = it
                break

    return {
        "ip": ip,
        "mac": mac or "—",
        "vendor": vendor,
        "hostname": hostname or "—",
        "open_ports": open_ports,
        "suggested_type": suggested_type,
        "in_inventory": in_inventory,
        "matched_item": {
            "id": matched_item["id"],
            "name": matched_item["name"],
            "site_name": matched_item.get("site_name", "Trụ sở chính")
        } if matched_item else None
    }

def scan_subnet(subnet_str, max_threads=75, inventory_items=None, site_name=""):
    """
    Quét toàn bộ dải mạng LAN:
    """
    # Tự động quét thêm dải phụ 200.x nếu chọn cơ sở TPTD-TML
    if "TPTD-TML" in site_name.upper() and "192.168.200.0/24" not in subnet_str:
        subnet_str = f"{subnet_str}, 192.168.200.0/24"

    subnet_str = subnet_str.strip()
    if "/" not in subnet_str:
        subnet_str = f"{subnet_str}/24"

    try:
        network = ipaddress.ip_network(subnet_str, strict=False)
    except Exception as e:
        raise ValueError(f"Dải IP '{subnet_str}' không hợp lệ: {e}")

    if network.num_addresses > 8192:
        raise ValueError(f"Dải mạng '{subnet_str}' quá lớn ({network.num_addresses} địa chỉ). Vui lòng quét dải /24 hoặc /23 để đảm bảo tốc độ phản hồi nhanh.")

    hosts = list(network.hosts())
    total_hosts = len(hosts)
    local_ip = get_local_ip()

    # Bước 1: Ping đa luồng kiểm tra host còn sống
    alive_hosts = set()
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        results = executor.map(ping_host, hosts)
        for ip, is_alive in results:
            if is_alive:
                alive_hosts.add(ip)

    # Bước 2: Đọc bảng ARP sau khi ping
    arp_map = read_arp_table()

    # Bổ sung những IP có trong ARP thuộc dải mạng
    for ip, mac in arp_map.items():
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj in network and ip != str(network.broadcast_address) and ip != str(network.network_address):
                alive_hosts.add(ip)
        except Exception:
            pass

    sorted_ips = sorted(list(alive_hosts), key=lambda x: [int(part) for part in x.split(".")])

    # Bước 3: Thu thập thông tin chi tiết đa luồng cho các IP còn sống
    inv_map_by_sn = {}
    if inventory_items:
        for it in inventory_items:
            sn = (it.get("serial_number") or "").strip().upper()
            if sn:
                inv_map_by_sn[sn] = it

    devices = []
    with ThreadPoolExecutor(max_workers=min(25, max(len(sorted_ips), 1))) as executor:
        futures = [
            executor.submit(inspect_single_host, ip, arp_map, inv_map_by_sn, inventory_items, local_ip)
            for ip in sorted_ips
        ]
        for f in futures:
            try:
                dev = f.result()
                if dev and "ip" in dev:
                    ip_str = dev["ip"]
                    try:
                        third_octet = int(ip_str.split('.')[2])
                        if ip_str.startswith("192.168.200.") or (8 <= third_octet <= 15):
                            dev["site_name"] = "TPTD-TML"
                    except Exception:
                        pass
                devices.append(dev)
            except Exception:
                pass

    # Sắp xếp lại theo địa chỉ IP
    devices.sort(key=lambda d: [int(p) for p in d["ip"].split(".")])

    return {
        "subnet": str(network),
        "total_hosts": total_hosts,
        "alive_count": len(devices),
        "devices": devices
    }