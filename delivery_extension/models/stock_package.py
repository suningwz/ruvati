from odoo import models, fields


class StockQuantPackage(models.Model):
    _name = "stock.quant.package"
    _inherit = ['stock.quant.package','mail.thread']

    label_data = fields.Binary("Label", attachment=True)
    file_name = fields.Char('File Name')
    label_id = fields.Many2one('ir.attachment', string="Attachment LAbel")

