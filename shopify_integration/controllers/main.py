# controllers/main.py

from odoo import http
from odoo.http import request

import requests


class ShopifyController(http.Controller):

    @http.route(
        '/shopify/callback',
        type='http',
        auth='public',
        csrf=False
    )
    def shopify_callback(self, **kwargs):

        code = kwargs.get("code")
        shop = kwargs.get("shop")

        if not code:
            return "Authorization code missing"

        if not shop:
            return "Shop missing"

        config = request.env['shopify.config'].sudo().search([
            ('shop_url', '=', shop)
        ], limit=1)

        if not config:
            return "Shopify configuration not found"

        token_url = f"https://{shop}/admin/oauth/access_token"

        payload = {
            "client_id": config.api_key,
            "client_secret": config.api_secret,
            "code": code,
        }

        response = requests.post(token_url, json=payload)

        data = response.json()

        if response.status_code != 200:
            return str(data)

        access_token = data.get("access_token")

        if not access_token:
            return "Access token not received"

        # SAVE PERMANENT TOKEN
        config.sudo().write({
            "access_token": access_token
        })

        return """
            <h1>Shopify Connected Successfully</h1>
            <h3>Permanent Offline Token Saved</h3>
        """