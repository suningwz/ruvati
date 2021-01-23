# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from itertools import groupby
from odoo import api, fields, models, exceptions, _, tools
from odoo.exceptions import UserError
from odoo.tools import pdf
from odoo.addons.delivery_fedex.models.fedex_request import FedexRequest

_logger = logging.getLogger(__name__)


class FedexRequestShipCollect(FedexRequest):

    def shipping_charges_payment_ship_collect(self, shipping_charges_payment_account):
        self.RequestedShipment.ShippingChargesPayment = self.factory.Payment()
        self.RequestedShipment.ShippingChargesPayment.PaymentType = 'RECIPIENT'
        Payor = self.factory.Payor()
        Payor.ResponsibleParty = self.factory.Party()
        Payor.ResponsibleParty.AccountNumber = shipping_charges_payment_account
        self.RequestedShipment.ShippingChargesPayment.Payor = Payor

