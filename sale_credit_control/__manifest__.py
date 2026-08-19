# -*- coding: utf-8 -*-
{
    'name': 'Sales Credit Control',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Credit-limit and overdue-payment approval workflow for sale orders',
    'description': """
Sales Credit Control
====================
Adds a credit-control approval workflow to Sale Orders.

A sale order requires approval before it can be confirmed when either:

* **Credit limit breach** - the customer's outstanding receivable
  (``res.partner.credit``) plus this order's total would exceed the
  customer's credit limit (``res.partner.credit_limit``); or
* **Overdue payment** - the customer has any posted customer invoice with a
  residual amount and a due date in the past (zero grace days).

Credit exposure is payment-status driven: a fully paid invoice consumes no
credit, a partially paid invoice consumes only its residual, an unpaid invoice
consumes its full amount.

Approvers are configured in *Sales > Configuration > Settings* (a Many2many of
users). Any single approver is sufficient to release an order. Approvers are
notified with an Odoo activity and a chatter message.
""",
    'author': 'Custom',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'account',
    ],
    'data': [
        'data/mail_activity_type_data.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
