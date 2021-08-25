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

    def shipping_charges_payment_ship_collect(self, picking, shipping_charges_payment_account):
        self.RequestedShipment.ShippingChargesPayment = self.factory.Payment()
        self.RequestedShipment.ShippingChargesPayment.PaymentType = 'THIRD_PARTY'
        Payor = self.factory.Payor()
        Payor.ResponsibleParty = self.factory.Party()
        Payor.ResponsibleParty.Contact = self.factory.Contact()
        Payor.ResponsibleParty.Contact.CompanyName = remove_accents(picking.sale_id.partner_id.name) or ''
        Payor.ResponsibleParty.Contact.PhoneNumber = picking.sale_id.partner_id.phone or ''
        Payor.ResponsibleParty.Address = self.factory.Address()
        Payor.ResponsibleParty.Address.StreetLines = [remove_accents(picking.sale_id.partner_id.street) or '',
                               remove_accents(picking.sale_id.partner_id.street2) or '']
        Payor.ResponsibleParty.Address.City = remove_accents(picking.sale_id.partner_id.city) or ''
        if picking.sale_id.partner_id.country_id.code in STATECODE_REQUIRED_COUNTRIES:
            Payor.ResponsibleParty.Address.StateOrProvinceCode = picking.sale_id.partner_id.state_id.code or ''
        else:
            Payor.ResponsibleParty.Address.StateOrProvinceCode = ''
        Payor.ResponsibleParty.Address.PostalCode = picking.sale_id.partner_id.zip or ''
        Payor.ResponsibleParty.Address.CountryCode = picking.sale_id.partner_id.country_id.code or ''
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
        
    def _add_package(self, weight_value, package_code=False, package_height=0, package_width=0, package_length=0, sequence_number=False, mode='shipping', po_number=False, dept_number=False, reference=False, **kwargs):
        package = self.factory.RequestedPackageLineItem()
        package_weight = self.factory.Weight()
        package_weight.Value = weight_value
        package_weight.Units = self.RequestedShipment.TotalWeight.Units

        package.PhysicalPackaging = 'BOX'
        if package_code == 'YOUR_PACKAGING':
            package.Dimensions = self.factory.Dimensions()
            package.Dimensions.Height = package_height
            package.Dimensions.Width = package_width
            package.Dimensions.Length = package_length
            # TODO in master, add unit in product packaging and perform unit conversion
            package.Dimensions.Units = "IN" if self.RequestedShipment.TotalWeight.Units == 'LB' else 'CM'
        if po_number:
            po_reference = self.factory.CustomerReference()
            po_reference.CustomerReferenceType = 'P_O_NUMBER'
            po_reference.Value = po_number
            package.CustomerReferences.append(po_reference)
        if dept_number:
            dept_reference = self.factory.CustomerReference()
            dept_reference.CustomerReferenceType = 'DEPARTMENT_NUMBER'
            dept_reference.Value = dept_number
            package.CustomerReferences.append(dept_reference)
        if reference:
            customer_reference = self.factory.CustomerReference()
            customer_reference.CustomerReferenceType = 'CUSTOMER_REFERENCE'
            customer_reference.Value = reference
            package.CustomerReferences.append(customer_reference)
        if kwargs.get('invoice_number', False):
            invoice_reference = self.factory.CustomerReference()
            invoice_reference.CustomerReferenceType = 'INVOICE_NUMBER'
            invoice_reference.Value = kwargs.get('invoice_number')
            package.CustomerReferences.append(invoice_reference)

        package.Weight = package_weight
        if mode == 'rating':
            package.GroupPackageCount = 1
        if sequence_number:
            package.SequenceNumber = sequence_number
        else:
            self.hasOnePackage = True

        if mode == 'rating':
            self.RequestedShipment.RequestedPackageLineItems.append(package)
        else:
            self.RequestedShipment.RequestedPackageLineItems = package
