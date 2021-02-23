# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from itertools import groupby
from odoo import api, fields, models, exceptions, _, tools
from odoo.exceptions import UserError
from odoo.tools import pdf
from odoo.addons.delivery_fedex.models.fedex_request import FedexRequest
from odoo.tools import remove_accents

_logger = logging.getLogger(__name__)

STATECODE_REQUIRED_COUNTRIES = ['US', 'CA', 'PR ', 'IN']


class FedexRequestShipCollect(FedexRequest):

    def shipping_charges_payment_ship_collect(self, shipping_charges_payment_account):
        self.RequestedShipment.ShippingChargesPayment = self.factory.Payment()
        self.RequestedShipment.ShippingChargesPayment.PaymentType = 'RECIPIENT'
        Payor = self.factory.Payor()
        Payor.ResponsibleParty = self.factory.Party()
        Payor.ResponsibleParty.AccountNumber = shipping_charges_payment_account
        self.RequestedShipment.ShippingChargesPayment.Payor = Payor

    def set_recipient(self, recipient_partner):
        Contact = self.factory.Contact()
        if recipient_partner.is_company:
            Contact.PersonName = ''
            Contact.CompanyName = remove_accents(recipient_partner.name)
        else:
            Contact.PersonName = remove_accents(recipient_partner.name)
            Contact.CompanyName = remove_accents(recipient_partner.commercial_company_name) or ''
        Contact.PhoneNumber = recipient_partner.phone or ''

        Address = self.factory.Address()
        Address.StreetLines = [remove_accents(recipient_partner.street) or '']
        if recipient_partner.street2:
            Address.StreetLines.append(remove_accents(recipient_partner.street2))
        Address.City = remove_accents(recipient_partner.city) or ''
        if recipient_partner.country_id.code in STATECODE_REQUIRED_COUNTRIES:
            Address.StateOrProvinceCode = recipient_partner.state_id.code or ''
        else:
            Address.StateOrProvinceCode = ''
        Address.PostalCode = recipient_partner.zip or ''
        Address.CountryCode = recipient_partner.country_id.code or ''

        self.RequestedShipment.Recipient = self.factory.Party()
        self.RequestedShipment.Recipient.Contact = Contact
        self.RequestedShipment.Recipient.Address = Address
