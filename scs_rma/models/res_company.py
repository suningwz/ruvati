
from odoo import fields, models


class ResCompany(models.Model):
    """inherited data model for ResCompany."""

    _inherit = "res.company"

    source_location_id = fields.Many2one('stock.location',
                                         string='Source Location',
                                         )
    destination_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
    )
    sup_source_location_id = fields.Many2one('stock.location',
                                             string='Source Location',
                                             )
    sup_destination_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
    )
