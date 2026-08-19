# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    approval_required = fields.Boolean(
        string='Credit Approval Required',
        compute='_compute_credit_approval',
        help='Computed live: True when this order breaches the customer credit '
             'limit or the customer has overdue payments.',
    )
    approval_reason = fields.Selection(
        selection=[
            ('credit_limit', 'Credit limit exceeded'),
            ('overdue', 'Overdue payment'),
            ('both', 'Credit limit exceeded and overdue payment'),
        ],
        string='Approval Reason',
        compute='_compute_credit_approval',
    )
    approval_state = fields.Selection(
        selection=[
            ('not_required', 'Not required'),
            ('to_approve', 'To approve'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
        ],
        string='Credit Approval Status',
        default='not_required',
        copy=False,
        tracking=True,
    )
    approved_by = fields.Many2one(
        comodel_name='res.users',
        string='Approved / Refused by',
        copy=False,
        readonly=True,
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        copy=False,
        readonly=True,
    )
    can_approve_credit = fields.Boolean(
        string='Can Approve Credit',
        compute='_compute_can_approve_credit',
        help='Technical field: True when the current user is a configured '
             'credit approver. Used to control button visibility.',
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('partner_id', 'amount_total', 'company_id', 'state')
    def _compute_credit_approval(self):
        for order in self:
            required, reason = order._evaluate_credit_control()
            order.approval_required = required
            order.approval_reason = reason

    @api.depends_context('uid')
    def _compute_can_approve_credit(self):
        user = self.env.user
        for order in self:
            order.can_approve_credit = user in order._get_credit_approvers()

    @api.depends('company_id', 'partner_id', 'amount_total')
    def _compute_partner_credit_warning(self):
        """Override the native credit-warning banner so the amount of the order
        currently being created is NOT added to the customer's outstanding
        balance. The banner therefore shows only the existing amount due
        (invoices + confirmed sales orders) and no longer grows as lines are
        added to this quotation. This mirrors the module's approval check, which
        also excludes the current order's amount.
        """
        for order in self:
            order.partner_credit_warning = ''
            show_warning = (
                order.state in ('draft', 'sent')
                and order.company_id.account_use_credit_limit
                # Secondary / Distributor orders are exempt from credit control.
                and getattr(order, 'order_category', False) != 'secondary_order'
            )
            if show_warning:
                order.partner_credit_warning = self.env[
                    'account.move']._build_credit_warning_message(
                    order.sudo(),  # access to credit / credit_limit fields
                    current_amount=0.0,  # exclude this document's own amount
                )

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _get_credit_approvers(self):
        """Return the res.users configured as credit approvers for this order's
        company. Read as sudo because a salesperson may not have read access on
        the company approvers relation."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return company.sudo().credit_approver_ids

    # ------------------------------------------------------------------
    # Credit evaluation
    # ------------------------------------------------------------------
    def _evaluate_credit_control(self):
        """Evaluate the two independent triggers.

        Returns a tuple ``(approval_required, reason)`` where reason is one of
        ``'credit_limit'`` / ``'overdue'`` / ``'both'`` / ``False``.
        """
        self.ensure_one()
        # Secondary / Distributor orders are exempt from credit control:
        # no credit-limit check and no approval workflow. They confirm directly.
        # (order_category is provided by the clearline_sales_custom module; use
        # getattr so this module still works if that module is not installed.)
        if getattr(self, 'order_category', False) == 'secondary_order':
            return False, False
        partner = self.partner_id.commercial_partner_id
        if not partner:
            return False, False
        credit_breach = self._check_credit_limit(partner)
        overdue = self._check_overdue(partner)
        if credit_breach and overdue:
            return True, 'both'
        if credit_breach:
            return True, 'credit_limit'
        if overdue:
            return True, 'overdue'
        return False, False

    def _check_credit_limit(self, partner):
        """Condition A - available-credit breach.

        Exposure = the customer's total amount due EXCLUDING this document, i.e.
        the same figure shown in Odoo's credit-warning banner:

            partner.credit            (posted invoice residuals, payment-status driven)
          + partner.credit_to_invoice (confirmed sales orders not yet invoiced)

        The order currently being created is NOT included (a draft quotation is
        not part of ``credit_to_invoice``). Approval is required when this
        existing amount due already exceeds a defined credit limit.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        partner_sudo = partner.sudo().with_company(company)
        credit_limit = partner_sudo.credit_limit
        if not credit_limit or credit_limit <= 0:
            # No defined limit -> condition A never triggers.
            return False
        # Total amount due excluding this document (matches the banner).
        exposure = partner_sudo.credit + partner_sudo.credit_to_invoice
        currency = self.currency_id or company.currency_id
        rounding = currency.rounding if currency else 0.01
        return float_compare(
            exposure, credit_limit, precision_rounding=rounding) > 0

    def _check_overdue(self, partner):
        """Condition B - any overdue payment.

        An open, posted customer invoice with residual > 0 whose due date is
        strictly before today. Zero grace days: an invoice becomes overdue the
        day after its due date.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        company = self.company_id or self.env.company
        domain = [
            ('company_id', '=', company.id),
            ('partner_id', 'child_of', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '>', 0.0),
            ('invoice_date_due', '!=', False),
            ('invoice_date_due', '<', today),
        ]
        return bool(self.env['account.move'].sudo().search_count(domain))

    def _credit_approval_message(self, reason):
        """Human-readable chatter/activity body describing why approval is
        required."""
        self.ensure_one()
        company = self.company_id or self.env.company
        partner = self.partner_id.commercial_partner_id.sudo().with_company(company)
        currency = self.currency_id or company.currency_id
        lines = [_(
            "Sale order %(name)s requires credit approval:",
            name=self.name or _('(new)'),
        )]
        if reason in ('credit_limit', 'both'):
            total_due = partner.credit + partner.credit_to_invoice
            lines.append(_(
                "• Credit limit breach - the customer's amount due %(out)s "
                "(invoices + confirmed sales orders) exceeds the credit limit "
                "%(limit)s. The amount of this order is not included.",
                out=self._format_amount(total_due, currency),
                limit=self._format_amount(partner.credit_limit, currency),
            ))
        if reason in ('overdue', 'both'):
            lines.append(_(
                "• Overdue payment - the customer has one or more posted "
                "invoices past their due date with an outstanding balance."))
        return "<br/>".join(lines)

    @staticmethod
    def _format_amount(amount, currency):
        try:
            return "%s %s" % (currency.symbol or '', "{:,.2f}".format(amount or 0.0))
        except Exception:
            return str(amount)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _start_credit_approval(self, reason):
        """Move the order to 'to_approve', post the reason on the chatter and
        schedule a to-do activity for every configured approver."""
        self.ensure_one()
        self.write({'approval_state': 'to_approve'})
        body = self._credit_approval_message(reason)
        self.message_post(body=body, subtype_xmlid='mail.mt_comment')

        approvers = self._get_credit_approvers()
        if not approvers:
            self.message_post(body=_(
                "No credit approvers are configured. Please define them in "
                "Sales \u25b8 Configuration \u25b8 Settings \u25b8 Credit Control."))
            return

        activity_type = self.env.ref(
            'sale_credit_control.mail_activity_credit_approval',
            raise_if_not_found=False)
        act_xmlid = (
            'sale_credit_control.mail_activity_credit_approval'
            if activity_type else 'mail.mail_activity_data_todo')
        for approver in approvers:
            self.activity_schedule(
                act_xmlid,
                user_id=approver.id,
                summary=_('Credit Approval Required'),
                note=body,
            )

    def _clear_credit_activities(self):
        """Mark the outstanding credit-approval activities as done."""
        self.ensure_one()
        activity_type = self.env.ref(
            'sale_credit_control.mail_activity_credit_approval',
            raise_if_not_found=False)
        domain = [('res_model', '=', 'sale.order'), ('res_id', '=', self.id)]
        if activity_type:
            domain.append(('activity_type_id', '=', activity_type.id))
        activities = self.env['mail.activity'].sudo().search(domain)
        if activities:
            activities.action_feedback(feedback=_('Credit approval processed.'))

    def _check_credit_approver(self):
        """Server-side enforcement: only configured approvers may act."""
        for order in self:
            if self.env.user not in order._get_credit_approvers():
                raise AccessError(_(
                    "Only users configured as Credit Approvers "
                    "(Sales \u25b8 Configuration \u25b8 Settings) can approve or "
                    "refuse credit-hold sale orders."))

    def _notify_salesperson(self, decision):
        self.ensure_one()
        user = self.user_id
        if not user or user == self.env.user:
            return
        if decision == 'approved':
            body = _("Credit approval for order %s was granted.", self.name)
        else:
            body = _("Credit approval for order %s was refused.", self.name)
        self.message_post(
            body=body,
            partner_ids=user.partner_id.ids,
            subtype_xmlid='mail.mt_comment',
        )

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_request_credit_approval(self):
        for order in self:
            required, reason = order._evaluate_credit_control()
            if not required:
                raise UserError(_(
                    "Order %s does not require credit approval.", order.name))
            if order.approval_state == 'approved':
                raise UserError(_("Order %s is already approved.", order.name))
            if order.approval_state == 'to_approve':
                raise UserError(_(
                    "Approval for order %s has already been requested.",
                    order.name))
            order._start_credit_approval(reason)
        return True

    def action_approve_credit(self):
        self._check_credit_approver()
        for order in self:
            if order.approval_state != 'to_approve':
                raise UserError(_(
                    "Only orders pending approval can be approved."))
            order.write({
                'approval_state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            order._clear_credit_activities()
            order.message_post(
                body=_("Credit approval granted by %s.", self.env.user.name),
                subtype_xmlid='mail.mt_comment')
            order._notify_salesperson('approved')
        return True

    def action_refuse_credit(self):
        self._check_credit_approver()
        for order in self:
            if order.approval_state != 'to_approve':
                raise UserError(_(
                    "Only orders pending approval can be refused."))
            order.write({
                'approval_state': 'refused',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            order._clear_credit_activities()
            order.message_post(
                body=_("Credit approval refused by %s.", self.env.user.name),
                subtype_xmlid='mail.mt_comment')
            order._notify_salesperson('refused')
        return True

    # ------------------------------------------------------------------
    # Confirmation gate
    # ------------------------------------------------------------------
    def action_confirm(self):
        confirmable = self.env['sale.order']
        started = self.env['sale.order']
        for order in self:
            # Already approved -> confirm normally.
            if order.approval_state == 'approved':
                confirmable |= order
                continue

            required, reason = order._evaluate_credit_control()
            if not required:
                # No trigger active -> clear any stale hold and confirm.
                if order.approval_state != 'not_required':
                    order.approval_state = 'not_required'
                confirmable |= order
                continue

            # A configured approver may confirm directly: doing so approves the
            # order (they do not have to go through request/approve). This is
            # also why the Confirm button stays visible for approvers.
            if self.env.user in order._get_credit_approvers():
                order.write({
                    'approval_state': 'approved',
                    'approved_by': self.env.user.id,
                    'approval_date': fields.Datetime.now(),
                })
                order._clear_credit_activities()
                order.message_post(
                    body=_("Credit approved directly by %s on confirmation.",
                           self.env.user.name),
                    subtype_xmlid='mail.mt_comment')
                confirmable |= order
                continue

            # Non-approver: block confirmation.
            if order.approval_state == 'to_approve':
                raise UserError(_(
                    "Order %s is on credit hold and is pending approval by a "
                    "credit approver. It cannot be confirmed yet.", order.name))
            if order.approval_state == 'refused':
                raise UserError(_(
                    "Credit approval for order %s was refused. It cannot be "
                    "confirmed.", order.name))

            # 'not_required' but a trigger is now active -> open the workflow.
            order._start_credit_approval(reason)
            started |= order

        result = (super(SaleOrder, confirmable).action_confirm()
                  if confirmable else False)

        if started:
            if not confirmable and len(started) == 1:
                # Reload the record so the user immediately sees the hold banner
                # and the Approve/Refuse buttons.
                return started._action_reload_form()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Credit approval required'),
                    'message': _(
                        '%s order(s) were placed on credit hold and now require '
                        'approval before they can be confirmed.', len(started)),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return result

    def _action_reload_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
