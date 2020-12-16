# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_po_number = fields.Char(string="Customer PO Number")

SaleOrder()
