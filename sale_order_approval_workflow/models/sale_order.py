from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', tracking=True)

    approval_level = fields.Integer(default=0)

    approval_config_id = fields.Many2one(
        'sale.approval.config'
    )

    approval_log_ids = fields.One2many(
        'sale.approval.log',
        'sale_id'
    )

    credit_limit_breach = fields.Boolean(
        compute="_compute_credit_limit_breach",
        store=False
    )

    @api.depends('partner_id')
    def _compute_credit_limit_breach(self):
        for rec in self:
            total_due = sum(
                rec.partner_id.invoice_ids.filtered(
                    lambda x: x.state == 'posted'
                ).mapped('amount_residual')
            )

            rec.credit_limit_breach = total_due > 100000

    # def action_submit_for_approval(self):

    #     for order in self:

    #         config = self.env[
    #             'sale.approval.config'
    #         ].sudo().search([
    #             ('active', '=', True),
    #             ('min_amount', '<=', order.amount_total),
    #             ('max_amount', '>=', order.amount_total),
    #         ], limit=1)

    #         if not config:

    #             config = self.env[
    #                 'sale.approval.config'
    #             ].sudo().search([
    #                 ('risk_category', '=',
    #                  order.partner_id.credit_risk)
    #             ], limit=1)

    #         if not config and order.credit_limit_breach:

    #             config = self.env[
    #                 'sale.approval.config'
    #             ].sudo().search([
    #                 ('credit_limit_breach', '=', True)
    #             ], limit=1)

    #         if not config:
    #             order.action_confirm()
    #             return

    #         order.sudo().write({
    #             'approval_state': 'waiting_approval',
    #             'approval_config_id': config.id
    #         })

    #         # order.approval_log_ids.sudo().create({
    #         #     'sale_id': order.id,
    #         #     'user_id': self.env.user.id,
    #         #     'action': 'submitted'
    #         # })
            
    #         self.env['sale.approval.log'].sudo().create({
    #             'sale_id': order.id,
    #             'user_id': self.env.user.id,
    #             'action': 'submitted',
    #         })

    #         order._notify_approvers()

    # def _notify_approvers(self):

    #     for user in self.approval_config_id.approver_ids:

    #         self.activity_schedule(
    #             'mail.mail_activity_data_todo',
    #             user_id=user.id,
    #             note='Sales Order Approval Required'
    #         )
    
    
    
    # def _notify_approvers(self):
    #     for order in self.sudo():
    #         for user in order.approval_config_id.approver_ids:
    #             order.activity_schedule(
    #                 'mail.mail_activity_data_todo',
    #                 user_id=user.id,
    #                 note='Sales Order Approval Required'
    #             )

    def action_submit_for_approval(self):
        for order in self:
            config = False
            reason = ""

            config = self.env['sale.approval.config'].sudo().search([
                ('active', '=', True),
                ('min_amount', '<=', order.amount_total),
                ('max_amount', '>=', order.amount_total),
            ], limit=1)

            if config:
                reason = (
                    f"Order amount ({order.amount_total}) "
                    f"requires approval as per approval matrix."
                )
            if not config and order.partner_credit_warning:
                config = self.env['sale.approval.config'].sudo().search([
                    ('credit_limit_breach', '=', True),
                ], limit=1)

                if config:
                    reason = (
                        f"Customer has exceeded the credit limit. "
                        f"Current Receivable: {order.partner_id.credit:.2f}, "
                        f"Credit Limit: {order.partner_id.credit_limit:.2f}."
                    )

            if not config:
                config = self.env['sale.approval.config'].sudo().search([
                    ('credit_limit_breach', '=', True)
                ], limit=1)

                if config:
                    reason = (
                        f"Customer risk category "
                        f"'{order.partner_id.credit_risk}' requires approval."
                    )

            if not config and order.credit_limit_breach:
                config = self.env['sale.approval.config'].sudo().search([
                    ('credit_limit_breach', '=', True)
                ], limit=1)

                if config:
                    reason = (
                        f"Customer credit limit exceeded. "
                        f"Current exposure: {order.partner_id.credit}"
                    )

            if not config:
                order.action_confirm()
            
            if not config:
                config = self.env['sale.approval.config'].sudo().search([
                    ('credit_limit_breach', '=', True)
                ], limit=1)
                
                order.sudo().write({
                    'approval_state': 'waiting_approval',
                    'approval_config_id': config.id,
                })
                
            else:
                order.sudo().write({
                    'approval_state': 'waiting_approval',
                    'approval_config_id': config.id,
                })

            self.env['sale.approval.log'].sudo().create({
                'sale_id': order.id,
                'user_id': self.env.user.id,
                'action': 'submitted',
                'remarks': reason,   # add field if needed
            })

            order._notify_approvers(reason)
            
    def _notify_approvers(self, reason):
        for user in self.approval_config_id.sudo().approver_ids:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                note=f"""
    Approval Required for Sales Order {self.name}

    Reason:
    {reason}

    Customer: {self.partner_id.name}
    Amount: {self.amount_total}
                """
            )
    
    def action_approve(self):

        self.ensure_one()

        if self.env.user not in self.approval_config_id.sudo().approver_ids:
            raise UserError(
                "You are not authorized."
            )

        self.sudo().write({
            'approval_state': 'approved'
        })

        # self.approval_log_ids.sudo().create({
        #     'sale_id': self.id,
        #     'user_id': self.env.user.id,
        #     'action': 'approved'
        # })
        
        self.env['sale.approval.log'].sudo().create({
            'sale_id': self.id,
            'user_id': self.env.user.id,
            'action': 'approved',
        })

        self.sudo().action_confirm()



    def action_reject(self):

        self.ensure_one()

        self.write({
            'approval_state': 'rejected',
        })

        # self.approval_log_ids.create({
        #     'sale_id': self.id,
        #     'user_id': self.env.user.id,
        #     'action': 'rejected'
        # })
        self.env['sale.approval.log'].sudo().create({
            'sale_id': self.id,
            'user_id': self.env.user.id,
            'action': 'rejected',
        })
        
        
        self.sudo().action_cancel()
        
    def _approval_required(self):
        self.ensure_one()
        config = self.env['sale.approval.config'].search([
            ('active', '=', True),
            ('min_amount', '<=', self.amount_total),
            ('max_amount', '>=', self.amount_total),
        ], limit=1)
        if config:
            return True
        if self.partner_id.credit_risk == 'high':
            return True
        # if self.credit_limit_breach:
        #     return True
        if self.partner_credit_warning:
            return True
        return False


    def action_confirm(self):

        for order in self:
            
            if (
                order._approval_required()
                and order.approval_state != 'approved'
            ):
                raise UserError(
                    "Sales Order must be approved before confirmation."
                )
        return super().action_confirm()
    
    def action_cancel(self):
        self.write({
            'approval_state': 'draft',
        })
        return super().action_cancel()
    
    
    approval_required = fields.Boolean(
        compute="_compute_approval_required",
    )

    @api.depends(
        'amount_total',
        'partner_id',
        'partner_id.credit_risk',
        'partner_credit_warning',
    )
    def _compute_approval_required(self):
        for order in self:
            order.approval_required = order._approval_required()