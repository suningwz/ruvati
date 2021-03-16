from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_id = fields.Char('Customer ID')

    def write(self, vals):
        for rec in self:
            if vals.get('customer_id', False):
                edi_partner_ids = self.env['edi.customer'].search([('partner_id', '=', rec.id)])
                edi_partner_ids.write({'customer_id': vals.get('customer_id')})

        return super(ResPartner, self).write(vals)
