# -*- coding: utf-8 -*-
{
    'name': 'Inventory Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Real-time Inventory Dashboard with KPIs, Charts, Filters and Exports',
    'description': """
Inventory Dashboard
====================
A modern, responsive, real-time Inventory Dashboard for warehouse managers,
inventory controllers and management.

Features:
- KPI cards: Available Stock, Reserved Stock, Planned Dispatch, Dispatched Stock,
  Free Stock, Incoming Stock, Inventory Value, Low Stock, Out of Stock
- Charts: Stock by Category, Stock Distribution, Dispatch Trend, Top 10 Available,
  Top 10 Dispatched, Warehouse Comparison
- Detailed, searchable, sortable, paginated product stock table
- Dynamic filters (Warehouse, Location, Product, Category, Company, Customer,
  Salesperson, Date Range, Stock Status)
- Clickable KPI smart actions
- Excel & PDF export
- Auto refresh every 60 seconds + manual refresh
- Dedicated security groups (User / Manager)
""",
    'author': 'Custom Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['stock', 'sale_management', 'purchase'],
    'data': [
        'security/inventory_dashboard_security.xml',
        'security/ir.model.access.csv',
        'report/inventory_dashboard_report_templates.xml',
        'views/inventory_dashboard_views.xml',
        'views/inventory_dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_dashboard/static/src/js/inventory_dashboard.js',
            'inventory_dashboard/static/src/xml/inventory_dashboard.xml',
            'inventory_dashboard/static/src/scss/inventory_dashboard.scss',
            ('include', 'web._assets_helpers'),
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}