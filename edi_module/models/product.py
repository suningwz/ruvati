from odoo import models, fields, api


class Product(models.Model):
    _inherit = 'product.template'

    edi_customer_ids = fields.One2many('edi.customer', 'product_id', string="EDI Customer")


class EdiCustomer(models.Model):
    _name = 'edi.customer'

    product_id = fields.Many2one('product.product', string="Product")
    partner_id = fields.Many2one('res.partner', string="Customer")
    customer_id = fields.Char("Customer ID")
    sale_approved_price = fields.Float("Price")
    sku_product_id = fields.Char("SKU ID")

    @api.onchange('partner_id')
    def partner_onchange(self):
        self.write({'customer_id': self.partner_id.customer_id})
