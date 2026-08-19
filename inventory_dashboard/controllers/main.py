# -*- coding: utf-8 -*-
import io
import json
import logging

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class InventoryDashboardController(http.Controller):

    @http.route('/inventory_dashboard/export_excel', type='http', auth='user', csrf=False)
    def export_excel(self, filters='{}', **kwargs):
        if not request.env.user.has_group('inventory_dashboard.group_inventory_dashboard_manager'):
            return request.not_found()

        if xlsxwriter is None:
            return request.make_response(
                "xlsxwriter python library is required for Excel export.",
                headers=[('Content-Type', 'text/plain')]
            )

        filters_dict = json.loads(filters) if filters else {}
        dashboard = request.env['inventory.dashboard']
        rows = dashboard._compute_table(filters_dict)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Inventory Stock')

        header_format = workbook.add_format({'bold': True, 'bg_color': '#875A7B', 'font_color': 'white'})
        headers = [
            'Product', 'Internal Reference', 'Category', 'Warehouse', 'Qty On Hand',
            'Reserved Qty', 'Planned Dispatch', 'Dispatched Qty', 'Incoming Qty',
            'Free Stock', 'Inventory Value',
        ]
        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_format)

        for row_idx, row in enumerate(rows, start=1):
            sheet.write(row_idx, 0, row['product_name'])
            sheet.write(row_idx, 1, row['internal_ref'])
            sheet.write(row_idx, 2, row['category'])
            sheet.write(row_idx, 3, row['warehouse'])
            sheet.write(row_idx, 4, row['qty_on_hand'])
            sheet.write(row_idx, 5, row['reserved_qty'])
            sheet.write(row_idx, 6, row['planned_dispatch'])
            sheet.write(row_idx, 7, row['dispatched_qty'])
            sheet.write(row_idx, 8, row['incoming_qty'])
            sheet.write(row_idx, 9, row['free_stock'])
            sheet.write(row_idx, 10, row['inventory_value'])

        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 10, 16)
        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="inventory_dashboard.xlsx"'),
            ]
        )

    @http.route('/inventory_dashboard/export_pdf', type='http', auth='user', csrf=False)
    def export_pdf(self, filters='{}', **kwargs):
        if not request.env.user.has_group('inventory_dashboard.group_inventory_dashboard_manager'):
            return request.not_found()

        filters_dict = json.loads(filters) if filters else {}
        dashboard = request.env['inventory.dashboard']
        rows = dashboard._compute_table(filters_dict)
        kpi_data = dashboard._compute_kpis(filters_dict)

        kpi_list = [
            {'label': 'Available Stock', 'value': kpi_data['available_stock']},
            {'label': 'Reserved Stock', 'value': kpi_data['reserved_stock']},
            {'label': 'Planned Dispatch', 'value': kpi_data['planned_dispatch']},
            {'label': 'Dispatched Stock', 'value': kpi_data['dispatched_stock']},
            {'label': 'Free Stock', 'value': kpi_data['free_stock']},
            {'label': 'Incoming Stock', 'value': kpi_data['incoming_stock']},
            {'label': 'Inventory Value', 'value': kpi_data['inventory_value']},
            {'label': 'Low Stock Products', 'value': kpi_data['low_stock_count']},
            {'label': 'Out of Stock Products', 'value': kpi_data['out_of_stock_count']},
        ]

        html = request.env['ir.qweb']._render(
            'inventory_dashboard.inventory_dashboard_pdf_template',
            {
                'kpis': kpi_list,
                'rows': rows,
                'generated_on': fields.Datetime.now().strftime('%Y-%m-%d %H:%M'),
            }
        )

        try:
            pdf_content, _dummy = request.env['ir.actions.report']._run_wkhtmltopdf([html])
        except Exception as e:
            _logger.exception("PDF generation failed")
            return request.make_response(
                "PDF export failed: wkhtmltopdf is not available on this server (%s)" % e,
                headers=[('Content-Type', 'text/plain')]
            )

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'attachment; filename="inventory_dashboard.pdf"'),
            ]
        )
