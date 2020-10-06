# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _

_WAREHOUSE = [
    ('main_warehouse', 'Main Warehouse'),
    ('sub_warehouse', 'Secondary Warehouse'),
    ('ocean', 'Ocean')]

class Location(models.Model):
    _inherit = "stock.warehouse"

    warehouse_type = fields.Selection(_WAREHOUSE, 'Warehouse')

Location()
