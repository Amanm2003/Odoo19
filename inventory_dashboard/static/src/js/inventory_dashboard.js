/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { user } from "@web/core/user";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";

const CHART_COLORS = [
    "#875A7B", "#00A09D", "#F1C40F", "#E67E22", "#3498DB",
    "#2ECC71", "#E74C3C", "#9B59B6", "#34495E", "#1ABC9C",
];

export class InventoryDashboard extends Component {
    static template = "inventory_dashboard.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.chartRefs = {
            category: useRef("chartCategory"),
            distribution: useRef("chartDistribution"),
            trend: useRef("chartTrend"),
            topAvailable: useRef("chartTopAvailable"),
            topDispatched: useRef("chartTopDispatched"),
            warehouseComparison: useRef("chartWarehouseComparison"),
        };
        this.chartInstances = {};

        this.state = useState({
            loading: true,
            isManager: false,
            kpis: {},
            charts: {},
            table: [],
            widgets: {
                today_planned_dispatch: 0,
                today_completed_dispatch: 0,
                pending_deliveries: 0,
                incoming_purchase_orders: 0,
                fast_moving: [],
                slow_moving: [],
                dead_stock: [],
                avg_daily_dispatch: 0,
                stock_coverage_days: 0,
                warehouse_utilization: [],
                inventory_turnover_ratio: 0,
            },
            filterOptions: {
                warehouses: [], locations: [], categories: [], companies: [], salespersons: [],
            },
            filters: {
                warehouse_id: false,
                location_id: false,
                product_id: false,
                category_id: false,
                company_id: false,
                partner_id: false,
                user_id: false,
                date_from: false,
                date_to: false,
                stock_status: false,
            },
            search: "",
            sortField: "product_name",
            sortOrder: "asc",
            page: 1,
            pageSize: 15,
            darkMode: false,
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.state.isManager = await user.hasGroup("inventory_dashboard.group_inventory_dashboard_manager");
            const options = await this.orm.call("inventory.dashboard", "get_filter_options", []);
            this.state.filterOptions = options;
            await this.loadData();
        });

        onMounted(() => {
            this.renderAllCharts();
            this.autoRefreshTimer = setInterval(() => this.loadData(true), 60000);
        });

        onWillUnmount(() => {
            if (this.autoRefreshTimer) {
                clearInterval(this.autoRefreshTimer);
            }
            Object.values(this.chartInstances).forEach((c) => c && c.destroy());
        });
    }

    // ------------------------------------------------------------
    // Data loading
    // ------------------------------------------------------------
    async loadData(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        try {
            const data = await this.orm.call("inventory.dashboard", "get_dashboard_data", [this.state.filters]);
            this.state.kpis = data.kpis || {};
            this.state.charts = data.charts || {};
            this.state.table = data.table || [];
            this.state.widgets = Object.assign(
                {
                    today_planned_dispatch: 0,
                    today_completed_dispatch: 0,
                    pending_deliveries: 0,
                    incoming_purchase_orders: 0,
                    fast_moving: [],
                    slow_moving: [],
                    dead_stock: [],
                    avg_daily_dispatch: 0,
                    stock_coverage_days: 0,
                    warehouse_utilization: [],
                    inventory_turnover_ratio: 0,
                },
                data.widgets || {}
            );
            this.page = 1;
            this.renderAllCharts();
        } catch (e) {
            console.error("Inventory Dashboard load error:", e);
            this.notification.add("Failed to load dashboard data. Check the browser console / Odoo server log for details.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(field, ev) {
        let value = ev.target.value;
        if (value === "") {
            value = false;
        } else if (["warehouse_id", "location_id", "product_id", "category_id", "company_id", "partner_id", "user_id"].includes(field)) {
            value = parseInt(value);
        }
        this.state.filters[field] = value;
        await this.loadData();
    }

    async clearFilters() {
        for (const key of Object.keys(this.state.filters)) {
            this.state.filters[key] = false;
        }
        this.state.search = "";
        await this.loadData();
    }

    async manualRefresh() {
        await this.loadData();
        this.notification.add("Dashboard refreshed.", { type: "success" });
    }

    // ------------------------------------------------------------
    // Charts
    // ------------------------------------------------------------
    renderAllCharts() {
        if (!window.Chart) {
            return;
        }
        this._renderBarChart("category", this.state.charts.stock_by_category, "Quantity");
        this._renderPieChart("distribution", this.state.charts.stock_distribution);
        this._renderLineChart("trend", this.state.charts.dispatch_trend);
        this._renderHorizontalBarChart("topAvailable", this.state.charts.top_available);
        this._renderBarChart("topDispatched", this.state.charts.top_dispatched, "Dispatched");
        this._renderBarChart("warehouseComparison", this.state.charts.warehouse_comparison, "Quantity");
    }

    _destroyChart(key) {
        if (this.chartInstances[key]) {
            this.chartInstances[key].destroy();
            this.chartInstances[key] = null;
        }
    }

    _renderBarChart(key, data, label) {
        const ref = this.chartRefs[key];
        if (!ref || !ref.el || !data) return;
        this._destroyChart(key);
        this.chartInstances[key] = new window.Chart(ref.el, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [{ label, data: data.data, backgroundColor: CHART_COLORS }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
        });
    }

    _renderHorizontalBarChart(key, data) {
        const ref = this.chartRefs[key];
        if (!ref || !ref.el || !data) return;
        this._destroyChart(key);
        this.chartInstances[key] = new window.Chart(ref.el, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [{ label: "Available", data: data.data, backgroundColor: CHART_COLORS }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
            },
        });
    }

    _renderPieChart(key, data) {
        const ref = this.chartRefs[key];
        if (!ref || !ref.el || !data) return;
        this._destroyChart(key);
        this.chartInstances[key] = new window.Chart(ref.el, {
            type: "pie",
            data: {
                labels: data.labels,
                datasets: [{ data: data.data, backgroundColor: CHART_COLORS }],
            },
            options: { responsive: true, maintainAspectRatio: false },
        });
    }

    _renderLineChart(key, data) {
        const ref = this.chartRefs[key];
        if (!ref || !ref.el || !data) return;
        this._destroyChart(key);
        this.chartInstances[key] = new window.Chart(ref.el, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [{
                    label: "Dispatched Qty",
                    data: data.data,
                    borderColor: CHART_COLORS[1],
                    backgroundColor: "rgba(0,160,157,0.15)",
                    fill: true,
                    tension: 0.3,
                }],
            },
            options: { responsive: true, maintainAspectRatio: false },
        });
    }

    // ------------------------------------------------------------
    // Smart actions
    // ------------------------------------------------------------
    async onKpiClick(kpiKey) {
        const actionDef = await this.orm.call("inventory.dashboard", "get_smart_action", [kpiKey, this.state.filters]);
        if (actionDef && actionDef.res_model) {
            await this.action.doAction(actionDef);
        }
    }

    // ------------------------------------------------------------
    // Table: search / sort / pagination
    // ------------------------------------------------------------
    get filteredRows() {
        let rows = this.state.table;
        if (this.state.search) {
            const s = this.state.search.toLowerCase();
            rows = rows.filter(
                (r) =>
                    (r.product_name || "").toLowerCase().includes(s) ||
                    (r.internal_ref || "").toLowerCase().includes(s) ||
                    (r.category || "").toLowerCase().includes(s) ||
                    (r.warehouse || "").toLowerCase().includes(s)
            );
        }
        const field = this.state.sortField;
        const order = this.state.sortOrder === "asc" ? 1 : -1;
        rows = [...rows].sort((a, b) => {
            const av = a[field], bv = b[field];
            if (typeof av === "string") return av.localeCompare(bv) * order;
            return (av - bv) * order;
        });
        return rows;
    }

    get pagedRows() {
        const start = (this.state.page - 1) * this.state.pageSize;
        return this.filteredRows.slice(start, start + this.state.pageSize);
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.filteredRows.length / this.state.pageSize));
    }

    setSort(field) {
        if (this.state.sortField === field) {
            this.state.sortOrder = this.state.sortOrder === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = field;
            this.state.sortOrder = "asc";
        }
    }

    goToPage(p) {
        if (p >= 1 && p <= this.totalPages) {
            this.state.page = p;
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.page = 1;
    }

    // ------------------------------------------------------------
    // Export
    // ------------------------------------------------------------
    exportExcel() {
        const filters = encodeURIComponent(JSON.stringify(this.state.filters));
        window.open(`/inventory_dashboard/export_excel?filters=${filters}`, "_blank");
    }

    exportPdf() {
        const filters = encodeURIComponent(JSON.stringify(this.state.filters));
        window.open(`/inventory_dashboard/export_pdf?filters=${filters}`, "_blank");
    }

    toggleDarkMode() {
        this.state.darkMode = !this.state.darkMode;
    }
}

registry.category("actions").add("inventory_dashboard.main", InventoryDashboard);