// Quản lý ứng dụng IT Inventory & Network Scanner

let currentItemsCache = [];
let itemModalInstance = null;
let txModalInstance = null;
let detectedSubnet = "192.168.1.0/24";
let preconfiguredSitesCache = [];

// Bảng ánh xạ danh sách dải IP cho từng cơ sở (192.168.0.0 -> 192.168.15.0, riêng TML có dải 200)
const SITE_IP_MAPPING = {
    "Q12-LTR": "192.168.0.0/24, 192.168.1.0/24",
    "Q12-HHG": "192.168.2.0/24, 192.168.3.0/24",
    "HBC-BH": "192.168.4.0/24, 192.168.5.0/24",
    "Q12-OHT02": "192.168.6.0/24, 192.168.7.0/24",
    "Q12-LTR2": "192.168.8.0/24",
    "Q12-T7TNG": "192.168.9.0/24, 192.168.10.0/24",
    "Q7-LOT": "192.168.11.0/24, 192.168.12.0/24",
    "QT-TML": "192.168.13.0/24, 192.168.14.0/24, 192.168.200.0/24", // Cơ sở TML bổ sung dải 200
    "Q12-BAG2-LDC": "192.168.15.0/24"
};

document.addEventListener("DOMContentLoaded", () => {
    itemModalInstance = new bootstrap.Modal(document.getElementById("itemModal"));
    txModalInstance = new bootstrap.Modal(document.getElementById("txModal"));

    loadDashboard();
    loadItems();
    loadTransactions();
    loadNetworkInfo();
    loadSitesDropdowns();
});

// Chuyển đổi tab
function switchTab(tabName) {
    const tabs = ["dashboard", "items", "scanner", "transactions", "reports"];
    tabs.forEach(t => {
        const sec = document.getElementById(`section-${t}`);
        const btn = document.getElementById(`tab-${t}-btn`);
        if (sec && btn) {
            if (t === tabName) {
                sec.classList.remove("d-none");
                btn.classList.add("active");
            } else {
                sec.classList.add("d-none");
                btn.classList.remove("active");
            }
        }
    });

    if (tabName === "dashboard") loadDashboard();
    if (tabName === "items") loadItems();
    if (tabName === "scanner") loadNetworkInfo();
    if (tabName === "transactions") loadTransactions();
}

// Toast thông báo
function showToast(message, isError = false) {
    const toastEl = document.getElementById("liveToast");
    const toastMsg = document.getElementById("toastMessage");
    toastMsg.textContent = message;
    toastEl.className = `toast align-items-center text-white border-0 shadow ${isError ? 'bg-danger' : 'bg-success'}`;
    const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
    toast.show();
}

// Định dạng badge trạng thái
function getStatusBadge(status) {
    switch (status) {
        case "Sẵn sàng trong kho":
            return `<span class="badge badge-ready px-2 py-1"><i class="bi bi-check-circle me-1"></i>Sẵn sàng trong kho</span>`;
        case "Đang sử dụng":
            return `<span class="badge badge-inuse px-2 py-1"><i class="bi bi-activity me-1"></i>Đang sử dụng</span>`;
        case "Sắp hết hàng":
            return `<span class="badge badge-lowstock px-2 py-1"><i class="bi bi-exclamation-triangle me-1"></i>Sắp hết hàng</span>`;
        case "Hết hàng":
            return `<span class="badge badge-outstock px-2 py-1"><i class="bi bi-x-circle me-1"></i>Hết hàng</span>`;
        case "Đang bảo hành":
            return `<span class="badge badge-warranty px-2 py-1"><i class="bi bi-shield-exclamation me-1"></i>Đang bảo hành</span>`;
        default:
            return `<span class="badge bg-secondary px-2 py-1">${status}</span>`;
    }
}

// Định dạng badge giao dịch
function getTxBadge(type) {
    switch (type) {
        case "Xuất kho":
            return `<span class="badge badge-tx-out px-2 py-1"><i class="bi bi-arrow-up-right me-1"></i>Xuất kho</span>`;
        case "Nhập kho":
            return `<span class="badge badge-tx-in px-2 py-1"><i class="bi bi-arrow-down-left me-1"></i>Nhập kho</span>`;
        case "Thu hồi":
            return `<span class="badge badge-tx-return px-2 py-1"><i class="bi bi-arrow-repeat me-1"></i>Thu hồi</span>`;
        default:
            return `<span class="badge bg-secondary px-2 py-1">${type}</span>`;
    }
}

// Nạp danh sách các Cơ sở / Chi nhánh cho các dropdown
async function loadSitesDropdowns() {
    try {
        const res = await fetch("/api/sites");
        const sites = await res.json();

        // 1. Dropdown lọc cơ sở ở Danh mục vật tư
        const filterSite = document.getElementById("items-filter-site");
        if (filterSite) {
            const currentVal = filterSite.value;
            filterSite.innerHTML = `<option value="">-- Tất cả cơ sở --</option>`;
            sites.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s;
                opt.textContent = s;
                filterSite.appendChild(opt);
            });
            filterSite.value = currentVal;
        }

        // 2. Dropdown cơ sở ở Modal thêm/sửa item
        const itemSite = document.getElementById("item-site");
        if (itemSite) {
            const currentVal = itemSite.value;
            itemSite.innerHTML = "";
            sites.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s;
                opt.textContent = s;
                itemSite.appendChild(opt);
            });
            if (currentVal) itemSite.value = currentVal;
        }

// 3. Dropdown cơ sở gán cho thiết bị quét được (scanner-target-site)
        const targetSite = document.getElementById("scanner-target-site");
        if (targetSite) {
            const currentVal = targetSite.value;
            targetSite.innerHTML = "";
            sites.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s;
                opt.textContent = s;
                targetSite.appendChild(opt);
            });
            if (currentVal) targetSite.value = currentVal;

            // Sự kiện khi chọn Cơ sở bên phải -> Tự đổi Radio & Nhảy IP bên trái
            targetSite.addEventListener("change", function () {
                const selectedSite = this.value;
                const presetSelect = document.getElementById("scanner-preset-select");
                const customInput = document.getElementById("scanner-custom-input");

                // 1. TỰ TÍCH CHỌN RADIO "b) Dải IP cấu hình sẵn theo Cơ sở"
                const radioPreset = document.getElementById("mode-preset");
                if (radioPreset) {
                    radioPreset.checked = true;
                    // Gọi hàm switch mode của giao diện (nếu có) để mở khóa ô chọn
                    if (typeof selectScanMode === "function") selectScanMode("preset");
                    if (typeof onScanModeChanged === "function") onScanModeChanged();
                }

                // 2. Tự động tìm và chọn đúng Cơ sở ở Dropdown mục b)
                if (presetSelect) {
                    for (let i = 0; i < presetSelect.options.length; i++) {
                        const optText = presetSelect.options[i].text;
                        if (optText.toLowerCase().includes(selectedSite.toLowerCase())) {
                            presetSelect.selectedIndex = i;
                            // Cập nhật Subnet hiển thị bên cạnh
                            if (typeof onPresetSiteSelected === "function") {
                                onPresetSiteSelected();
                            }
                            break;
                        }
                    }
                }

                // 3. Điền sẵn dải IP vào ô "c) Nhập dải IP tùy chỉnh"
                if (typeof preconfiguredSitesCache !== "undefined" && Array.isArray(preconfiguredSitesCache)) {
                    const foundSite = preconfiguredSitesCache.find(site => 
                        site.name.toLowerCase() === selectedSite.toLowerCase() || 
                        selectedSite.toLowerCase().includes(site.name.toLowerCase())
                    );
                    if (foundSite && customInput) {
                        customInput.value = foundSite.subnet;
                    }
                }
            });

            // Kích hoạt ngay lần đầu nạp
            targetSite.dispatchEvent(new Event("change"));
        }
    } catch (err) {
        console.error("Lỗi nạp danh sách cơ sở:", err);
    }
}
// ================= TAB 1: DASHBOARD =================
async function loadDashboard() {
    try {
        const res = await fetch("/api/dashboard");
        const data = await res.json();

        // Cards
        document.getElementById("dash-total-types").textContent = data.total_types;
        document.getElementById("dash-total-quantity").textContent = data.total_quantity;
        document.getElementById("dash-low-stock").textContent = data.low_stock;
        document.getElementById("dash-warranty-count").textContent = data.warranty_count;

        // Low stock items
        const lowStockTbody = document.getElementById("dash-low-stock-body");
        lowStockTbody.innerHTML = "";
        if (data.low_stock_items.length === 0) {
            lowStockTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4"><i class="bi bi-check2-circle text-success fs-4 d-block mb-1"></i>Không có thiết bị nào sắp hết hàng. Kho hàng dồi dào!</td></tr>`;
        } else {
            data.low_stock_items.forEach(it => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td class="fw-semibold text-dark">${escapeHtml(it.name)}</td>
                    <td><span class="badge bg-light text-primary border"><i class="bi bi-building me-1"></i>${escapeHtml(it.site_name || 'Trụ sở chính')}</span></td>
                    <td><span class="badge bg-danger text-white fs-6 fw-bold px-3 py-1">${it.quantity} ${escapeHtml(it.unit)}</span></td>
                    <td class="text-secondary small"><i class="bi bi-geo-alt me-1"></i>${escapeHtml(it.location || 'Chưa xếp vị trí')}</td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-warning text-dark fw-semibold" onclick="quickStockIn(${it.id})">
                            <i class="bi bi-plus-circle me-1"></i>Nhập Thêm
                        </button>
                    </td>
                `;
                lowStockTbody.appendChild(tr);
            });
        }

        // Recent Transactions
        const recentUl = document.getElementById("dash-recent-txs");
        recentUl.innerHTML = "";
        if (data.recent_txs.length === 0) {
            recentUl.innerHTML = `<li class="list-group-item text-center text-muted py-4">Chưa có giao dịch nào được ghi nhận.</li>`;
        } else {
            data.recent_txs.forEach(tx => {
                const li = document.createElement("li");
                li.className = "list-group-item py-3 px-3";
                li.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="fw-semibold text-dark">${escapeHtml(tx.item_name)}</div>
                        ${getTxBadge(tx.type)}
                    </div>
                    <div class="small text-muted mb-1">
                        <span>Số lượng: <strong class="text-dark">${tx.quantity} ${escapeHtml(tx.unit)}</strong></span> |
                        <span>Bàn giao: <strong>${escapeHtml(tx.recipient || 'N/A')}</strong> (${escapeHtml(tx.department || 'N/A')})</span>
                    </div>
                    <div class="small text-secondary d-flex justify-content-between">
                        <span><i class="bi bi-person me-1"></i>${escapeHtml(tx.performer)}</span>
                        <span><i class="bi bi-clock me-1"></i>${escapeHtml(tx.created_at)}</span>
                    </div>
                `;
                recentUl.appendChild(li);
            });
        }

        // Category breakdown
        const catDiv = document.getElementById("dash-category-list");
        catDiv.innerHTML = "";
        data.by_category.forEach(c => {
            const pct = data.total_quantity > 0 ? Math.round((c.total_qty / data.total_quantity) * 100) : 0;
            catDiv.innerHTML += `
                <div class="mb-3">
                    <div class="d-flex justify-content-between small fw-semibold mb-1">
                        <span>${escapeHtml(c.category)} (${c.count} model)</span>
                        <span>${c.total_qty} đơn vị (${pct}%)</span>
                    </div>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar bg-primary" style="width: ${pct}%"></div>
                    </div>
                </div>
            `;
        });

        // Site breakdown
        const siteDiv = document.getElementById("dash-site-list");
        siteDiv.innerHTML = "";
        if (data.by_site) {
            data.by_site.forEach(s => {
                const pct = data.total_quantity > 0 ? Math.round((s.total_qty / data.total_quantity) * 100) : 0;
                siteDiv.innerHTML += `
                    <div class="mb-3">
                        <div class="d-flex justify-content-between small fw-semibold mb-1">
                            <span><i class="bi bi-building me-1 text-primary"></i>${escapeHtml(s.site_name)} (${s.count} model)</span>
                            <span>${s.total_qty} đơn vị (${pct}%)</span>
                        </div>
                        <div class="progress" style="height: 8px;">
                            <div class="progress-bar bg-info" style="width: ${pct}%"></div>
                        </div>
                    </div>
                `;
            });
        }

        // Status breakdown
        const statusDiv = document.getElementById("dash-status-list");
        statusDiv.innerHTML = `<div class="d-flex flex-wrap gap-2">`;
        data.by_status.forEach(s => {
            statusDiv.innerHTML += `
                <div class="p-3 bg-light rounded-3 border flex-grow-1 text-center">
                    <div class="small text-muted mb-1">${getStatusBadge(s.status)}</div>
                    <div class="fs-4 fw-bold text-dark">${s.count}</div>
                    <small class="text-secondary">Chủng loại</small>
                </div>
            `;
        });
        statusDiv.innerHTML += `</div>`;

    } catch (err) {
        console.error("Lỗi nạp dashboard:", err);
    }
}

// ================= TAB 2: DANH MỤC VẬT TƯ =================
async function loadItems() {
    const q = document.getElementById("items-search")?.value || "";
    const site = document.getElementById("items-filter-site")?.value || "";
    const cat = document.getElementById("items-filter-category")?.value || "";
    const st = document.getElementById("items-filter-status")?.value || "";

    const params = new URLSearchParams();
    if (q) params.append("q", q);
    if (site) params.append("site", site);
    if (cat) params.append("category", cat);
    if (st) params.append("status", st);

    // Cập nhật URL xuất Excel cho đúng bộ lọc cơ sở
    const exportBtn = document.getElementById("btn-export-inventory");
    if (exportBtn) {
        exportBtn.href = `/api/export/inventory?${params.toString()}`;
    }

    try {
        const res = await fetch(`/api/items?${params.toString()}`);
        const items = await res.json();
        currentItemsCache = items;

        const tbody = document.getElementById("items-table-body");
        tbody.innerHTML = "";

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-5"><i class="bi bi-search fs-3 d-block mb-2"></i>Không tìm thấy thiết bị nào phù hợp với bộ lọc.</td></tr>`;
            return;
        }

        items.forEach((it, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="text-secondary text-center small">${idx + 1}</td>
                <td>
                    <div class="fw-bold text-dark">${escapeHtml(it.name)}</div>
                    ${it.notes ? `<small class="text-muted text-truncate d-block" style="max-width: 230px;">${escapeHtml(it.notes)}</small>` : ''}
                </td>
                <td><span class="badge bg-light text-dark border">${escapeHtml(it.category)}</span></td>
                <td><span class="badge bg-primary bg-opacity-10 text-primary border border-primary-subtle"><i class="bi bi-building me-1"></i>${escapeHtml(it.site_name || 'Trụ sở chính')}</span></td>
                <td><code class="text-primary small">${escapeHtml(it.serial_number || '—')}</code></td>
                <td class="text-center">
                    <span class="fw-bold fs-6 ${it.quantity <= 2 ? 'text-danger' : 'text-success'}">${it.quantity}</span>
                    <small class="text-muted">${escapeHtml(it.unit)}</small>
                </td>
                <td class="small text-secondary"><i class="bi bi-geo-alt me-1"></i>${escapeHtml(it.location || '—')}</td>
                <td>${getStatusBadge(it.status)}</td>
                <td class="small text-secondary">${escapeHtml(it.warranty_end || '—')}</td>
                <td class="text-end">
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-warning" title="Xuất/Nhập nhanh" onclick="quickStockOut(${it.id})">
                            <i class="bi bi-arrow-left-right"></i>
                        </button>
                        <button class="btn btn-outline-primary" title="Chỉnh sửa" onclick="openEditItemModal(${it.id})">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger" title="Xóa" onclick="confirmDeleteItem(${it.id}, '${escapeHtml(it.name)}')">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Lỗi tải danh mục vật tư:", err);
    }
}

function resetItemsFilter() {
    document.getElementById("items-search").value = "";
    document.getElementById("items-filter-site").value = "";
    document.getElementById("items-filter-category").value = "";
    document.getElementById("items-filter-status").value = "";
    loadItems();
}

// Thêm / Sửa item
function openCreateItemModal() {
    document.getElementById("itemModalTitle").textContent = "Thêm Thiết Bị / Vật Tư Mới";
    document.getElementById("item-id").value = "";
    document.getElementById("itemForm").reset();
    document.getElementById("item-qty").value = 1;
    document.getElementById("item-unit").value = "Cái";
    document.getElementById("item-status").value = "Sẵn sàng trong kho";
    
    // Đặt mặc định cơ sở
    const targetSite = document.getElementById("scanner-target-site")?.value;
    if (targetSite) document.getElementById("item-site").value = targetSite;
    
    itemModalInstance.show();
}

async function openEditItemModal(id) {
    try {
        const res = await fetch(`/api/items/${id}`);
        const it = await res.json();
        document.getElementById("itemModalTitle").textContent = "Chỉnh Sửa Thông Tin Thiết Bị";
        document.getElementById("item-id").value = it.id;
        document.getElementById("item-name").value = it.name;
        document.getElementById("item-category").value = it.category;
        document.getElementById("item-site").value = it.site_name || "Trụ sở chính";
        document.getElementById("item-sn").value = it.serial_number || "";
        document.getElementById("item-qty").value = it.quantity;
        document.getElementById("item-unit").value = it.unit || "Cái";
        document.getElementById("item-location").value = it.location || "";
        document.getElementById("item-status").value = it.status;
        document.getElementById("item-warranty").value = it.warranty_end || "";
        document.getElementById("item-notes").value = it.notes || "";
        itemModalInstance.show();
    } catch (err) {
        showToast("Lỗi khi tải dữ liệu thiết bị: " + err, true);
    }
}

async function submitItemForm(e) {
    e.preventDefault();
    const id = document.getElementById("item-id").value;
    const data = {
        name: document.getElementById("item-name").value,
        category: document.getElementById("item-category").value,
        site_name: document.getElementById("item-site").value,
        serial_number: document.getElementById("item-sn").value,
        quantity: document.getElementById("item-qty").value,
        unit: document.getElementById("item-unit").value,
        location: document.getElementById("item-location").value,
        status: document.getElementById("item-status").value,
        warranty_end: document.getElementById("item-warranty").value,
        notes: document.getElementById("item-notes").value
    };

    const isEdit = !!id;
    const url = isEdit ? `/api/items/${id}` : "/api/items";
    const method = isEdit ? "PUT" : "POST";

    try {
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (res.ok) {
            itemModalInstance.hide();
            showToast(result.message || "Đã lưu thành công!");
            loadItems();
            loadDashboard();
            loadSitesDropdowns();
        } else {
            showToast(result.error || "Có lỗi xảy ra", true);
        }
    } catch (err) {
        showToast("Lỗi kết nối máy chủ: " + err, true);
    }
}

async function confirmDeleteItem(id, name) {
    if (confirm(`Bạn có chắc chắn muốn xóa thiết bị "${name}" khỏi hệ thống không?`)) {
        try {
            const res = await fetch(`/api/items/${id}`, { method: "DELETE" });
            const result = await res.json();
            if (res.ok) {
                showToast(result.message);
                loadItems();
                loadDashboard();
            } else {
                showToast(result.error || "Không thể xóa", true);
            }
        } catch (err) {
            showToast("Lỗi kết nối: " + err, true);
        }
    }
}

// ================= TAB 3: QUÉT IP LAN =================
async function loadNetworkInfo() {
    try {
        const res = await fetch("/api/network-info");
        const data = await res.json();
        
        detectedSubnet = data.suggested_subnet || "192.168.1.0/24";
        document.getElementById("scanner-current-ip").textContent = data.local_ip;
        document.getElementById("detected-subnet-badge").textContent = detectedSubnet;

        // Điền danh sách cơ sở cấu hình sẵn
        const presetSelect = document.getElementById("scanner-preset-select");
        presetSelect.innerHTML = "";
        preconfiguredSitesCache = data.preconfigured_sites || [];

        preconfiguredSitesCache.forEach((site, idx) => {
            const opt = document.createElement("option");
            opt.value = site.subnet;
            opt.textContent = `${site.name} — (${site.subnet})`;
            opt.dataset.siteName = site.name;
            presetSelect.appendChild(opt);
        });

        if (preconfiguredSitesCache.length > 0) {
            document.getElementById("scanner-preset-subnet").value = preconfiguredSitesCache[0].subnet;
        }

    } catch (err) {
        console.error("Lỗi lấy thông tin card mạng:", err);
    }
}

function selectScanMode(mode) {
    const radio = document.getElementById(`mode-${mode}`);
    if (radio) {
        radio.checked = true;
        onScanModeChanged();
    }
}

function onScanModeChanged() {
    const mode = document.querySelector('input[name="subnet_mode"]:checked')?.value || "auto";

    // Cập nhật class active trên các thẻ
    ["auto", "preset", "custom"].forEach(m => {
        const card = document.getElementById(`mode-card-${m}`);
        if (m === mode) {
            card.classList.add("active");
        } else {
            card.classList.remove("active");
        }
    });

    const presetSelect = document.getElementById("scanner-preset-select");
    const customInput = document.getElementById("scanner-custom-input");

    if (mode === "auto") {
        presetSelect.disabled = true;
        customInput.disabled = true;
    } else if (mode === "preset") {
        presetSelect.disabled = false;
        customInput.disabled = true;
        onPresetSiteSelected();
    } else if (mode === "custom") {
        presetSelect.disabled = true;
        customInput.disabled = false;
        customInput.focus();
    }
}

function onPresetSiteSelected() {
    const presetSelect = document.getElementById("scanner-preset-select");
    const subnet = presetSelect.value;
    document.getElementById("scanner-preset-subnet").value = subnet;

    // Đồng thời tự động chọn cơ sở tương ứng trong dropdown gán cơ sở nếu khớp
    const selectedOpt = presetSelect.options[presetSelect.selectedIndex];
    if (selectedOpt && selectedOpt.dataset.siteName) {
        const siteName = selectedOpt.dataset.siteName;
        const targetSiteSelect = document.getElementById("scanner-target-site");
        for (let i = 0; i < targetSiteSelect.options.length; i++) {
            if (targetSiteSelect.options[i].value.includes(siteName) || siteName.includes(targetSiteSelect.options[i].value)) {
                targetSiteSelect.selectedIndex = i;
                break;
            }
        }
    }
}

async function startLanScan() {
    const mode = document.querySelector('input[name="subnet_mode"]:checked')?.value || "auto";
    let subnetToScan = "";

    if (mode === "auto") {
        subnetToScan = detectedSubnet;
    } else if (mode === "preset") {
        subnetToScan = document.getElementById("scanner-preset-select").value;
    } else if (mode === "custom") {
        subnetToScan = document.getElementById("scanner-custom-input").value.trim();
        if (!subnetToScan) {
            showToast("Vui lòng nhập dải IP mạng cần quét (vd: 192.168.1.0/24)", true);
            document.getElementById("scanner-custom-input").focus();
            return;
        }
    }

    const targetSite = document.getElementById("scanner-target-site").value;
    const btn = document.getElementById("btn-start-scan");
    const btnText = document.getElementById("btn-scan-text");
    const statusBox = document.getElementById("scanner-status-box");
    const statusDesc = document.getElementById("scanner-status-desc");
    const tbody = document.getElementById("scanner-table-body");
    const summaryBadge = document.getElementById("scanner-summary-badge");

    // Khởi tạo trạng thái đang quét
    btn.disabled = true;
    btnText.textContent = "ĐANG QUÉT MẠNG...";
    statusBox.classList.remove("d-none");
    statusBox.classList.add("d-flex");
    statusDesc.textContent = `Đang gửi tín hiệu quét dải ${subnetToScan} (gồm 254 IP), đọc bảng ARP MAC và kiểm tra cổng...`;

    tbody.innerHTML = `
        <tr>
            <td colspan="8" class="text-center py-5">
                <div class="spinner-border text-primary mb-2" role="status"></div>
                <div class="text-secondary fw-semibold">Đang quét dải mạng <code>${escapeHtml(subnetToScan)}</code>...</div>
                <small class="text-muted">Quá trình này chỉ mất khoảng 2-3 giây</small>
            </td>
        </tr>
    `;

    try {
        const t0 = performance.now();
        const res = await fetch("/api/scan-lan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                subnet_ip: subnetToScan,
                site_name: targetSite
            })
        });

        const data = await res.json();
        const elapsed = ((performance.now() - t0) / 1000).toFixed(2);

        if (!res.ok) {
            statusBox.classList.add("d-none");
            statusBox.classList.remove("d-flex");
            btn.disabled = false;
            btnText.textContent = "BẮT ĐẦU QUÉT MẠNG";
            showToast(data.error || "Quét mạng thất bại!", true);
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4"><i class="bi bi-exclamation-triangle fs-3 d-block mb-1"></i>${escapeHtml(data.error || "Không thể quét dải mạng này.")}</td></tr>`;
            return;
        }

        // Hoàn tất quét thành công
        statusBox.classList.add("d-none");
        statusBox.classList.remove("d-flex");
        btn.disabled = false;
        btnText.textContent = "QUÉT LẠI DẢI MẠNG";

        summaryBadge.className = "badge bg-success-subtle text-success-emphasis border border-success px-3 py-2";
        summaryBadge.innerHTML = `<i class="bi bi-check2 me-1"></i>Đã quét xong ${data.total_hosts} IP trong ${elapsed}s: Tìm thấy <strong>${data.alive_count}</strong> thiết bị hoạt động`;

        if (data.devices.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-5"><i class="bi bi-wifi-off fs-3 d-block mb-1"></i>Không phát hiện thiết bị nào phản hồi trên dải mạng <code>${escapeHtml(subnetToScan)}</code>.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        data.devices.forEach((dev, idx) => {
            const tr = document.createElement("tr");

            // Format Open Ports
            let portsHtml = "";
            if (dev.open_ports && dev.open_ports.length > 0) {
                portsHtml = dev.open_ports.map(p => {
                    let pClass = "badge-port";
                    if ([80, 443, 8080].includes(p)) pClass += " badge-port-http";
                    else if ([22, 23].includes(p)) pClass += " badge-port-ssh";
                    return `<span class="${pClass}">${p}</span>`;
                }).join(" ");
            } else {
                portsHtml = `<span class="text-muted small">Không mở Web/SSH</span>`;
            }

            // Trạng thái đối chiếu kho
            let invStatusHtml = "";
            let actionBtnHtml = "";

            if (dev.in_inventory) {
                invStatusHtml = `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1"><i class="bi bi-check2-circle me-1"></i>Đã có trong kho (#${dev.matched_item.id})</span>`;
                actionBtnHtml = `
                    <button class="btn btn-sm btn-outline-primary" onclick="openEditItemModal(${dev.matched_item.id})">
                        <i class="bi bi-box-arrow-up-right me-1"></i>Xem Chi Tiết
                    </button>
                `;
            } else {
                invStatusHtml = `<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle px-2 py-1"><i class="bi bi-plus-circle me-1"></i>Thiết bị mới</span>`;
                actionBtnHtml = `
                    <button class="btn btn-sm btn-success fw-semibold" onclick="quickAddFromScan('${escapeHtml(dev.ip)}', '${escapeHtml(dev.mac)}', '${escapeHtml(dev.vendor)}', '${escapeHtml(dev.suggested_type)}')">
                        <i class="bi bi-plus-lg me-1"></i>+ Thêm Vào Kho
                    </button>
                `;
            }

            tr.innerHTML = `
                <td class="text-secondary text-center small">${idx + 1}</td>
                <td>
                    <span class="font-monospace fw-bold text-primary fs-6">${escapeHtml(dev.ip)}</span>
                    ${dev.hostname && dev.hostname !== '—' ? `<small class="text-muted d-block">${escapeHtml(dev.hostname)}</small>` : ''}
                </td>
                <td><code class="text-dark fw-semibold">${escapeHtml(dev.mac)}</code></td>
                <td>
                    <div class="fw-semibold text-dark">${escapeHtml(dev.vendor)}</div>
                </td>
                <td>${portsHtml}</td>
                <td><span class="badge bg-light text-dark border">${escapeHtml(dev.suggested_type)}</span></td>
                <td>${invStatusHtml}</td>
                <td class="text-end">${actionBtnHtml}</td>
            `;
            tbody.appendChild(tr);
        });

        showToast(`Quét thành công dải ${subnetToScan}: Tìm thấy ${data.alive_count} thiết bị!`);

    } catch (err) {
        statusBox.classList.add("d-none");
        statusBox.classList.remove("d-flex");
        btn.disabled = false;
        btnText.textContent = "BẮT ĐẦU QUÉT MẠNG";
        showToast("Lỗi kết nối khi quét mạng: " + err, true);
    }
}

// Thêm nhanh thiết bị phát hiện qua quét LAN vào kho
function quickAddFromScan(ip, mac, vendor, suggestedType) {
    const targetSite = document.getElementById("scanner-target-site").value || "Trụ sở chính";
    
    // Mở modal thêm thiết bị và điền sẵn thông tin nhận diện được
    document.getElementById("itemModalTitle").textContent = "Thêm Thiết Bị Phát Hiện Qua Quét Mạng";
    document.getElementById("item-id").value = "";
    document.getElementById("itemForm").reset();

    // Điền tên gợi ý
    let autoName = `${suggestedType}`;
    if (vendor && vendor !== "Không xác định" && !vendor.includes("Chưa nhận dạng")) {
        autoName = `${suggestedType} ${vendor}`;
    }
    document.getElementById("item-name").value = autoName;
    document.getElementById("item-category").value = suggestedType.includes("Router") ? "Router Gateway" : (suggestedType.includes("Switch") ? "Core Switch" : (suggestedType.includes("AP") || suggestedType.includes("Access Point") ? "Wi-Fi Access Point" : "Thiết bị mạng LAN"));
    document.getElementById("item-site").value = targetSite;
    document.getElementById("item-sn").value = (mac && mac !== "—") ? mac : "";
    document.getElementById("item-qty").value = 1;
    document.getElementById("item-unit").value = "Cái";
    document.getElementById("item-location").value = `IP LAN: ${ip}`;
    document.getElementById("item-status").value = "Đang sử dụng";
    document.getElementById("item-notes").value = `Tự động phát hiện qua tính năng Quét IP LAN (IP: ${ip} | MAC: ${mac} | Vendor: ${vendor})`;

    itemModalInstance.show();
}

// ================= TAB 4: NHẬP / XUẤT KHO =================
async function loadTransactions() {
    const q = document.getElementById("tx-search")?.value || "";
    const type = document.getElementById("tx-filter-type")?.value || "";

    const params = new URLSearchParams();
    if (q) params.append("q", q);
    if (type) params.append("type", type);

    try {
        const res = await fetch(`/api/transactions?${params.toString()}`);
        const txs = await res.json();

        const tbody = document.getElementById("tx-table-body");
        tbody.innerHTML = "";

        if (txs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-5"><i class="bi bi-clock-history fs-3 d-block mb-2"></i>Chưa có lịch sử giao dịch nào.</td></tr>`;
            return;
        }

        txs.forEach(tx => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="font-monospace text-primary fw-bold">#${String(tx.id).padStart(5, '0')}</td>
                <td><strong class="text-dark">${escapeHtml(tx.item_name)}</strong></td>
                <td class="text-center">${getTxBadge(tx.type)}</td>
                <td class="text-center fw-bold fs-6 text-dark">${tx.quantity} <small class="text-muted fw-normal">${escapeHtml(tx.unit)}</small></td>
                <td>
                    <div class="fw-semibold text-dark">${escapeHtml(tx.recipient || '—')}</div>
                    <small class="text-muted">${escapeHtml(tx.department || '')}</small>
                </td>
                <td class="small text-secondary"><i class="bi bi-person me-1"></i>${escapeHtml(tx.performer)}</td>
                <td class="small text-secondary">${escapeHtml(tx.notes || '—')}</td>
                <td class="small text-muted">${escapeHtml(tx.created_at)}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Lỗi nạp transactions:", err);
    }
}

// Mở modal tạo phiếu kho
async function openCreateTxModal(preselectedItemId = null, preselectedType = "Xuất kho") {
    try {
        const res = await fetch("/api/items");
        const items = await res.json();
        const sel = document.getElementById("tx-item-id");
        sel.innerHTML = `<option value="">-- Chọn thiết bị trong kho --</option>`;

        items.forEach(it => {
            const opt = document.createElement("option");
            opt.value = it.id;
            opt.textContent = `${it.name} [${it.site_name || 'Trụ sở'}] (Tồn: ${it.quantity} ${it.unit}) [${it.status}]`;
            opt.dataset.qty = it.quantity;
            opt.dataset.unit = it.unit;
            opt.dataset.name = it.name;
            if (preselectedItemId && it.id === preselectedItemId) {
                opt.selected = true;
            }
            sel.appendChild(opt);
        });

        document.getElementById("txForm").reset();
        document.getElementById("tx-type").value = preselectedType;
        document.getElementById("tx-qty").value = 1;
        document.getElementById("tx-performer").value = "Kỹ thuật IT";
        if (preselectedItemId) sel.value = preselectedItemId;

        onTxItemSelect();
        txModalInstance.show();
    } catch (err) {
        showToast("Lỗi nạp danh sách thiết bị: " + err, true);
    }
}

function quickStockOut(itemId) {
    openCreateTxModal(itemId, "Xuất kho");
}

function quickStockIn(itemId) {
    openCreateTxModal(itemId, "Nhập kho");
}

function onTxTypeChange() {
    onTxItemSelect();
}

function onTxItemSelect() {
    const sel = document.getElementById("tx-item-id");
    const hint = document.getElementById("tx-stock-hint");
    const selectedOpt = sel.options[sel.selectedIndex];

    if (selectedOpt && selectedOpt.value) {
        const currentQty = parseInt(selectedOpt.dataset.qty || "0");
        const unit = selectedOpt.dataset.unit || "Cái";
        const txType = document.getElementById("tx-type").value;

        hint.innerHTML = `Tồn kho hiện tại: <strong class="${currentQty <= 2 ? 'text-danger' : 'text-success'}">${currentQty} ${unit}</strong>`;
        if (txType === "Xuất kho") {
            document.getElementById("tx-qty").max = currentQty;
        } else {
            document.getElementById("tx-qty").removeAttribute("max");
        }
    } else {
        hint.textContent = "Tồn kho hiện tại: —";
    }
}

async function submitTxForm(e) {
    e.preventDefault();
    const itemId = document.getElementById("tx-item-id").value;
    if (!itemId) {
        showToast("Vui lòng chọn thiết bị!", true);
        return;
    }

    const data = {
        item_id: parseInt(itemId),
        type: document.getElementById("tx-type").value,
        quantity: parseInt(document.getElementById("tx-qty").value),
        recipient: document.getElementById("tx-recipient").value,
        department: document.getElementById("tx-department").value,
        performer: document.getElementById("tx-performer").value,
        notes: document.getElementById("tx-notes").value
    };

    try {
        const res = await fetch("/api/transactions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (res.ok) {
            txModalInstance.hide();
            showToast(result.message || "Giao dịch kho thành công!");
            loadTransactions();
            loadItems();
            loadDashboard();
        } else {
            showToast(result.error || "Giao dịch thất bại!", true);
        }
    } catch (err) {
        showToast("Lỗi kết nối máy chủ: " + err, true);
    }
}

// Helper tránh XSS
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}