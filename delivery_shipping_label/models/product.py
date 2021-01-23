from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = "product.template"

    height = fields.Integer("Height")
    width = fields.Integer("Width")
    length = fields.Integer("Length")
