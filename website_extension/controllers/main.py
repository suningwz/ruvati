# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request


class WebsiteSalePoUpdate(WebsiteSale):

    @http.route(['/shop/poupdate'], type='http', auth="public", website=True, sitemap=False)
    def po_update(self, po_ref, **post):
        order = request.website.sale_get_order()
        print(order.id)
        order.write({'client_order_ref': po_ref})
        return request.redirect('/shop/cart')
