from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_id = fields.Char('Customer ID')
