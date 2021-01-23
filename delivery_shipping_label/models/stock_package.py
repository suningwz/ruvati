from odoo import models, fields


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    height = fields.Integer("Height")
    width = fields.Integer("Width")
    length = fields.Integer("lengh")
