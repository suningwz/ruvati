# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, tools, SUPERUSER_ID
_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def _get_pricelist_available(self, req, show_visible=False):
        """ Return the list of pricelists that can be used on website for the current user.
        Country restrictions will be detected with GeoIP (if installed).
        :param bool show_visible: if True, we don't display pricelist where selectable is False (Eg: Code promo)
        :returns: pricelist recordset
        """
        partner = self.env.user.partner_id
        partner_pl = partner.with_user(self.env.user).property_product_pricelist
        return partner_pl
