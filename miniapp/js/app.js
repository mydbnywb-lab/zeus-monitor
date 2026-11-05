
async function loadDashboard() {
    try {
        const response = await fetch("/api/dashboard?t=" + Date.now(), {
            cache: "no-store"
        });

        if (!response.ok) throw new Error("API HTTP " + response.status);

        const data = await response.json();

        document.getElementById("total-users").textContent = data.users.total;
        document.getElementById("active-users").textContent = data.users.active;
        document.getElementById("online-users").textContent = data.users.online;
        const health = data.health || {};
        const scoreEl = document.getElementById("health-score");
        const barEl = document.getElementById("health-progress-bar");
        const statusEl = document.getElementById("health-status");

        if (scoreEl && barEl && statusEl) {
            const score = health.score;
            const color = health.color || "unknown";
            scoreEl.textContent = score === null || score === undefined ? "--" : score;
            scoreEl.style.color = color;
            barEl.style.width = score === null || score === undefined ? "0%" : score + "%";
            barEl.style.backgroundColor = color;
            statusEl.textContent = score === null || score === undefined
                ? "No nodes available"
                : color === "green" ? "Healthy"
                : color === "yellow" ? "Warning" : "Critical";
        }

        const onlineNodes = document.getElementById("online-nodes");
        if (onlineNodes) onlineNodes.textContent = data.nodes.online;
        const offlineNodes = document.getElementById("offline-nodes");
        if (offlineNodes) offlineNodes.textContent = data.nodes.offline;
        renderNodes(data.nodes.items || []);


        const connection = document.querySelector(
            ".connection-status span:last-child"
        );
        if (connection) connection.textContent = "BACKEND ONLINE";

        document.getElementById("panel-status").textContent =
            "PasarGuard " + data.panel_version +
            " · " + data.users.online + " users online";

        const indicator = document.getElementById("panel-indicator");
        indicator.textContent = "ONLINE";
        indicator.style.color = "#22c55e";

    } catch (error) {
        console.error("ZEUS DASHBOARD ERROR:", error);
        document.getElementById("panel-status").textContent =
            "Connection error: " + error.message;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
    setInterval(loadDashboard, 30000);
});


function formatTraffic(bytes) {
    const gb = bytes / (1024 ** 3);
    if (gb >= 1024) return (gb / 1024).toFixed(2) + " TB";
    return gb.toFixed(2) + " GB";
}

function renderNodes(nodes) {
    const container = document.getElementById("nodes-list");
    if (!container) return;

    if (!nodes.length) {
        container.innerHTML = '<div class="nodes-loading">No nodes found.</div>';
        return;
    }

    container.innerHTML = nodes.map(node => {
        const connected = node.status === "connected";
        const statusText = connected ? "ACTIVE" : "DISCONNECTED";
        const statusClass = connected ? "node-online" : "node-offline";
        const dotClass = connected ? "green" : "red";

        return `
            <article class="node-card">
                <div class="node-card-top">
                    <div class="node-name-area">
                        <span class="metric-dot ${dotClass}"></span>
                        <span class="node-name">${escapeNodeName(node.name)}</span>
                    </div>
                    <span class="node-status ${statusClass}">${statusText}</span>
                </div>
                <div class="node-traffic">
                    <span class="traffic-label">TOTAL TRAFFIC USED</span>
                    <span class="traffic-value">${formatTraffic(Number(node.traffic_bytes) || 0)}</span>
                </div>
            </article>
        `;
    }).join("");
}

function escapeNodeName(value) {
    const element = document.createElement("span");
    element.textContent = value || "Unknown Node";
    return element.innerHTML;
}

/* ZEUS REAL-TIME ANALYTICS */
const zeusCharts = {};

function createZeusChart(id, type, datasets, labels) {
    const canvas = document.getElementById(id);
    if (!canvas) return;

    zeusCharts[id] = new Chart(canvas, {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index"
            },
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: "#cbd5e1",
                        usePointStyle: true,
                        boxWidth: 8
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: "#94a3b8", maxTicksLimit: 6 },
                    grid: { color: "rgba(148,163,184,0.08)" }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: "#94a3b8" },
                    grid: { color: "rgba(148,163,184,0.08)" }
                }
            }
        }
    });
}

function updateZeusChart(id, labels, datasets) {
    const chart = zeusCharts[id];

    if (!chart) {
        createZeusChart(id, "line", datasets, labels);
        return;
    }

    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.update("none");
}

async function loadAnalytics() {
    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded.");
        return;
    }

    try {
        const response = await fetch(
            "/api/analytics?range=24h&t=" + Date.now(),
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error("Analytics HTTP " + response.status);
        }

        const result = await response.json();
        const samples = result.samples || [];

        if (!samples.length) return;

        const labels = samples.map(item =>
            new Date(item.time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            })
        );

        // 1. TRAFFIC USAGE - cumulative traffic in GB
        updateZeusChart(
            "traffic-chart",
            labels,
            [
                {
                    label: "Incoming GB",
                    data: samples.map(s => s.traffic.incoming / 1073741824),
                    borderColor: "#38bdf8",
                    backgroundColor: "rgba(56,189,248,0.12)",
                    fill: true,
                    tension: 0.35
                },
                {
                    label: "Outgoing GB",
                    data: samples.map(s => s.traffic.outgoing / 1073741824),
                    borderColor: "#a78bfa",
                    backgroundColor: "rgba(167,139,250,0.10)",
                    fill: true,
                    tension: 0.35
                }
            ]
        );

        // 2. NODE TRAFFIC
        const nodeNames = [
            ...new Set(samples.flatMap(s =>
                (s.nodes || []).map(n => n.name)
            ))
        ];

        const nodeColors = [
            "#38bdf8", "#a78bfa", "#22c55e",
            "#f59e0b", "#f472b6", "#fb7185"
        ];

        updateZeusChart(
            "node-chart",
            labels,
            nodeNames.map((name, index) => ({
                label: name,
                data: samples.map(s => {
                    const node = (s.nodes || []).find(n => n.name === name);
                    return node ? node.traffic_bytes / 1073741824 : null;
                }),
                borderColor: nodeColors[index % nodeColors.length],
                backgroundColor: "transparent",
                tension: 0.3,
                spanGaps: true
            }))
        );

        // 3. USER STATISTICS
        updateZeusChart(
            "users-chart",
            labels,
            [
                {
                    label: "Active",
                    data: samples.map(s => s.users.active),
                    borderColor: "#22c55e",
                    tension: 0.3
                },
                {
                    label: "Online",
                    data: samples.map(s => s.users.online),
                    borderColor: "#38bdf8",
                    tension: 0.3
                },
                {
                    label: "Expired",
                    data: samples.map(s => s.users.expired),
                    borderColor: "#f87171",
                    tension: 0.3
                }
            ]
        );

        // 4. SERVER RESOURCES
        updateZeusChart(
            "resources-chart",
            labels,
            [
                {
                    label: "CPU %",
                    data: samples.map(s => s.resources.cpu),
                    borderColor: "#a78bfa",
                    tension: 0.3
                },
                {
                    label: "RAM %",
                    data: samples.map(s =>
                        s.resources.memory_total > 0
                            ? (s.resources.memory_used /
                               s.resources.memory_total) * 100
                            : 0
                    ),
                    borderColor: "#38bdf8",
                    tension: 0.3
                }
            ]
        );

    } catch (error) {
        console.error("ZEUS ANALYTICS ERROR:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadAnalytics();
    setInterval(loadAnalytics, 60000);
});
/* END ZEUS REAL-TIME ANALYTICS */


/* ZEUS MENU AND SECTIONS */
document.addEventListener("DOMContentLoaded", () => {
    const menu = document.getElementById("side-menu");
    const overlay = document.getElementById("menu-overlay");

    function closeMenu() {
        menu.classList.remove("open");
        overlay.classList.remove("show");
    }

    document.getElementById("menu-button").addEventListener("click", () => {
        menu.classList.add("open");
        overlay.classList.add("show");
    });

    document.getElementById("menu-close").addEventListener("click", closeMenu);
    overlay.addEventListener("click", closeMenu);

    document.querySelectorAll(".menu-link").forEach(button => {
        button.addEventListener("click", () => {
            const page = button.dataset.page;

            document.querySelectorAll(".page-section").forEach(section => {
                section.classList.toggle("active", section.id === `page-${page}`);
            });

            document.querySelectorAll(".menu-link").forEach(link => {
                link.classList.toggle("active", link === button);
            });

            closeMenu();

            if (page === "users" || page === "nodes") loadDashboard();
            if (page === "charts") loadAnalytics();
        });
    });

    loadUserDetails();
    setInterval(loadUserDetails, 30000);
});

async function loadUserDetails() {
    try {
        const response = await fetch(`/api/dashboard?t=${Date.now()}`);
        if (!response.ok) throw new Error("Dashboard request failed");

        const data = await response.json();
        const users = data.users || {};
        const traffic = data.traffic || {};

        const values = {
            "total-users": users.total,
            "users-active": users.active,
            "users-online": users.online,
            "expired-users": users.expired,
            "on-hold-users": users.on_hold,
            "disabled-users": users.disabled,
            "limited-users": users.limited
        };

        Object.entries(values).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = Number(value ?? 0).toLocaleString();
        });

        const totalTraffic = Number(traffic.incoming || 0) + Number(traffic.outgoing || 0);
        const trafficElement = document.getElementById("total-panel-traffic");
        if (trafficElement) trafficElement.textContent = formatTraffic(totalTraffic);

        const status = document.querySelector(".connection-status span:last-child");
        if (status) status.textContent = "BACKEND ONLINE";
    } catch (error) {
        console.error("User details error:", error);
    }
}

async function loadOutages() {
    const container = document.getElementById("outages-list");
    if (!container) return;

    try {
        const response = await fetch(`/api/outages?t=${Date.now()}`);
        if (!response.ok) throw new Error("Outage request failed");

        const data = await response.json();

        if (!data.items || data.items.length === 0) {
            container.innerHTML = '<div class="empty-state">No outage records found.</div>';
            return;
        }

        container.innerHTML = data.items.map(item => {
            const started = item.started_at
                ? new Date(item.started_at).toLocaleString()
                : "--";
            const recovered = item.recovered_at
                ? new Date(item.recovered_at).toLocaleString()
                : "Not recovered";
            const duration = item.duration_seconds == null
                ? "--"
                : `${Math.floor(item.duration_seconds / 60)} min`;

            const safe = value => String(value ?? "").replace(/[&<>"']/g, char => ({
                "&": "&amp;", "<": "&lt;", ">": "&gt;",
                '"': "&quot;", "'": "&#39;"
            })[char]);

            return `
                <article class="outage-card">
                    <div class="outage-card-heading">
                        <strong>${safe(item.service)}</strong>
                        <span class="outage-status">${safe(item.status)}</span>
                    </div>
                    <div class="outage-details">
                        <span>Started: ${safe(started)}</span>
                        <span>Recovered: ${safe(recovered)}</span>
                        <span>Duration: ${safe(duration)}</span>
                    </div>
                    ${item.message ? `<p>${safe(item.message)}</p>` : ""}
                </article>
            `;
        }).join("");
    } catch (error) {
        console.error("Outage history error:", error);
        container.innerHTML = '<div class="empty-state">Unable to load outage history.</div>';
    }
}
/* END ZEUS MENU AND SECTIONS */

/* ZEUS CUSTOMIZATION ENGINE */
const zeusTranslations = {
    fa: {
        dashboard: "داشبورد",
        users: "کاربران",
        nodes: "نودها",
        charts: "نمودارها",
        outages: "تاریخچه قطعی‌ها",
        customization: "شخصی‌سازی",
        panelSettings: "اطلاعات پنل",
        notifications: "اطلاع‌رسانی",
        dashboardTitle: "داشبورد",
        dashboardDesc: "نمای کلی وضعیت سرور",
        active: "کاربران فعال",
        online: "کاربران آنلاین",
        healthScore: "امتیاز سلامت نودها",
        total: "کل کاربران",
        expired: "کاربران منقضی",
        hold: "در انتظار",
        disabled: "غیرفعال",
        limited: "محدود شده",
        traffic: "کل ترافیک پنل",
        trafficDesc: "مجموع ترافیک ورودی و خروجی",
        nodesTitle: "نودها",
        nodesDesc: "وضعیت و مصرف ترافیک نودها",
        chartsTitle: "نمودارها",
        chartsDesc: "آمار و تحلیل تاریخی پنل",
        outageTitle: "تاریخچه قطعی‌ها",
        outageDesc: "گزارش قطعی و بازیابی سرویس‌ها",
        customizationTitle: "شخصی‌سازی",
        customizationDesc: "تنظیم ظاهر و زبان ZEUS",
        theme: "رنگ نئون",
        language: "زبان",
        green: "سبز نئونی",
        yellow: "زرد نئونی",
        blue: "آبی نئونی",
        red: "قرمز نئونی",
        purple: "بنفش نئونی",
        pink: "صورتی نئونی",
        orange: "نارنجی نئونی",
        cyan: "فیروزه‌ای نئونی",
        gold: "طلایی",
        white: "سفید",
        applyTheme: "اعمال رنگ",
        cancelTheme: "لغو",
        saved: "تنظیمات به‌صورت خودکار ذخیره می‌شوند.",
        started: "شروع:",
        recovered: "بازیابی:",
        duration: "مدت:",
        noOutages: "هنوز سابقه قطعی ثبت نشده است.",
        loading: "در حال دریافت اطلاعات...",
        live: "پایش زنده",
        nodeMonitor: "مانیتور نودها",
        trafficUsage: "مصرف ترافیک",
        nodeTraffic: "ترافیک نودها",
        userStats: "آمار کاربران",
        resources: "منابع سرور",
        systemStatus: "وضعیت سیستم",
        panel: "پنل پاسارگارد",
        onlineStatus: "متصل",
        offlineStatus: "قطع",
        totalTraffic: "مجموع مصرف ترافیک"
    },
    en: {
        dashboard: "Dashboard",
        users: "Users",
        nodes: "Nodes",
        charts: "Charts",
        outages: "Outage History",
        customization: "Customization",
        panelSettings: "Panel Settings",
        notifications: "Notifications",
        dashboardTitle: "Dashboard",
        dashboardDesc: "Server status overview",
        active: "Active Users",
        online: "Online Users",
        healthScore: "NODE HEALTH SCORE",
        total: "Total Users",
        expired: "Expired Users",
        hold: "On Hold",
        disabled: "Disabled",
        limited: "Limited Users",
        traffic: "Total Panel Traffic",
        trafficDesc: "Incoming + outgoing traffic",
        nodesTitle: "Nodes",
        nodesDesc: "Node status and traffic usage",
        chartsTitle: "Charts",
        chartsDesc: "Historical panel analytics",
        outageTitle: "Outage History",
        outageDesc: "Service interruption and recovery records",
        customizationTitle: "Customization",
        customizationDesc: "Personalize ZEUS appearance and language",
        theme: "Neon Theme Color",
        language: "Language",
        green: "Neon Green",
        yellow: "Neon Yellow",
        blue: "Neon Blue",
        red: "Neon Red",
        purple: "Neon Purple",
        pink: "Neon Pink",
        orange: "Neon Orange",
        cyan: "Neon Cyan",
        gold: "Gold",
        white: "White",
        applyTheme: "Apply Theme",
        cancelTheme: "Cancel",
        saved: "Settings are saved automatically.",
        started: "Started:",
        recovered: "Recovered:",
        duration: "Duration:",
        noOutages: "No outage records found.",
        loading: "Loading information...",
        live: "Live Monitoring",
        nodeMonitor: "Node Monitor",
        trafficUsage: "Traffic Usage",
        nodeTraffic: "Node Traffic",
        userStats: "User Statistics",
        resources: "Server Resources",
        systemStatus: "System Status",
        panel: "PasarGuard Panel",
        onlineStatus: "Connected",
        offlineStatus: "Disconnected",
        totalTraffic: "Total Traffic Used"
    }
};

const ZEUS_THEMES = ["green", "blue", "purple", "red", "pink", "orange", "cyan", "gold", "white"];
let savedZeusTheme = "blue";
let pendingZeusTheme = "blue";

function setZeusTheme(theme) {
    if (theme === "yellow") theme = "gold";
    if (!ZEUS_THEMES.includes(theme)) theme = "blue";

    document.body.dataset.theme = theme;
    document.querySelectorAll(".theme-option").forEach(button => {
        button.classList.toggle("selected", button.dataset.theme === theme);
    });
    return theme;
}

function applyZeusTheme(theme) {
    savedZeusTheme = setZeusTheme(theme);
    pendingZeusTheme = savedZeusTheme;
    localStorage.setItem("zeus-theme", savedZeusTheme);
}

function previewZeusTheme(theme) {
    if (!ZEUS_THEMES.includes(theme)) return;
    pendingZeusTheme = theme;
    setZeusTheme(theme);
}

function applyZeusLanguage(language) {
    if (!["fa", "en"].includes(language)) language = "fa";

    const t = zeusTranslations[language];

    document.documentElement.lang = language;
    document.documentElement.dir = language === "fa" ? "rtl" : "ltr";
    document.body.dir = language === "fa" ? "rtl" : "ltr";
    document.body.classList.toggle("rtl-language", language === "fa");

    const setText = (selector, value) => {
        document.querySelectorAll(selector).forEach(element => {
            element.textContent = value;
        });
    };

    const menuLabels = document.querySelectorAll(".menu-link span");
    const menuKeys = ["dashboard", "users", "nodes", "charts", "customization", "panelSettings", "notifications"];
    menuLabels.forEach((element, index) => {
        if (menuKeys[index]) element.textContent = t[menuKeys[index]];
    });

    setText("#custom-title", t.customizationTitle);
    setText("#page-panel-settings .welcome h2", t.panelSettings);
    setText("#page-notifications .welcome h2", t.notifications);
    setText("#custom-subtitle", t.customizationDesc);
    setText("#theme-title", t.theme);
    setText("#language-title", t.language);
    setText("#theme-apply", t.applyTheme);
    setText("#theme-cancel", t.cancelTheme);
    setText("#custom-save-note", t.saved);

    setText("#page-dashboard .welcome h2", t.dashboardTitle);
    setText("#page-dashboard .welcome p", t.dashboardDesc);

    setText("#page-users .welcome h2", t.users);
    setText("#page-users .welcome p", t.dashboardDesc);
    setText("#page-nodes .welcome h2", t.nodesTitle);
    setText("#page-nodes .welcome p", t.nodesDesc);
    setText("#page-charts .welcome h2", t.chartsTitle);
    setText("#page-charts .welcome p", t.chartsDesc);
    setText("#page-outages .welcome h2", t.outageTitle);
    setText("#page-outages .welcome p", t.outageDesc);

    const cardLabels = {
        "#page-dashboard .stat-card:nth-child(1) .card-label": t.active,
        "#page-dashboard .stat-card:nth-child(2) .card-label": t.online,
        "#page-dashboard .health-card .card-label": t.healthScore,
        "#page-users .stat-card:nth-child(1) .card-label": t.total,
        "#page-users .stat-card:nth-child(2) .card-label": t.active,
        "#page-users .stat-card:nth-child(3) .card-label": t.online,
        "#page-users .stat-card:nth-child(4) .card-label": t.expired,
        "#page-users .stat-card:nth-child(5) .card-label": t.hold,
        "#page-users .stat-card:nth-child(6) .card-label": t.disabled,
        "#page-users .stat-card:nth-child(7) .card-label": t.limited,
        "#page-users .stat-card:nth-child(8) .card-label": t.traffic
    };

    Object.entries(cardLabels).forEach(([selector, value]) => setText(selector, value));

    setText("#total-panel-traffic + .card-description", t.trafficDesc);
    setText("#page-users .section-header h3", t.systemStatus);
    setText("#page-users .system-info h4", t.panel);

    const chartTitles = [
        t.trafficUsage, t.nodeTraffic, t.userStats, t.resources
    ];
    document.querySelectorAll("#page-charts .chart-card h3").forEach((element, index) => {
        if (chartTitles[index]) element.textContent = chartTitles[index];
    });

    document.querySelectorAll(".theme-option span[data-i18n]").forEach(element => {
        element.textContent = t[element.dataset.i18n];
    });

    document.querySelectorAll(".language-option").forEach(button => {
        button.classList.toggle("selected", button.dataset.language === language);
    });

    document.querySelectorAll("footer p").forEach((element, index) => {
        if (index === 1) element.textContent = language === "fa" ? "قدرت گرفته از ZEUS" : "POWERED BY ZEUS";
    });

    localStorage.setItem("zeus-language", language);
}

document.addEventListener("DOMContentLoaded", () => {
    applyZeusTheme(localStorage.getItem("zeus-theme") || "blue");
    applyZeusLanguage(localStorage.getItem("zeus-language") || "fa");

    document.querySelectorAll(".theme-option").forEach(button => {
        button.addEventListener("click", () => {
            previewZeusTheme(button.dataset.theme);
        });
    });

    document.getElementById("theme-apply")?.addEventListener("click", () => {
        applyZeusTheme(pendingZeusTheme);
    });

    document.getElementById("theme-cancel")?.addEventListener("click", () => {
        pendingZeusTheme = savedZeusTheme;
        setZeusTheme(savedZeusTheme);
    });

    document.querySelectorAll(".language-option").forEach(button => {
        button.addEventListener("click", () => {
            applyZeusLanguage(button.dataset.language);
        });
    });
});
/* END ZEUS CUSTOMIZATION ENGINE */


// ZEUS WELCOME MESSAGE EDITOR
document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById("welcome-message");
    const preview = document.getElementById("welcome-preview-box");
    const status = document.getElementById("welcome-status");

    if (!textarea || !preview || !status) return;

    const showStatus = (message, success = true) => {
        status.textContent = message;
        status.style.color = success ? "var(--accent)" : "#ff5252";
    };

    async function loadWelcomeMessage() {
        try {
            const response = await fetch("/api/settings/welcome");
            if (!response.ok) throw new Error("Load failed");
            const data = await response.json();
            textarea.value = data.message || "";
        } catch (error) {
            showStatus("خطا در دریافت پیام از سرور", false);
        }
    }

    document.getElementById("welcome-preview")?.addEventListener("click", () => {
        preview.textContent = textarea.value;
        preview.hidden = false;
    });

    document.getElementById("welcome-save")?.addEventListener("click", async () => {
        const message = textarea.value;
        if (!message.trim()) {
            showStatus("متن پیام نمی‌تواند خالی باشد.", false);
            return;
        }

        try {
            const response = await fetch("/api/settings/welcome", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message })
            });

            if (!response.ok) throw new Error("Save failed");
            showStatus("پیام خوشامدگویی با موفقیت ذخیره شد.");
        } catch (error) {
            showStatus("خطا در ذخیره پیام.", false);
        }
    });

    document.getElementById("welcome-reset")?.addEventListener("click", async () => {
        if (!confirm("پیام خوشامدگویی به حالت پیش‌فرض برگردد؟")) return;

        try {
            const response = await fetch("/api/settings/welcome/reset", {
                method: "POST"
            });

            if (!response.ok) throw new Error("Reset failed");

            const data = await response.json();
            textarea.value = data.message || "";
            preview.hidden = true;
            showStatus("پیام به حالت پیش‌فرض بازگردانده شد.");
        } catch (error) {
            showStatus("خطا در بازگردانی پیام.", false);
        }
    });

    loadWelcomeMessage();
});
// END ZEUS WELCOME MESSAGE EDITOR

// ZEUS PANEL SETTINGS
document.addEventListener("DOMContentLoaded", () => {
    const url = document.getElementById("panel-url");
    const interval = document.getElementById("panel-interval");
    const key = document.getElementById("panel-api-key");
    const save = document.getElementById("panel-settings-save");
    const status = document.getElementById("panel-settings-status");

    if (!url || !interval || !key || !save || !status) return;

    async function loadPanelSettings() {
        try {
            const response = await fetch("/api/settings/panel");
            if (!response.ok) throw new Error();
            const data = await response.json();
            url.value = data.panel_url || "";
            interval.value = data.check_interval || 60;
            key.placeholder = data.api_key_configured
                ? "کلید فعلی تنظیم شده؛ برای حفظ آن خالی بگذارید"
                : "API Key / Token";
        } catch {
            status.textContent = "خطا در دریافت اطلاعات پنل";
        }
    }


    const test = document.getElementById("public-alert-test");

    if (test) {
        test.addEventListener("click", async () => {
            test.disabled = true;
            status.textContent = "🧪 در حال ارسال پیام آزمایشی...";

            try {
                const response = await fetch("/api/settings/public-alert/test", {
                    method: "POST"
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || "ارسال ناموفق بود");
                status.textContent = "✅ پیام آزمایشی با موفقیت ارسال شد.";
            } catch (error) {
                status.textContent = "❌ " + error.message;
            } finally {
                test.disabled = false;
            }
        });
    }

    save.addEventListener("click", async () => {
        status.textContent = "در حال ذخیره...";
        save.disabled = true;

        try {
            const response = await fetch("/api/settings/panel", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    panel_url: url.value.trim(),
                    check_interval: Number(interval.value),
                    api_key: key.value || null
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "خطا در ذخیره");

            key.value = "";
            status.textContent = "تنظیمات با موفقیت ذخیره شد. برای اعمال کامل، سرویس‌ها باید راه‌اندازی مجدد شوند.";
            status.style.color = "var(--accent)";
        } catch (error) {
            status.textContent = error.message || "خطا در ذخیره تنظیمات";
            status.style.color = "#ff5252";
        } finally {
            save.disabled = false;
        }
    });

    loadPanelSettings();
});
// END ZEUS PANEL SETTINGS

// ZEUS PUBLIC ALERT SETTINGS
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("public-alert-chat");
    const save = document.getElementById("public-alert-save");
    const status = document.getElementById("public-alert-status");

    if (!input || !save || !status) return;

    fetch("/api/settings/public-alert")
        .then(r => r.json())
        .then(data => { input.value = data.chat || ""; })
        .catch(() => { status.textContent = "خطا در دریافت تنظیمات"; });

    save.addEventListener("click", async () => {
        save.disabled = true;
        status.textContent = "در حال ذخیره...";

        try {
            const response = await fetch("/api/settings/public-alert", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat: input.value.trim() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "خطا در ذخیره");

            status.textContent = "✅ تنظیمات اطلاع‌رسانی ذخیره شد.";
        } catch (error) {
            status.textContent = "❌ " + error.message;
        } finally {
            save.disabled = false;
        }
    });
});
