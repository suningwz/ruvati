# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    is_ship_collect = fields.Boolean(string="Ship Collect")
    carrier_id = fields.Many2one("delivery.carrier", string="Carrier")
    shipper_number = fields.Char(string="Shipper No.")
    is_home_depot = fields.Boolean(string="Home Depot")

    @api.onchange('is_ship_collect')
    def onchange_is_ship_collect(self):
        if not self.is_ship_collect:
            self.shipper_number = False
            self.carrier_id = False

    def _get_contact_name(self, partner, name):
        if partner.type == 'delivery':
            return "%s" % (name)
        return super(ResPartner, self)._get_contact_name(partner, name)

ResPartner()


class ResUser(models.Model):
    _inherit = "res.users"

    @api.model
    def create(self, vals):
        res = super(ResUser, self).create(vals)
        res.groups_id = [(4, self.env.ref('delivery_extension.group_internal_common_user').id)]
        # vals.update({'groups_id': [(4, self.env.ref('delivery_extension.group_internal_common_user').id, False)]})
        return res
