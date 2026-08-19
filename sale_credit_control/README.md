# Sales Credit Control (Odoo 19)

Adds a **credit-control approval workflow** to Sale Orders. When confirming an
order would breach the customer's available credit **or** the customer has any
overdue payment, the order is placed on **credit hold** and must be approved by
a configured approver before it can be confirmed.

## Installation

1. Copy the `sale_credit_control` folder into your Odoo 19 addons path
   (on Odoo.sh, commit it to your repository).
2. Update the apps list and install **Sales Credit Control**.
   Dependencies (`sale_management`, `account`) are installed automatically.

## Setup — where to set approvers

1. Go to **Sales ▸ Configuration ▸ Settings**.
2. In the **Credit Control** section, add one or more users to
   **Credit Approvers** and save.
3. Set a customer's **Credit Limit** on the customer form
   (*Sales / Accounting* tab). A limit of `0` disables the credit-limit trigger
   for that customer; the overdue trigger still applies.

> Tip: the credit-limit field on the partner is provided by the Accounting app.
> If you don't see it, enable *Sales Credit Limit* in **Invoicing/Accounting ▸
> Settings** (native Odoo setting `use_partner_credit_limit`). The exposure
> logic in this module works regardless of that toggle.

## How the triggers work

On pressing the native **Confirm** button, the order is evaluated against two
**independent** conditions. If **either** fires, confirmation is blocked and the
order moves to *To Approve*.

**Condition A — available-credit breach**
Exposure is driven by the *payment status* of the customer's invoices, using the
native outstanding receivable (`res.partner.credit` = sum of unpaid residuals):

- fully **paid** invoice → consumes no credit;
- **partially** paid → consumes only the remaining residual;
- **unpaid** → consumes its full amount.

```
amount due = partner.credit + partner.credit_to_invoice
approval needed  ⇔ amount due > credit_limit   (only when credit_limit > 0)
```

where `partner.credit` is the posted-invoice residual (payment-status driven)
and `partner.credit_to_invoice` is the amount from **confirmed sales orders**
not yet invoiced. This is the same total Odoo shows in its credit-warning
banner.

> The amount of the order **currently being created is not counted** toward this
> check (a draft quotation is not part of `credit_to_invoice`). Approval is
> triggered when the customer's *existing* amount due already exceeds the limit.

**Condition B — overdue payment (zero grace days)**
Any posted customer invoice with residual `> 0` whose **due date is before
today** puts the customer on hold, even when the credit limit is not breached.
An invoice is overdue the day after its due date (no grace period).

If neither condition is met, the order confirms normally.

## The approval workflow

| Field | Meaning |
|-------|---------|
| `approval_required` | Live-computed flag (credit breach / overdue). |
| `approval_reason` | `credit_limit` / `overdue` / `both`. |
| `approval_state` | `not_required` → `to_approve` → `approved` / `refused`. |
| `approved_by`, `approval_date` | Who released/refused it, and when. |

- While an order needs approval and is not yet approved, the native **Confirm**
  button is **hidden** for regular users; they see **Request Approval** instead.
  Once the order is *Approved*, the Confirm button **reappears** and the user
  can confirm normally.
- **Request Approval** moves the order to *To Approve*, posts a chatter message
  stating the reason, and schedules a **Credit Approval** to-do activity for
  **each** configured approver.
- **Approve Credit / Refuse Credit** are usable **only** by configured
  approvers. This is enforced **server-side** in the methods
  (`_check_credit_approver`) — not merely by UI visibility. The buttons are also
  hidden from non-approvers via the technical `can_approve_credit` field.
- Any **one** approver approving is sufficient: the order becomes *Approved* and
  then confirms normally through the native Confirm button.
- **Approvers bypass the workflow:** the Confirm button stays visible for a
  configured approver even on a credit-hold order, and pressing it confirms the
  order directly (recorded as an approval by that user). They never have to
  request or wait for approval.
- The salesperson is notified on the chatter when their order is approved or
  refused.

## Notifications

- One `mail.activity` ("Credit Approval") per configured approver.
- A chatter message on the sale order citing the credit-limit breach and/or the
  overdue payment.

## Security

This module adds **no new models** — approvers are stored on `res.company` and
surfaced through `res.config.settings`. Consequently no `ir.model.access.csv`
is required. The approve/refuse authorization is enforced in the Python methods
themselves, so it cannot be bypassed from the UI, the API, or automated actions.
Single company / single currency is assumed, so no record rules are added.

## Acceptance test (matches the spec)

1. Customer credit limit = `500000`; approvers = User A, User B.
2. Confirm + invoice a `300000` order, leave it **unpaid** (outstanding
   `300000`, available `200000`).
3. New `300000` order → exposure `600000 > 500000` → **Confirm is blocked**, the
   order goes **To Approve**, and User A & User B each receive an activity +
   chatter message citing *credit limit*.
4. Approve as User A → the order can now be confirmed (User B not needed).
5. Fully **pay** the first invoice, then create a new `300000` order → it
   confirms **without** approval (full `500000` available again).
6. A customer within limit but with an **overdue** unpaid invoice → a new order
   requires approval citing *overdue payment*.
7. A user **not** in the approvers list attempting to approve is **blocked**
   (server-side `AccessError`).
