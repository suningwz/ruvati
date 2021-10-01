from odoo import models, fields, api
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_amazon_customer = fields.Boolean('Customer ID')

    @api.onchange('phone', 'zip')
    def check_zip_phone_validation(self):
        for rec in self:
            phone = ''.join(e for e in rec.phone if e.isalnum())
            if len(phone) < 10 or not phone.isnumeric():
                raise UserError("Phone number is incorrect for this customer")
            zip = ''.join(e for e in rec.zip if e.isalnum())
            if len(zip) < 5 or not zip.isnumeric():
                raise UserError("Zip Code is incorrect for this customer")
        return
