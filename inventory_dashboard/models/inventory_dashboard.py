# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class InventoryDashboard(models.AbstractModel):
    """Server-side data provider for the Inventory Dashboard OWL component.

    This is an AbstractModel (no table) - it only exposes methods that are
    called over RPC from the frontend. All heavy aggregation is done with
    read_group() / SQL to keep the dashboard fast on large datasets.
    """
    _name = 'inventory.dashboard'
    _description = 'Inventory Dashboard'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_stock_locations_domain(self, filters):
        """Build a domain for stock.quant based on dashboard filters."""
        domain = [('location_id.usage', '=', 'internal')]
        if filters.get('warehouse_id'):
            domain.append(('location_id.warehouse_id', '=', filters['warehouse_id']))
        if filters.get('location_id'):
            domain.append(('location_id', 'child_of', filters['location_id']))
        if filters.get('product_id'):
            domain.append(('product_id', '=', filters['product_id']))
        if filters.get('category_id'):
            domain.append(('product_id.categ_id', '=', filters['category_id']))
        if filters.get('company_id'):
            domain.append(('company_id', '=', filters['company_id']))
        return domain

    def _get_sale_lines_domain(self, filters, extra=None):
        domain = [('order_id.state', '=', 'sale'), ('display_type', '=', False)]
        if filters.get('warehouse_id'):
            domain.append(('order_id.warehouse_id', '=', filters['warehouse_id']))
        if filters.get('product_id'):
            domain.append(('product_id', '=', filters['product_id']))
        if filters.get('category_id'):
            domain.append(('product_id.categ_id', '=', filters['category_id']))
        if filters.get('company_id'):
            domain.append(('order_id.company_id', '=', filters['company_id']))
        if filters.get('partner_id'):
            domain.append(('order_id.partner_id', '=', filters['partner_id']))
        if filters.get('user_id'):
            domain.append(('order_id.user_id', '=', filters['user_id']))
        if filters.get('date_from'):
            domain.append(('order_id.date_order', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('order_id.date_order', '<=', filters['date_to']))
        if extra:
            domain += extra
        return domain

    def _get_purchase_lines_domain(self, filters):
        domain = [('order_id.state', 'in', ('purchase', 'done'))]
        if filters.get('warehouse_id'):
            domain.append(('order_id.picking_type_id.warehouse_id', '=', filters['warehouse_id']))
        if filters.get('product_id'):
            domain.append(('product_id', '=', filters['product_id']))
        if filters.get('category_id'):
            domain.append(('product_id.categ_id', '=', filters['category_id']))
        if filters.get('company_id'):
            domain.append(('order_id.company_id', '=', filters['company_id']))
        if filters.get('date_from'):
            domain.append(('order_id.date_order', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('order_id.date_order', '<=', filters['date_to']))
        return domain

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        kpis = self._compute_kpis(filters)
        charts = self._compute_charts(filters)
        table = self._compute_table(filters)
        widgets = self._compute_widgets(filters)
        return {
            'kpis': kpis,
            'charts': charts,
            'table': table,
            'widgets': widgets,
        }

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    def _compute_kpis(self, filters):
        Quant = self.env['stock.quant']
        quant_domain = self._get_stock_locations_domain(filters)

        quant_data = Quant.read_group(
            quant_domain, ['quantity:sum', 'reserved_quantity:sum'], []
        )
        qty_on_hand = quant_data[0]['quantity'] if quant_data else 0.0
        reserved_qty = quant_data[0]['reserved_quantity'] if quant_data else 0.0

        products_in_stock = Quant.read_group(
            quant_domain + [('quantity', '>', 0)], ['product_id'], ['product_id']
        )
        total_products = len(products_in_stock)

        # Planned dispatch = ordered - delivered on confirmed sale order lines
        sale_lines = self.env['sale.order.line'].search(
            self._get_sale_lines_domain(filters), limit=None
        )
        planned_dispatch = sum(
            (l.product_uom_qty - l.qty_delivered) for l in sale_lines
            if l.product_uom_qty > l.qty_delivered
        )
        dispatched_qty = sum(l.qty_delivered for l in sale_lines)

        free_stock = qty_on_hand - reserved_qty - planned_dispatch

        # Incoming stock from confirmed purchase orders
        purchase_lines = self.env['purchase.order.line'].search(
            self._get_purchase_lines_domain(filters), limit=None
        )
        incoming_qty = sum(
            (l.product_qty - l.qty_received) for l in purchase_lines
            if l.product_qty > l.qty_received
        )

        # Inventory value (best-effort, requires stock_account valuation)
        inventory_value = 0.0
        try:
            layers = self.env['stock.valuation.layer'].sudo().search(
                [('product_id.type', '=', 'consu')], limit=0
            )
            quants = Quant.search(quant_domain)
            inventory_value = sum(
                (q.value if 'value' in q._fields else q.quantity * q.product_id.standard_price)
                for q in quants
            )
        except Exception:
            quants = Quant.search(quant_domain)
            inventory_value = sum(q.quantity * q.product_id.standard_price for q in quants)

        # Low stock: below reordering rule min qty
        low_stock_count = 0
        out_of_stock_count = 0
        product_domain = []
        if filters.get('category_id'):
            product_domain.append(('categ_id', '=', filters['category_id']))
        if filters.get('product_id'):
            product_domain.append(('id', '=', filters['product_id']))
        products = self.env['product.product'].search(product_domain + [('type', '=', 'consu')], limit=5000)
        orderpoints = self.env['stock.warehouse.orderpoint'].search([
            ('product_id', 'in', products.ids)
        ])
        min_qty_map = {}
        for op in orderpoints:
            min_qty_map[op.product_id.id] = max(min_qty_map.get(op.product_id.id, 0), op.product_min_qty)

        for p in products:
            qty_avail = p.qty_available
            if qty_avail <= 0:
                out_of_stock_count += 1
            min_qty = min_qty_map.get(p.id, 0)
            if min_qty and qty_avail < min_qty:
                low_stock_count += 1

        return {
            'available_stock': round(qty_on_hand, 2),
            'products_in_stock': total_products,
            'reserved_stock': round(reserved_qty, 2),
            'planned_dispatch': round(planned_dispatch, 2),
            'dispatched_stock': round(dispatched_qty, 2),
            'free_stock': round(free_stock, 2),
            'incoming_stock': round(incoming_qty, 2),
            'inventory_value': round(inventory_value, 2),
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'currency_symbol': self.env.company.currency_id.symbol,
        }

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    def _compute_charts(self, filters):
        Quant = self.env['stock.quant']
        quant_domain = self._get_stock_locations_domain(filters)

        # Stock by category (read_group can't group on a dotted/related path,
        # so group by product_id directly and roll up to category in Python)
        prod_qty_groups = Quant.read_group(quant_domain, ['quantity:sum'], ['product_id'])
        categ_totals = {}
        for g in prod_qty_groups:
            if not g['product_id']:
                continue
            product = self.env['product.product'].browse(g['product_id'][0])
            categ_name = product.categ_id.display_name or _('Undefined')
            categ_totals[categ_name] = categ_totals.get(categ_name, 0.0) + (g['quantity'] or 0.0)
        stock_by_category = {
            'labels': list(categ_totals.keys()),
            'data': [round(v, 2) for v in categ_totals.values()],
        }

        # Stock distribution pie: available / reserved / planned / dispatched
        kpis = self._compute_kpis(filters)
        stock_distribution = {
            'labels': [_('Available'), _('Reserved'), _('Planned Dispatch'), _('Dispatched')],
            'data': [
                max(kpis['available_stock'] - kpis['reserved_stock'], 0),
                kpis['reserved_stock'],
                kpis['planned_dispatch'],
                kpis['dispatched_stock'],
            ],
        }

        # Dispatch trend - last 30 days, based on done outgoing stock moves
        date_from = fields.Date.today() - timedelta(days=29)
        move_domain = [
            ('state', '=', 'done'),
            ('location_dest_id.usage', '=', 'customer'),
            ('date', '>=', fields.Datetime.to_datetime(date_from)),
        ]
        if filters.get('warehouse_id'):
            move_domain.append(('picking_id.picking_type_id.warehouse_id', '=', filters['warehouse_id']))
        if filters.get('product_id'):
            move_domain.append(('product_id', '=', filters['product_id']))
        moves = self.env['stock.move'].search(move_domain, limit=20000)
        trend_map = {}
        for i in range(30):
            d = date_from + timedelta(days=i)
            trend_map[d.strftime('%Y-%m-%d')] = 0.0
        for m in moves:
            d_key = fields.Datetime.to_datetime(m.date).date().strftime('%Y-%m-%d')
            if d_key in trend_map:
                trend_map[d_key] += m.product_uom_qty
        dispatch_trend = {
            'labels': list(trend_map.keys()),
            'data': [round(v, 2) for v in trend_map.values()],
        }

        # Top 10 products by available stock
        prod_groups = Quant.read_group(
            quant_domain + [('quantity', '>', 0)], ['quantity:sum'], ['product_id'],
            orderby='quantity desc', limit=10
        )
        top_available = {
            'labels': [g['product_id'][1] for g in prod_groups],
            'data': [round(g['quantity'], 2) for g in prod_groups],
        }

        # Top 10 most dispatched products (based on delivered SO lines)
        sale_lines = self.env['sale.order.line'].search(
            self._get_sale_lines_domain(filters, extra=[('qty_delivered', '>', 0)]), limit=None
        )
        dispatched_map = {}
        for l in sale_lines:
            dispatched_map.setdefault(l.product_id, 0.0)
            dispatched_map[l.product_id] += l.qty_delivered
        top_dispatched_sorted = sorted(dispatched_map.items(), key=lambda x: x[1], reverse=True)[:10]
        top_dispatched = {
            'labels': [p.display_name for p, q in top_dispatched_sorted],
            'data': [round(q, 2) for p, q in top_dispatched_sorted],
        }

        # Warehouse comparison (same fix: group by location_id directly,
        # then roll up to warehouse in Python)
        loc_qty_groups = Quant.read_group(quant_domain, ['quantity:sum'], ['location_id'])
        wh_totals = {}
        for g in loc_qty_groups:
            if not g['location_id']:
                continue
            location = self.env['stock.location'].browse(g['location_id'][0])
            wh_name = location.warehouse_id.display_name or _('Undefined')
            wh_totals[wh_name] = wh_totals.get(wh_name, 0.0) + (g['quantity'] or 0.0)
        warehouse_comparison = {
            'labels': list(wh_totals.keys()),
            'data': [round(v, 2) for v in wh_totals.values()],
        }

        return {
            'stock_by_category': stock_by_category,
            'stock_distribution': stock_distribution,
            'dispatch_trend': dispatch_trend,
            'top_available': top_available,
            'top_dispatched': top_dispatched,
            'warehouse_comparison': warehouse_comparison,
        }

    # ------------------------------------------------------------------
    # Detailed table
    # ------------------------------------------------------------------
    def _compute_table(self, filters):
        Quant = self.env['stock.quant']
        quant_domain = self._get_stock_locations_domain(filters)
        quants = Quant.search(quant_domain, limit=5000)

        rows_map = {}
        for q in quants:
            key = (q.product_id.id, q.location_id.warehouse_id.id)
            if key not in rows_map:
                rows_map[key] = {
                    'product_id': q.product_id.id,
                    'product_name': q.product_id.display_name,
                    'internal_ref': q.product_id.default_code or '',
                    'category': q.product_id.categ_id.display_name,
                    'warehouse': q.location_id.warehouse_id.display_name or _('N/A'),
                    'warehouse_id': q.location_id.warehouse_id.id,
                    'qty_on_hand': 0.0,
                    'reserved_qty': 0.0,
                }
            rows_map[key]['qty_on_hand'] += q.quantity
            rows_map[key]['reserved_qty'] += q.reserved_quantity

        # attach planned dispatch / dispatched / incoming per product (not warehouse-specific due to complexity)
        sale_lines = self.env['sale.order.line'].search(self._get_sale_lines_domain(filters), limit=None)
        planned_map, dispatched_map = {}, {}
        for l in sale_lines:
            pid = l.product_id.id
            planned_map[pid] = planned_map.get(pid, 0.0) + max(l.product_uom_qty - l.qty_delivered, 0)
            dispatched_map[pid] = dispatched_map.get(pid, 0.0) + l.qty_delivered

        purchase_lines = self.env['purchase.order.line'].search(self._get_purchase_lines_domain(filters), limit=None)
        incoming_map = {}
        for l in purchase_lines:
            pid = l.product_id.id
            incoming_map[pid] = incoming_map.get(pid, 0.0) + max(l.product_qty - l.qty_received, 0)

        rows = []
        for key, row in rows_map.items():
            pid = row['product_id']
            product = self.env['product.product'].browse(pid)
            row['planned_dispatch'] = round(planned_map.get(pid, 0.0), 2)
            row['dispatched_qty'] = round(dispatched_map.get(pid, 0.0), 2)
            row['incoming_qty'] = round(incoming_map.get(pid, 0.0), 2)
            row['free_stock'] = round(
                row['qty_on_hand'] - row['reserved_qty'] - row['planned_dispatch'], 2
            )
            row['qty_on_hand'] = round(row['qty_on_hand'], 2)
            row['reserved_qty'] = round(row['reserved_qty'], 2)
            row['inventory_value'] = round(row['qty_on_hand'] * product.standard_price, 2)
            rows.append(row)

        # apply stock status filter
        status = filters.get('stock_status')
        if status == 'available':
            rows = [r for r in rows if r['free_stock'] > 0]
        elif status == 'reserved':
            rows = [r for r in rows if r['reserved_qty'] > 0]
        elif status == 'low_stock':
            orderpoints = self.env['stock.warehouse.orderpoint'].search([])
            min_map = {}
            for op in orderpoints:
                min_map[op.product_id.id] = max(min_map.get(op.product_id.id, 0), op.product_min_qty)
            rows = [r for r in rows if min_map.get(r['product_id'], 0) and r['qty_on_hand'] < min_map.get(r['product_id'], 0)]
        elif status == 'out_of_stock':
            rows = [r for r in rows if r['qty_on_hand'] <= 0]
        elif status == 'negative_stock':
            rows = [r for r in rows if r['qty_on_hand'] < 0 or r['free_stock'] < 0]

        rows.sort(key=lambda r: r['product_name'])
        return rows

    # ------------------------------------------------------------------
    # Extra widgets
    # ------------------------------------------------------------------
    def _compute_widgets(self, filters):
        today = fields.Date.today()
        today_start = fields.Datetime.to_datetime(today)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)

        # Today's planned / completed dispatch (outgoing pickings)
        Picking = self.env['stock.picking']
        picking_domain_base = [('picking_type_id.code', '=', 'outgoing')]
        if filters.get('warehouse_id'):
            picking_domain_base.append(('picking_type_id.warehouse_id', '=', filters['warehouse_id']))

        today_planned = Picking.search_count(picking_domain_base + [
            ('scheduled_date', '>=', today_start), ('scheduled_date', '<', today_end),
            ('state', 'not in', ('done', 'cancel')),
        ])
        today_completed = Picking.search_count(picking_domain_base + [
            ('date_done', '>=', today_start), ('date_done', '<', today_end),
            ('state', '=', 'done'),
        ])
        pending_deliveries = Picking.search_count(picking_domain_base + [
            ('state', 'in', ('assigned', 'confirmed', 'waiting')),
        ])
        incoming_domain_base = [('picking_type_id.code', '=', 'incoming')]
        if filters.get('warehouse_id'):
            incoming_domain_base.append(('picking_type_id.warehouse_id', '=', filters['warehouse_id']))
        incoming_pos = Picking.search_count(incoming_domain_base + [
            ('state', 'in', ('assigned', 'confirmed', 'waiting')),
        ])

        # Fast / slow moving & dead stock (based on dispatched qty in last 90 days)
        date_90 = fields.Datetime.to_datetime(today - timedelta(days=90))
        move_domain = [
            ('state', '=', 'done'),
            ('location_dest_id.usage', '=', 'customer'),
            ('date', '>=', date_90),
        ]
        moves = self.env['stock.move'].search(move_domain, limit=20000)
        move_qty_map = {}
        for m in moves:
            move_qty_map[m.product_id.id] = move_qty_map.get(m.product_id.id, 0.0) + m.product_uom_qty

        products = self.env['product.product'].search([('type', '=', 'consu')], limit=5000)
        scored = sorted(products, key=lambda p: move_qty_map.get(p.id, 0.0), reverse=True)
        fast_moving = [
            {'name': p.display_name, 'qty': round(move_qty_map.get(p.id, 0.0), 2)}
            for p in scored[:10] if move_qty_map.get(p.id, 0.0) > 0
        ]
        slow_candidates = [p for p in products if 0 < move_qty_map.get(p.id, 0.0) <= 2]
        slow_moving = [
            {'name': p.display_name, 'qty': round(move_qty_map.get(p.id, 0.0), 2)}
            for p in slow_candidates[:10]
        ]
        dead_stock_products = [p for p in products if move_qty_map.get(p.id, 0.0) == 0 and p.qty_available > 0]
        dead_stock = [{'name': p.display_name, 'qty': round(p.qty_available, 2)} for p in dead_stock_products[:10]]

        avg_daily_dispatch = round(sum(move_qty_map.values()) / 90.0, 2) if move_qty_map else 0.0

        total_on_hand = sum(p.qty_available for p in products)
        stock_coverage_days = round(total_on_hand / avg_daily_dispatch, 1) if avg_daily_dispatch else 0.0

        # Warehouse utilization: quantity stored vs a notional capacity placeholder
        warehouses = self.env['stock.warehouse'].search([])
        utilization = []
        for wh in warehouses:
            qty = sum(self.env['stock.quant'].search([
                ('location_id.warehouse_id', '=', wh.id), ('location_id.usage', '=', 'internal')
            ]).mapped('quantity'))
            utilization.append({'warehouse': wh.display_name, 'qty': round(qty, 2)})

        # Inventory turnover ratio = dispatched qty (90d) / average stock on hand
        turnover_ratio = round(sum(move_qty_map.values()) / total_on_hand, 2) if total_on_hand else 0.0

        return {
            'today_planned_dispatch': today_planned,
            'today_completed_dispatch': today_completed,
            'pending_deliveries': pending_deliveries,
            'incoming_purchase_orders': incoming_pos,
            'fast_moving': fast_moving,
            'slow_moving': slow_moving,
            'dead_stock': dead_stock,
            'avg_daily_dispatch': avg_daily_dispatch,
            'stock_coverage_days': stock_coverage_days,
            'warehouse_utilization': utilization,
            'inventory_turnover_ratio': turnover_ratio,
        }

    # ------------------------------------------------------------------
    # Filter options (for dropdowns)
    # ------------------------------------------------------------------
    @api.model
    def get_filter_options(self):
        return {
            'warehouses': self.env['stock.warehouse'].search_read([], ['id', 'name']),
            'locations': self.env['stock.location'].search_read(
                [('usage', '=', 'internal')], ['id', 'display_name'], limit=200),
            'categories': self.env['product.category'].search_read([], ['id', 'display_name']),
            'companies': self.env['res.company'].search_read([], ['id', 'name']),
            'salespersons': self.env['res.users'].search_read(
                [('share', '=', False)], ['id', 'name'], limit=200),
        }

    # ------------------------------------------------------------------
    # Smart action targets
    # ------------------------------------------------------------------
    @api.model
    def get_smart_action(self, kpi_key, filters=None):
        filters = filters or {}
        actions = {
            'available_stock': self._action_stock_quants(filters),
            'reserved_stock': self._action_stock_quants(filters, reserved=True),
            'planned_dispatch': self._action_pending_deliveries(filters),
            'dispatched_stock': self._action_completed_deliveries(filters),
            'free_stock': self._action_free_stock(filters),
            'incoming_stock': self._action_incoming_pos(filters),
            'inventory_value': self._action_stock_valuation(),
            'low_stock_count': self._action_low_stock(filters),
            'out_of_stock_count': self._action_out_of_stock(filters),
        }
        return actions.get(kpi_key, {})

    def _make_window_action(self, name, res_model, domain, context=None):
        """Build a complete ir.actions.act_window dict safe for the client's
        doAction() when called with a plain object (not fetched by id) -
        this requires an explicit 'views' list, not just 'view_mode'.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'context': context or {},
            'target': 'current',
        }

    def _action_stock_quants(self, filters, reserved=False):
        domain = self._get_stock_locations_domain(filters)
        if reserved:
            domain.append(('reserved_quantity', '>', 0))
        return self._make_window_action(
            _('Stock Quants'), 'stock.quant', domain, {'search_default_internal_loc': 1}
        )

    def _action_pending_deliveries(self, filters):
        domain = [('picking_type_id.code', '=', 'outgoing'), ('state', 'not in', ('done', 'cancel'))]
        if filters.get('warehouse_id'):
            domain.append(('picking_type_id.warehouse_id', '=', filters['warehouse_id']))
        return self._make_window_action(_('Pending Delivery Orders'), 'stock.picking', domain)

    def _action_completed_deliveries(self, filters):
        domain = [('picking_type_id.code', '=', 'outgoing'), ('state', '=', 'done')]
        if filters.get('warehouse_id'):
            domain.append(('picking_type_id.warehouse_id', '=', filters['warehouse_id']))
        return self._make_window_action(_('Completed Deliveries'), 'stock.picking', domain)

    def _action_incoming_pos(self, filters):
        domain = [('state', 'in', ('purchase', 'done'))]
        return self._make_window_action(_('Incoming Purchase Orders'), 'purchase.order', domain)

    def _action_free_stock(self, filters):
        # Free stock isn't a stored field anywhere, so derive matching
        # product ids from the same computation used for the table.
        rows = self._compute_table(filters)
        product_ids = list({r['product_id'] for r in rows if r['free_stock'] > 0})
        return self._make_window_action(
            _('Products with Free Stock'), 'product.product', [('id', 'in', product_ids)]
        )

    def _action_stock_valuation(self):
        if 'stock.valuation.layer' in self.env:
            return self._make_window_action(_('Stock Valuation'), 'stock.valuation.layer', [])
        # stock_account isn't installed - fall back to a valued view of quants
        return self._make_window_action(
            _('Stock Quants (Inventory Value)'), 'stock.quant',
            [('location_id.usage', '=', 'internal')],
        )

    def _action_low_stock(self, filters):
        orderpoints = self.env['stock.warehouse.orderpoint'].search([])
        low_ids = []
        for op in orderpoints:
            if op.product_id.qty_available < op.product_min_qty:
                low_ids.append(op.product_id.id)
        return self._make_window_action(
            _('Products Below Minimum Stock'), 'product.product', [('id', 'in', low_ids)]
        )

    def _action_out_of_stock(self, filters):
        products = self.env['product.product'].search([('type', '=', 'consu')], limit=5000)
        out_ids = [p.id for p in products if p.qty_available <= 0]
        return self._make_window_action(
            _('Out of Stock Products'), 'product.product', [('id', 'in', out_ids)]
        )