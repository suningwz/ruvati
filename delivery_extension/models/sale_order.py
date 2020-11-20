# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from odoo import api, fields, models, exceptions, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_ship_collect = fields.Boolean(string="Ship Collect")
    carrier_id = fields.Many2one("delivery.carrier", string="Carrier")
    shipper_number = fields.Char(string="Shipper No.")
    
    @api.onchange('partner_id')
    def ship_collect_onchange_partner(self):
        if self.partner_id and self.partner_id.is_ship_collect:
            self.is_ship_collect = self.partner_id.is_ship_collect
            self.carrier_id = self.partner_id.carrier_id
            self.shipper_number = self.partner_id.shipper_number
        else:
            self.is_ship_collect = False
            self.carrier_id = False
            self.shipper_number = False

    @api.onchange('is_ship_collect')
    def onchange_ship_collect(self):
        if not self.is_ship_collect:
            self.carrier_id = False
            self.shipper_number = False
        else:
            self.carrier_id = self.partner_id.carrier_id
            self.shipper_number = self.partner_id.shipper_number

SaleOrder()

