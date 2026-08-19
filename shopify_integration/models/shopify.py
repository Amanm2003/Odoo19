import requests
import urllib
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timezone
import logging

_logger = logging.getLogger(__name__)

class ShopifyIntegration(models.Model):
    _name = "shopify.integration"
    _description = "Shopify Integration Configuration"

    name = fields.Char(string="Instance Name", required=True)
    shop_url = fields.Char(string="Shopify Store URL", required=True)
    api_key = fields.Char(string="API Key", required=True)
    password = fields.Char(string="Password", required=True)
    api_version = fields.Char(string="API Version", default="2026-10")
    
    access_token = fields.Char( string="Access Token",  store=True)
    auth_code = fields.Char(string="Authorization Code")
    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string="Status", default='draft', copy=False)
    
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    
    shopify_order_count = fields.Integer(
        string="Shopify Orders",
        compute="_compute_shopify_order_count",
    )

    @api.depends()
    def _compute_shopify_order_count(self):
        SaleOrder = self.env["sale.order"]
        for rec in self:
            rec.shopify_order_count = SaleOrder.search_count([
                ("is_shopify_order", "=", True),
            ])

    def action_view_shopify_orders(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Shopify Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("is_shopify_order", "=", True)],
            "context": {
                "search_default_is_shopify_order": 1,
            },
        }
    
    def action_generate_access_token(self):
        for record in self:
            if not record.api_key or not record.password:
                raise UserError("API Key and Password are required.")

            if not record.shop_url:
                raise UserError("Shop URL is required.")

            # Clean shop URL (remove https:// if user included it)
            shop_url = record.shop_url.replace("https://", "").replace("http://", "").strip("/")

            url = f"https://{shop_url}/admin/api/{record.api_version}/shop.json"

            try:
                response = requests.get(
                    url,
                    auth=(record.api_key, record.password),
                    timeout=10
                )
            except requests.exceptions.ConnectionError:
                raise UserError(f"Could not connect to Shopify store: {shop_url}\nCheck your Store URL.")
            except requests.exceptions.Timeout:
                raise UserError("Request timed out. Please try again.")

            if response.status_code == 401:
                raise UserError("Invalid API Key or Password. Please check your credentials.")
            elif response.status_code == 403:
                raise UserError("Access forbidden. Make sure your Private App has the required permissions.")
            elif response.status_code != 200:
                raise UserError(f"Failed to connect to Shopify:\n{response.text}")

            # For Private Apps, the password IS the access token
            record.access_token = record.password

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Success",
                    "message": f"Access token generated successfully for {record.name}!",
                    "type": "success",
                    "sticky": False,
                }
            }
    
    
    # def action_get_auth_url(self):

    #     self.ensure_one()

    #     # YOUR ODOO CALLBACK URL
    #     redirect_uri = "http://localhost:8070/shopify/callback"

    #     scopes = [
    #         "read_all_orders","read_analytics","write_app_proxy","read_apps","write_assigned_fulfillment_order","read_audit_events","read_customer_events","write_cart_transforms","read_all_cart_transforms","write_validations","write_cash_tracking","write_channels","write_checkout_branding_settings","write_checkouts","write_companies","write_custom_fulfillment_services","write_custom_pixels","write_customers","write_customer_data_erasure","read_customer_payment_methods","write_customer_merge","write_delivery_customizations","write_price_rules","write_discounts","write_discounts_allocator_functions","write_discovery","write_draft_orders","write_files","write_fulfillment_constraint_rules","write_fulfillments","write_gift_card_transactions","write_gift_cards","write_inventory","write_inventory_shipments","write_inventory_shipments_received_items","write_inventory_transfers","write_legal_policies","write_delivery_option_generators","write_locales","write_locations","write_marketing_integrated_campaigns","write_marketing_events","write_markets","write_markets_home","write_merchant_managed_fulfillment_orders","write_metaobject_definitions","write_metaobjects","write_online_store_navigation","write_online_store_pages","write_order_edits","write_orders","write_packing_slip_templates","write_payment_mandate","write_payment_terms","write_payment_customizations","write_pixels","write_privacy_settings","write_product_feeds","write_product_listings","write_products","write_publications","write_purchase_options","write_reports","write_resource_feedbacks","write_returns","write_script_tags","read_shopify_payments_provider_accounts_sensitive","write_shipping","read_shopify_payments_accounts","read_shopify_payments_payouts","read_shopify_payments_bank_accounts","write_shopify_payments_disputes","write_content","write_store_credit_account_transactions","read_store_credit_accounts","write_own_subscription_contracts","write_theme_code","write_themes","write_third_party_fulfillment_orders","write_translations","customer_write_companies","customer_write_customers","customer_read_draft_orders","customer_read_markets","customer_read_metaobjects","customer_write_orders","customer_write_quick_sale","customer_read_store_credit_account_transactions","customer_read_store_credit_accounts","customer_write_own_subscription_contracts","unauthenticated_write_bulk_operations","unauthenticated_read_bundles","unauthenticated_write_checkouts","unauthenticated_write_customers","unauthenticated_read_customer_tags","unauthenticated_read_metaobjects","unauthenticated_read_product_pickup_locations","unauthenticated_read_product_inventory","unauthenticated_read_product_listings","unauthenticated_read_product_tags","unauthenticated_read_selling_plans","unauthenticated_read_shop_pay_installments_pricing","unauthenticated_read_content",
        
    #     ]

    #     params = {
    #         "client_id": self.api_key,
    #         "scope": ",".join(scopes),
    #         "redirect_uri": redirect_uri,
    #     }

    #     auth_url = (
    #         f"https://{self.shop_url}/admin/oauth/authorize?"
    #         + urllib.parse.urlencode(params)
    #     )

    #     return {
    #         "type": "ir.actions.act_url",
    #         "url": auth_url,
    #         "target": "new",
    #     }

    # def generate_access_token(self):

    #     for record in self:

    #         if not record.api_key or not record.password:
    #             raise UserError("API Key and API Secret are required.")

    #         if not record.auth_code:
    #             raise UserError(
    #                 "Authorization code not found.\n"
    #                 "Please authorize the app first."
    #             )

    #         url = f"https://{record.shop_url}/admin/oauth/access_token"

    #         payload = {
    #             "client_id": record.api_key,
    #             "client_secret": record.password,
    #             "code": record.auth_code,
    #         }

    #         response = requests.post(url, json=payload)

    #         if response.status_code != 200:
    #             raise UserError(
    #                 f"Failed to generate token:\n{response.text}"
    #             )

    #         data = response.json()

    #         record.access_token = data.get("access_token")

    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": "Success",
    #                 "message": "Shopify access token generated successfully.",
    #                 "type": "success",
    #             }
    #         }
    
    
    def action_connect_shopify(self):
        """
        Generate Shopify authorization URL
        Open only ONE TIME for permanent offline token
        """

        self.ensure_one()

        redirect_uri = "https://throng-viewer-flyer.ngrok-free.dev/shopify/callback"

        scopes = [
            "read_all_orders","read_analytics","write_app_proxy","read_apps","write_assigned_fulfillment_order","read_audit_events","read_customer_events","write_cart_transforms","read_all_cart_transforms","write_validations","write_cash_tracking","write_channels","write_checkout_branding_settings","write_checkouts","write_companies","write_custom_fulfillment_services","write_custom_pixels","write_customers","write_customer_data_erasure","read_customer_payment_methods","write_customer_merge","write_delivery_customizations","write_price_rules","write_discounts","write_discounts_allocator_functions","write_discovery","write_draft_orders","write_files","write_fulfillment_constraint_rules","write_fulfillments","write_gift_card_transactions","write_gift_cards","write_inventory","write_inventory_shipments","write_inventory_shipments_received_items","write_inventory_transfers","write_legal_policies","write_delivery_option_generators","write_locales","write_locations","write_marketing_integrated_campaigns","write_marketing_events","write_markets","write_markets_home","write_merchant_managed_fulfillment_orders","write_metaobject_definitions","write_metaobjects","write_online_store_navigation","write_online_store_pages","write_order_edits","write_orders","write_packing_slip_templates","write_payment_mandate","write_payment_terms","write_payment_customizations","write_pixels","write_privacy_settings","write_product_feeds","write_product_listings","write_products","write_publications","write_purchase_options","write_reports","write_resource_feedbacks","write_returns","write_script_tags","read_shopify_payments_provider_accounts_sensitive","write_shipping","read_shopify_payments_accounts","read_shopify_payments_payouts","read_shopify_payments_bank_accounts","write_shopify_payments_disputes","write_content","write_store_credit_account_transactions","read_store_credit_accounts","write_own_subscription_contracts","write_theme_code","write_themes","write_third_party_fulfillment_orders","write_translations","customer_write_companies","customer_write_customers","customer_read_draft_orders","customer_read_markets","customer_read_metaobjects","customer_write_orders","customer_write_quick_sale","customer_read_store_credit_account_transactions","customer_read_store_credit_accounts","customer_write_own_subscription_contracts","unauthenticated_write_bulk_operations","unauthenticated_read_bundles","unauthenticated_write_checkouts","unauthenticated_write_customers","unauthenticated_read_customer_tags","unauthenticated_read_metaobjects","unauthenticated_read_product_pickup_locations","unauthenticated_read_product_inventory","unauthenticated_read_product_listings","unauthenticated_read_product_tags","unauthenticated_read_selling_plans","unauthenticated_read_shop_pay_installments_pricing","unauthenticated_read_content",
        ]

        params = {
            "client_id": self.api_key,
            "scope": ",".join(scopes),

            # IMPORTANT:
            # DO NOT USE grant_options[]=per-user
            # otherwise token becomes temporary

            "redirect_uri": redirect_uri,
        }

        auth_url = (
            f"https://{self.shop_url}/admin/oauth/authorize?"
            + urllib.parse.urlencode(params)
        )

        return {
            "type": "ir.actions.act_url",
            "url": auth_url,
            "target": "new",
        }
        



    def test_shopify_connection(self):
        """Test Shopify connection using the saved access token."""

        self.ensure_one()

        if not self.shop_url:
            raise UserError("Please enter the Shopify Store URL.")

        if not self.password:
            raise UserError("Please enter the Shopify Access Token.")

        headers = {
            "X-Shopify-Access-Token": self.password,
            "Content-Type": "application/json",
        }

        url = f"https://{self.shop_url}/admin/api/{self.api_version}/shop.json"

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=20,
            )

            if response.status_code == 200:
                self.state = "connected"

                # return {
                #     "type": "ir.actions.client",
                #     "tag": "display_notification",
                #     "params": {
                #         "title": ("Success"),
                #         "message": ("Successfully connected to Shopify."),
                #         "type": "success",
                #         "sticky": False,
                #     },
                # }
                return {
                    "type":"ir.actions.client",
                    "tag":"reload",
                }
                
            else:
                self.state = "draft"
                # return {
                #     "type": "ir.actions.client",
                #     "tag": "display_notification",
                #     "params": {
                #         "title": "Failed",
                #         "message": "Connection failed.",
                #         "type": "danger",
                #         "sticky": False,
                #     },
                # }
                return {
                    "type":"ir.actions.client",
                    "tag":"reload",
                }

            # try:
            #     error = response.json().get("errors", response.text)
            # except Exception:
            #     error = response.text

                # raise UserError("Connection failed.")

        except requests.exceptions.RequestException as e:
            self.state = "draft"
            raise UserError("Unable to connect to Shopify.")

    # def test_shopify_connection(self):
    #     """
    #     Test saved permanent token
    #     """

    #     self.ensure_one()

    #     if not self.password:
    #         raise UserError("Shopify access token not found.")

    #     headers = {
    #         "X-Shopify-Access-Token": self.password,
    #         "Content-Type": "application/json",
    #     }

    #     url = f"https://{self.shop_url}/admin/api/2025-01/shop.json"

    #     response = requests.get(url, headers=headers)

    #     if response.status_code == 200:
    #         self.state='connected'
    #         raise UserError("Shopify Connected Successfully")
    #     else:
    #         self.state = 'draft'

    #     raise UserError(response.text)
    

    def fetch_products(self):
        integrations = self.env["shopify.integration"].search([
            ("state", "=", "connected")
        ])
        for record in integrations:
            
            url = f"https://{record.shop_url}/admin/api/{record.api_version}/products.json"
            headers = {
                "X-Shopify-Access-Token": record.password,
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                products = response.json().get("products", [])
                for prod in products:
                    vals = {
                        "name": prod["title"],
                        "shopify_name": prod["title"],
                        "default_code": prod["id"],
                        "list_price": float(prod["variants"][0]["price"]) if prod["variants"] else 0.0,
                    }
                    existing = self.env['product.product'].search([('shopify_name', '=', prod["title"])], limit=1)
                    if existing:
                        existing.write(vals)
                    else:
                        self.env['product.product'].create(vals)
            else:
                # Raise error to see immediately
                raise Exception(f"Shopify API Error {response.status_code}: {response.text}")

    def fetch_customers(self):
        integrations = self.env["shopify.integration"].search([
            ("state", "=", "connected")
        ])
        for record in integrations:
            url = f"https://{record.api_key}:{record.password}@{record.shop_url}/admin/api/{record.api_version}/customers.json"
            response = requests.get(url)
            if response.status_code == 200:
                customers = response.json().get("customers", [])
                for cust in customers:
                    vals = {
                        "name": f"{cust['first_name']} {cust['last_name']}",
                        "email": cust["email"],
                    }
                    existing = self.env['res.partner'].search([('email', '=', cust["email"])], limit=1)
                    if existing:
                        # existing.write(vals)
                        continue
                    else:
                        self.env['res.partner'].create(vals)
            # else:
            #     _logger = self.env['ir.logging']
            #     _logger.sudo().create({
            #         'name': 'Shopify Sync Error',
            #         'type': 'server',
            #         'message': f"Failed to fetch customers: {response.text}",
            #         'level': 'ERROR',
            #     })

    # def fetch_orders(self):
    #     integrations = self.env["shopify.integration"].search([
    #         ("state", "=", "connected")
    #     ])

    #     for record in integrations:

    #         url = f"https://{record.shop_url}/admin/api/{record.api_version}/orders.json?status=any"

    #         headers = {
    #             "X-Shopify-Access-Token": record.password,
    #             "Content-Type": "application/json",
    #         }

    #         response = requests.get(url, headers=headers)

    #         if response.status_code != 200:
    #             raise UserError(
    #                 f"Shopify Order API Error {response.status_code}: {response.text}"
    #             )

    #         orders = response.json().get("orders", [])

    #         for order in orders:

    #             # ---------------------------------------------
    #             # CHECK IF ORDER ALREADY EXISTS
    #             # ---------------------------------------------

    #             existing_sale = self.env['sale.order'].search(
    #                 [('client_order_ref', '=', order.get("name"))],
    #                 limit=1
    #             )

    #             if existing_sale:
    #                 continue

    #             # ---------------------------------------------
    #             # CUSTOMER
    #             # ---------------------------------------------

    #             customer = order.get("customer")

    #             partner = False

    #             if customer:

    #                 customer_email = customer.get("email")

    #                 partner = self.env['res.partner'].search(
    #                     [('email', '=', customer_email)],
    #                     limit=1
    #                 )

    #                 if not partner:

    #                     partner_vals = {
    #                         "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
    #                         "email": customer_email,
    #                         "phone": customer.get("phone"),
    #                     }

    #                     partner = self.env['res.partner'].create(partner_vals)

    #             # Guest customer
    #             if not partner:
    #                 partner = self.env['res.partner'].create({
    #                     "name": order.get("name"),
    #                 })

    #             # ---------------------------------------------
    #             # SALE ORDER LINES
    #             # ---------------------------------------------

    #             order_lines = []

    #             for line in order.get("line_items", []):

    #                 shopify_product_id = str(line.get("product_id"))

    #                 product = self.env['product.product'].search(
    #                     [('shopify_name', '=', line.get("title"))],
    #                     limit=1
    #                 )

    #                 # Create product if not found
    #                 if not product:

    #                     product_vals = {
    #                         "name": line.get("title"),
    #                         "shopify_name":line.get("title"),
    #                         "default_code": shopify_product_id,
    #                         "list_price": float(line.get("price", 0)),
    #                     }

    #                     product = self.env['product.product'].create(product_vals)

    #                 line_vals = (0, 0, {
    #                     "product_id": product.id,
    #                     "name": line.get("title"),
    #                     "product_uom_qty": line.get("quantity", 1),
    #                     "price_unit": float(line.get("price", 0)),
    #                 })

    #                 order_lines.append(line_vals)

    #             # ---------------------------------------------
    #             # CREATE SALE ORDER
    #             # ---------------------------------------------

    #             sale_order_vals = {
    #                 "company_id": record.company_id.id,
    #                 "partner_id": partner.id,
    #                 "is_shopify_order": True,
    #                 "client_order_ref": order.get("name"),
    #                 "note": f"Imported from Shopify Order ID: {order.get('id')}",
    #                 "order_line": order_lines,
    #             }

    #             sale_order = self.env['sale.order'].create(sale_order_vals)

    #             # Optional: Confirm Sale Order Automatically
    #             sale_order.action_confirm()
    
    def fetch_orders(self):
        integrations = self.env["shopify.integration"].search([
            ("state", "=", "connected")
        ])

        for record in integrations:

            headers = {
                "X-Shopify-Access-Token": record.password,
                "Content-Type": "application/json",
            }

            url = (
                f"https://{record.shop_url}/admin/api/{record.api_version}"
                f"/orders.json?status=any&limit=250&order=created_at+desc"
            )

            _logger.info("Fetching latest 250 Shopify orders for %s", record.shop_url)

            try:
                response = requests.get(url, headers=headers, timeout=30)
            except requests.exceptions.RequestException as e:
                raise UserError(f"Shopify Order API connection failed: {e}")

            if response.status_code != 200:
                raise UserError(
                    f"Shopify Order API Error {response.status_code}: {response.text}"
                )

            orders = response.json().get("orders", [])

            for order in orders:

                try:

                    # ---------------------------------------------
                    # CHECK IF ORDER ALREADY EXISTS
                    # ---------------------------------------------

                    existing_sale = self.env['sale.order'].search(
                        [('client_order_ref', '=', order.get("name"))],
                        limit=1
                    )

                    if existing_sale:
                        continue

                    # ---------------------------------------------
                    # CUSTOMER
                    # ---------------------------------------------

                    customer = order.get("customer")
                    partner = False

                    if customer:

                        shopify_customer_id = str(customer.get("id")) if customer.get("id") else False
                        customer_email = customer.get("email")

                        if shopify_customer_id:
                            partner = self.env['res.partner'].search(
                                [('shopify_customer_id', '=', shopify_customer_id)], limit=1
                            )

                        if not partner and customer_email:
                            partner = self.env['res.partner'].search(
                                [('email', '=', customer_email)], limit=1
                            )

                        # A matched partner locked to a different company than this
                        # order would cause "company crossover" errors on create().
                        shipping_address = order.get("shipping_address") or {}
                        if partner and partner.company_id and partner.company_id.id != self.env.company.id:
                            partner.sudo().write({"company_id": False})
                        if partner:
                            partner.sudo().write({  "street": shipping_address.get("address1") or "",
                                                    "street2": shipping_address.get("address2") or "",
                                                    "city": shipping_address.get("city") or "",
                                                    "zip": shipping_address.get("zip") or "",
                                                    })
                            

                        if not partner:
                            
                            partner_vals = {
                                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                                        or order.get("name"),
                                "email": customer_email,
                                "phone": customer.get("phone"),
                                "shopify_customer_id": shopify_customer_id,
                                "company_id": False,
                                "street": shipping_address.get("address1") or "",
                                "street2": shipping_address.get("address2") or "",
                                "city": shipping_address.get("city") or "",
                                "zip": shipping_address.get("zip") or "",
                            }
                            partner = self.env['res.partner'].create(partner_vals)

                    # Guest customer
                    if not partner:
                        partner = self.env['res.partner'].create({
                            "name": order.get("name"),
                            "company_id": False,
                        })

                    # ---------------------------------------------
                    # SALE ORDER LINES — use Shopify's actual paid price
                    # ---------------------------------------------

                    order_lines = []

                    for line in order.get("line_items", []):

                        shopify_product_id = str(line.get("product_id"))
                        qty = line.get("quantity", 1) or 1

                        # Shopify's line "price" is the pre-discount unit price.
                        # Sum per-line discount_allocations and express as a
                        # percentage so Odoo's discount field reflects what the
                        # customer actually paid.
                        unit_price = float(line.get("price", 0))
                        discount_total = sum(
                            float(d.get("amount", 0))
                            for d in line.get("discount_allocations", [])
                        )
                        discount_percent = (
                            (discount_total / (unit_price * qty)) * 100
                            if unit_price and qty else 0.0
                        )

                        product = self.env['product.product'].search(
                            [('shopify_name', '=', line.get("title"))],
                            limit=1
                        )

                        if not product:
                            product_vals = {
                                "name": line.get("title"),
                                "shopify_name": line.get("title"),
                                "default_code": shopify_product_id,
                                "list_price": unit_price,
                            }
                            product = self.env['product.product'].create(product_vals)

                        line_vals = (0, 0, {
                            "product_id": product.id,
                            "name": line.get("title"),
                            "product_uom_qty": qty,
                            "price_unit": unit_price / 1.18,
                            "discount": round(discount_percent, 2),
                        })

                        order_lines.append(line_vals)

                    # ---------------------------------------------
                    # CREATE SALE ORDER
                    # ---------------------------------------------

                    sale_order_vals = {
                        "partner_id": partner.id,
                        "company_id": record.env.company.id,
                        "is_shopify_order": True,
                        "client_order_ref": order.get("name"),
                        "date_order": self._parse_shopify_datetime(order.get("created_at")),
                        "note": f"Imported from Shopify Order ID: {order.get('id')}",
                        "order_line": order_lines,
                        "shopify_id": order.get("name"),
                    }

                    sale_order = self.env['sale.order'].create(sale_order_vals)

                    # Optional: Confirm Sale Order Automatically
                    sale_order.action_confirm()
                    # invoice = sale_order._create_invoices()
                    # if invoice and invoice.state == 'draft':
                    #     invoice.action_post()

                except Exception as e:
                    # Don't let one bad order kill the whole run
                    _logger.error(
                        "Failed to import Shopify order %s: %s",
                        order.get("name"), e
                    )
                    self.env.cr.rollback()
                    continue

            self.env.cr.commit()

            _logger.info(
                "Finished Shopify order import for %s: %s orders fetched",
                record.shop_url, len(orders)
            )
                
    @api.model
    def _parse_shopify_datetime(self, value):
        """Convert a Shopify ISO 8601 timestamp (e.g. '2026-07-23T19:17:47+05:30')
        into a naive UTC datetime, which is what Odoo's Datetime fields expect."""
        if not value:
            return fields.Datetime.now()
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, TypeError) as e:
            _logger.warning("Could not parse Shopify datetime '%s': %s", value, e)
            return fields.Datetime.now()