# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from itertools import groupby
from odoo import api, fields, models, exceptions, _, tools
from odoo.exceptions import UserError
from odoo.tools import pdf
import io
import PIL.PdfImagePlugin   # activate PDF support in PIL
from PIL import Image
from odoo.addons.delivery_ups.models.ups_request import UPSRequest
from odoo.http import request
from zeep.exceptions import Fault
import base64

_logger = logging.getLogger(__name__)


class UPSRequestRef(UPSRequest):

    def save_label(self, image64, label_file_type='GIF'):
        img_decoded = base64.decodebytes(image64.encode('utf-8'))
        if label_file_type == 'GIF':
            # Label format is GIF, so need to rotate and convert as PDF
            image_string = io.BytesIO(img_decoded)
            im = Image.open(image_string)

            label_result = io.BytesIO()
            im.save(label_result, 'pdf', quality=95)
            return label_result.getvalue()
        else:
            image_string = io.BytesIO(img_decoded)
            im = Image.open(image_string)
            im1 = im.rotate(-90, expand=1)
            im2 = im1.crop((0,0,800,1200))
            label_result = io.BytesIO()
            im2.save(label_result, 'png',)
            return label_result.getvalue()

    def send_shipping(self, shipment_info, packages, shipper, ship_from, ship_to, packaging_type, service_type, saturday_delivery, duty_payment, cod_info=None, label_file_type='GIF', ups_carrier_account=False, **kwargs):
        client = self._set_client(self.ship_wsdl, 'Ship', 'ShipmentRequest')
        request = self.factory_ns3.RequestType()
        request.RequestOption = 'nonvalidate'

        request_type = "shipping"
        label = self.factory_ns2.LabelSpecificationType()
        label.LabelImageFormat = self.factory_ns2.LabelImageFormatType()
        label_file_type = 'PNG'
        label.LabelImageFormat.Code = label_file_type
        label.LabelImageFormat.Description = label_file_type
        if label_file_type != 'GIF':
            label.LabelStockSize = self.factory_ns2.LabelStockSizeType()
            label.LabelStockSize.Height = '6'
            label.LabelStockSize.Width = '4'

        shipment = self.factory_ns2.ShipmentType()
        shipment.Description = shipment_info.get('description')

        for package in self.set_package_detail(client, packages, packaging_type, ship_from, ship_to, cod_info, request_type, order=kwargs.get('order', False)):
            shipment.Package.append(package)

        shipment.Shipper = self.factory_ns2.ShipperType()
        # sale_order_id = kwargs.get('order', False)
        # postal_code = shipper.zip
        # if sale_order_id and sale_order_id.is_ship_collect:
        #     postal_code = sale_order_id.partner_id.zip
        shipment.Shipper.Address = self.factory_ns2.ShipAddressType()
        shipment.Shipper.AttentionName = (shipper.name or '')[:35]
        shipment.Shipper.Name = (shipper.parent_id.name or shipper.name or '')[:35]
        shipment.Shipper.Address.AddressLine = [l for l in [shipper.street or '', shipper.street2 or ''] if l]
        shipment.Shipper.Address.City = shipper.city or ''
        shipment.Shipper.Address.PostalCode = shipper.zip or ''
        shipment.Shipper.Address.CountryCode = shipper.country_id.code or ''
        if shipper.country_id.code in ('US', 'CA', 'IE'):
            shipment.Shipper.Address.StateProvinceCode = shipper.state_id.code or ''
        shipment.Shipper.ShipperNumber = self.shipper_number or ''
        shipment.Shipper.Phone = self.factory_ns2.ShipPhoneType()
        shipment.Shipper.Phone.Number = self._clean_phone_number(shipper.phone)

        shipment.ShipFrom = self.factory_ns2.ShipFromType()
        shipment.ShipFrom.Address = self.factory_ns2.ShipAddressType()
        shipment.ShipFrom.AttentionName = (ship_from.name or '')[:35]
        shipment.ShipFrom.Name = (ship_from.parent_id.name or ship_from.name or '')[:35]
        shipment.ShipFrom.Address.AddressLine = [l for l in [ship_from.street or '', ship_from.street2 or ''] if l]
        shipment.ShipFrom.Address.City = ship_from.city or ''
        shipment.ShipFrom.Address.PostalCode = ship_from.zip or ''
        shipment.ShipFrom.Address.CountryCode = ship_from.country_id.code or ''
        if ship_from.country_id.code in ('US', 'CA', 'IE'):
            shipment.ShipFrom.Address.StateProvinceCode = ship_from.state_id.code or ''
        shipment.ShipFrom.Phone = self.factory_ns2.ShipPhoneType()
        shipment.ShipFrom.Phone.Number = self._clean_phone_number(ship_from.phone)

        shipment.ShipTo = self.factory_ns2.ShipToType()
        shipment.ShipTo.Address = self.factory_ns2.ShipToAddressType()
        shipment.ShipTo.AttentionName = (ship_to.name or '')[:35]
        shipment.ShipTo.Name = (ship_to.parent_id.name or ship_to.name or '')[:35]
        shipment.ShipTo.Address.AddressLine = [l for l in [ship_to.street or '', ship_to.street2 or ''] if l]
        shipment.ShipTo.Address.City = ship_to.city or ''
        shipment.ShipTo.Address.PostalCode = ship_to.zip or ''
        shipment.ShipTo.Address.CountryCode = ship_to.country_id.code or ''
        if ship_to.country_id.code in ('US', 'CA', 'IE'):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or ''
        shipment.ShipTo.Phone = self.factory_ns2.ShipPhoneType()
        shipment.ShipTo.Phone.Number = self._clean_phone_number(shipment_info['phone'])
        if not ship_to.commercial_partner_id.is_company:
            shipment.ShipTo.Address.ResidentialAddressIndicator = None

        shipment.Service = self.factory_ns2.ServiceType()
        shipment.Service.Code = service_type or ''
        shipment.Service.Description = 'Service Code'
        if service_type == "96":
            shipment.NumOfPiecesInShipment = int(shipment_info.get('total_qty'))
        shipment.ShipmentRatingOptions = self.factory_ns2.RateInfoType()
        shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = 1

        # Shipments from US to CA or PR require extra info
        if ship_from.country_id.code == 'US' and ship_to.country_id.code in ['CA', 'PR']:
            shipment.InvoiceLineTotal = self.factory_ns2.CurrencyMonetaryType()
            shipment.InvoiceLineTotal.CurrencyCode = shipment_info.get('itl_currency_code')
            shipment.InvoiceLineTotal.MonetaryValue = shipment_info.get('ilt_monetary_value')

        # set the default method for payment using shipper account
        payment_info = self.factory_ns2.PaymentInfoType()
        shipcharge = self.factory_ns2.ShipmentChargeType()
        shipcharge.Type = '01'

        # Bill Recevier 'Bill My Account'
        if ups_carrier_account:
            shipcharge.BillReceiver = self.factory_ns2.BillReceiverType()
            shipcharge.BillReceiver.Address = self.factory_ns2.BillReceiverAddressType()
            shipcharge.BillReceiver.AccountNumber = ups_carrier_account
            shipcharge.BillReceiver.Address.PostalCode = ship_to.zip
            # shipcharge.BillThirdParty = self.factory_ns2.BillThirdPartyChargeType()
            # shipcharge.BillThirdParty.AccountNumber = '0109FX'
            # shipcharge.BillThirdParty.Address = self.factory_ns2.AccountAddressType()
            # shipcharge.BillThirdParty.Address.PostalCode = '680711'
            # shipcharge.BillThirdParty.Address.CountryCode = 'US'
        else:
            shipcharge.BillShipper = self.factory_ns2.BillShipperType()
            shipcharge.BillShipper.AccountNumber = self.shipper_number or ''

        payment_info.ShipmentCharge = [shipcharge]

        if duty_payment == 'SENDER':
            duty_charge = self.factory_ns2.ShipmentChargeType()
            duty_charge.Type = '02'
            duty_charge.BillShipper = self.factory_ns2.BillShipperType()
            duty_charge.BillShipper.AccountNumber = self.shipper_number or ''
            payment_info.ShipmentCharge.append(duty_charge)

        shipment.PaymentInformation = payment_info

        if saturday_delivery:
            shipment.ShipmentServiceOptions = self.factory_ns2.ShipmentServiceOptionsType()
            shipment.ShipmentServiceOptions.SaturdayDeliveryIndicator = saturday_delivery
        else:
            shipment.ShipmentServiceOptions = ''
        self.shipment = shipment
        self.label = label
        self.request = request
        self.label_file_type = label_file_type

    def set_package_detail(self, client, packages, packaging_type, ship_from, ship_to, cod_info, request_type, **kwargs):
        order = kwargs.get('order', False)
        Packages = []
        if request_type == "rating":
            MeasurementType = self.factory_ns2.CodeDescriptionType
        elif request_type == "shipping":
            MeasurementType = self.factory_ns2.ShipUnitOfMeasurementType
        for i, p in enumerate(packages):
            package = self.factory_ns2.PackageType()
            if hasattr(package, 'Packaging'):
                package.Packaging = self.factory_ns2.PackagingType()
                package.Packaging.Code = p.packaging_type or packaging_type or ''
            elif hasattr(package, 'PackagingType'):
                package.PackagingType = self.factory_ns2.CodeDescriptionType()
                package.PackagingType.Code = p.packaging_type or packaging_type or ''

            if p.dimension_unit and any(p.dimension.values()):
                package.Dimensions = self.factory_ns2.DimensionsType()
                package.Dimensions.UnitOfMeasurement = MeasurementType()
                package.Dimensions.UnitOfMeasurement.Code = p.dimension_unit or ''
                package.Dimensions.Length = p.dimension['length'] or ''
                package.Dimensions.Width = p.dimension['width'] or ''
                package.Dimensions.Height = p.dimension['height'] or ''

            if cod_info:
                package.PackageServiceOptions = self.factory_ns2.PackageServiceOptionsType()
                package.PackageServiceOptions.COD = self.factory_ns2.CODType()
                package.PackageServiceOptions.COD.CODFundsCode = str(cod_info['funds_code'])
                package.PackageServiceOptions.COD.CODAmount = self.factory_ns2.CODAmountType() if request_type == 'rating' else self.factory_ns2.CurrencyMonetaryType()
                package.PackageServiceOptions.COD.CODAmount.MonetaryValue = cod_info['monetary_value']
                package.PackageServiceOptions.COD.CODAmount.CurrencyCode = cod_info['currency']

            package.PackageWeight = self.factory_ns2.PackageWeightType()
            package.PackageWeight.UnitOfMeasurement = MeasurementType()
            package.PackageWeight.UnitOfMeasurement.Code = p.weight_unit or ''
            package.PackageWeight.Weight = p.weight or ''

            # Package and shipment reference text is only allowed for shipments within
            # the USA and within Puerto Rico. This is a UPS limitation.
            if (p.name and ship_from.country_id.code in ('US') and ship_to.country_id.code in ('US')):
#                 reference_number = self.factory_ns2.ReferenceNumberType()
#                 reference_number.Code = 'PM'
#                 reference_number.Value = p.name
#                 reference_number.BarCodeIndicator = p.name
# #                package.ReferenceNumber = reference_number
#                 package.ReferenceNumber.append(reference_number)

                #adding PO Number to ups label reference number
                if order:
                    if order.partner_id.is_home_depot:
                        reference_number_po = self.factory_ns2.ReferenceNumberType()
                        reference_number_po.Code = 'PO'
                        reference_number_po.Value = '8119'
                        package.ReferenceNumber.append(reference_number_po)
                    else:
                        po_number = order.display_name or False
                        reference_number_po = self.factory_ns2.ReferenceNumberType()
                        reference_number_po.Code = 'PO'
                        reference_number_po.Value = str(order.client_order_ref and order.client_order_ref or po_number)
                        package.ReferenceNumber.append(reference_number_po)
                        
                    reference_number_inv = self.factory_ns2.ReferenceNumberType()
                    reference_number_inv.Code = 'IK'
                    reference_number_inv.Value = order.display_name or False
                    package.ReferenceNumber.append(reference_number_inv)
            Packages.append(package)
        return Packages

