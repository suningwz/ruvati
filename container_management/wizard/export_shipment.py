# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ShipmentReportExcel(models.TransientModel):

    _name = "po.shipment.excel"
    _description = "Shipment Report"


    data = fields.Binary(string='File', readonly=True)
    name = fields.Char(string='Filename', readonly=True)

