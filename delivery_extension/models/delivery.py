# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from itertools import groupby
from odoo import api, fields, models, exceptions, _, tools
#from .fedex_request import FedexRequest
from odoo.exceptions import UserError
from odoo.tools import pdf
from .fedex import FedexRequestShipCollect
from .ups import UPSRequestRef
from odoo.addons.delivery_ups.models.ups_request import UPSRequest, Package
from odoo.addons.delivery_fedex.models.fedex_request import FedexRequest

_logger = logging.getLogger(__name__)

FEDEX_CURR_MATCH = {
    u'UYU': u'UYP',
    u'XCD': u'ECD',
    u'MXN': u'NMP',
    u'KYD': u'CID',
    u'CHF': u'SFR',
    u'GBP': u'UKL',
    u'IDR': u'RPA',
    u'DOP': u'RDD',
    u'JPY': u'JYE',
    u'KRW': u'WON',
    u'SGD': u'SID',
    u'CLP': u'CHP',
    u'JMD': u'JAD',
    u'KWD': u'KUD',
    u'AED': u'DHS',
    u'TWD': u'NTD',
    u'ARS': u'ARN',
    u'LVL': u'EURO',
}


class Provider(models.Model):
    _inherit = 'delivery.carrier'

    def fedex_send_shipping(self, pickings):
        res = []

        for picking in pickings:
            srm = FedexRequestShipCollect(self.log_xml, request_type="shipping", prod_environment=self.prod_environment)
            superself = self.sudo()
            srm.web_authentication_detail(superself.fedex_developer_key, superself.fedex_developer_password)
            if picking.is_ship_collect:
                srm.client_detail(picking.shipper_number, superself.fedex_meter_number)
            else:
                srm.client_detail(superself.fedex_account_number, superself.fedex_meter_number)
            srm.transaction_detail(picking.id)
            package_type = picking.package_ids and picking.package_ids[0].packaging_id.shipper_package_code or self.fedex_default_packaging_id.shipper_package_code
            srm.shipment_request(self.fedex_droppoff_type, self.fedex_service_type, package_type, self.fedex_weight_unit, self.fedex_saturday_delivery)
            srm.set_currency(_convert_curr_iso_fdx(picking.company_id.currency_id.name))
            srm.set_shipper(picking.company_id.partner_id, picking.picking_type_id.warehouse_id.partner_id)
            srm.set_recipient(picking.partner_id)
            
            # using customer's shipper number for UPS integration'
            if picking.is_ship_collect:
                srm.shipping_charges_payment_ship_collect(picking.shipper_number)
            else:
                srm.shipping_charges_payment(superself.fedex_account_number)

            srm.shipment_label('COMMON2D', self.fedex_label_file_type, self.fedex_label_stock_type, 'TOP_EDGE_OF_TEXT_FIRST', 'SHIPPING_LABEL_FIRST')
            order = picking.sale_id
            company = order.company_id or picking.company_id or self.env.company
            order_currency = picking.sale_id.currency_id or picking.company_id.currency_id

            net_weight = self._fedex_convert_weight(picking.shipping_weight, self.fedex_weight_unit)

            # Commodities for customs declaration (international shipping)
            if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or (picking.partner_id.country_id.code == 'IN' and picking.picking_type_id.warehouse_id.partner_id.country_id.code == 'IN'):

                commodity_currency = order_currency
                total_commodities_amount = 0.0
                commodity_country_of_manufacture = picking.picking_type_id.warehouse_id.partner_id.country_id.code

                for operation in picking.move_line_ids:
                    commodity_amount = operation.move_id.sale_line_id.price_reduce_taxinc or operation.product_id.list_price
                    total_commodities_amount += (commodity_amount * operation.qty_done)
                    commodity_description = operation.product_id.name
                    commodity_number_of_piece = '1'
                    commodity_weight_units = self.fedex_weight_unit
                    commodity_weight_value = self._fedex_convert_weight(operation.product_id.weight * operation.qty_done, self.fedex_weight_unit)
                    commodity_quantity = operation.qty_done
                    commodity_quantity_units = 'EA'
                    commodity_harmonized_code = operation.product_id.hs_code or ''
                    srm.commodities(_convert_curr_iso_fdx(commodity_currency.name), commodity_amount, commodity_number_of_piece, commodity_weight_units, commodity_weight_value, commodity_description, commodity_country_of_manufacture, commodity_quantity, commodity_quantity_units, commodity_harmonized_code)
                srm.customs_value(_convert_curr_iso_fdx(commodity_currency.name), total_commodities_amount, "NON_DOCUMENTS")
                if picking.is_ship_collect:
                    srm.duties_payment(picking.picking_type_id.warehouse_id.partner_id, picking.shipper_number, 'RECIPIENT')
                else:
                    srm.duties_payment(picking.picking_type_id.warehouse_id.partner_id, superself.fedex_account_number, superself.fedex_duty_payment)
                send_etd = superself.env['ir.config_parameter'].get_param("delivery_fedex.send_etd")
                srm.commercial_invoice(self.fedex_document_stock_type, send_etd)

            package_count = len(picking.package_ids) or 1

            # For india picking courier is not accepted without this details in label.
            po_number = order.display_name or False
            dept_number = False
            if picking.partner_id.country_id.code == 'IN' and picking.picking_type_id.warehouse_id.partner_id.country_id.code == 'IN':
                po_number = 'B2B' if picking.partner_id.commercial_partner_id.is_company else 'B2C'
                dept_number = 'BILL D/T: SENDER'

            # TODO RIM master: factorize the following crap

            ################
            # Multipackage #
            ################
            if package_count > 1:

                # Note: Fedex has a complex multi-piece shipping interface
                # - Each package has to be sent in a separate request
                # - First package is called "master" package and holds shipping-
                #   related information, including addresses, customs...
                # - Last package responses contains shipping price and code
                # - If a problem happens with a package, every previous package
                #   of the shipping has to be cancelled separately
                # (Why doing it in a simple way when the complex way exists??)

                master_tracking_id = False
                package_labels = []
                carrier_tracking_ref = ""

                for sequence, package in enumerate(picking.package_ids, start=1):

                    package_weight = self._fedex_convert_weight(package.shipping_weight, self.fedex_weight_unit)
                    packaging = package.packaging_id
                    
                    if order.partner_id.is_home_depot:
                        srm._add_package(
                        package_weight,
                        package_code=packaging.shipper_package_code,
                        package_height=packaging.height,
                        package_width=packaging.width,
                        package_length=packaging.length,
                        sequence_number=sequence,
                        po_number='8119',
                        dept_number=dept_number,
                        reference=picking.display_name,
                    )
                    else:
                        srm._add_package(
                            package_weight,
                            package_code=packaging.shipper_package_code,
                            package_height=packaging.height,
                            package_width=packaging.width,
                            package_length=packaging.length,
                            sequence_number=sequence,
                            po_number=order.client_order_ref and order.client_order_ref or po_number,
                            dept_number=dept_number,
                            reference=picking.display_name,
                        )
                    srm.set_master_package(net_weight, package_count, master_tracking_id=master_tracking_id)
                    request = srm.process_shipment()
                    package_name = package.name or sequence

                    warnings = request.get('warnings_message')
                    if warnings:
                        _logger.info(warnings)

                    # First package
                    if sequence == 1:
                        if not request.get('errors_message'):
                            master_tracking_id = request['master_tracking_id']
                            package_labels.append((package_name, srm.get_label()))
                            package.carrier_tracking_ref = request['tracking_number']
                            carrier_tracking_ref = request['tracking_number']
                        else:
                            raise UserError(request['errors_message'])

                    # Intermediary packages
                    elif sequence > 1 and sequence < package_count:
                        if not request.get('errors_message'):
                            package_labels.append((package_name, srm.get_label()))
                            package.carrier_tracking_ref = request['tracking_number']
                            carrier_tracking_ref = carrier_tracking_ref + "," + request['tracking_number']
                        else:
                            raise UserError(request['errors_message'])

                    # Last package
                    elif sequence == package_count:
                        # recuperer le label pdf
                        if not request.get('errors_message'):
                            package_labels.append((package_name, srm.get_label()))

                            carrier_price = self._get_request_price(request['price'], order, order_currency)
                            package.carrier_tracking_ref = request['tracking_number']
                            carrier_tracking_ref = carrier_tracking_ref + "," + request['tracking_number']

                            logmessage = _("Shipment created into Fedex<br/>"
                                           "<b>Tracking Numbers:</b> %s<br/>"
                                           "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join([pl[0] for pl in package_labels]))
                            if self.fedex_label_file_type != 'PDF':
                                attachments = [('LabelFedex-%s.%s' % (pl[0], self.fedex_label_file_type), pl[1]) for pl in package_labels]
                            if self.fedex_label_file_type == 'PDF':
                                attachments = [('LabelFedex.pdf', pdf.merge_pdf([pl[1] for pl in package_labels]))]
                            picking.message_post(body=logmessage, attachments=attachments)
                            shipping_data = {'exact_price': carrier_price,
                                             'tracking_number': carrier_tracking_ref and carrier_tracking_ref.split(',')[0] or carrier_tracking_ref}
                            res = res + [shipping_data]
                        else:
                            raise UserError(request['errors_message'])

            # TODO RIM handle if a package is not accepted (others should be deleted)

            ###############
            # One package #
            ###############
            elif package_count == 1:
                packaging = picking.package_ids[:1].packaging_id or picking.carrier_id.fedex_default_packaging_id
                if order.partner_id.is_home_depot:
                    srm._add_package(
                        net_weight,
                        package_code=packaging.shipper_package_code,
                        package_height=packaging.height,
                        package_width=packaging.width,
                        package_length=packaging.length,
                        po_number='8119',
                        dept_number=dept_number,
                        reference=picking.display_name,
                    )
                else:
                    srm._add_package(
                        net_weight,
                        package_code=packaging.shipper_package_code,
                        package_height=packaging.height,
                        package_width=packaging.width,
                        package_length=packaging.length,
                        po_number=order.client_order_ref and order.client_order_ref or po_number,
                        dept_number=dept_number,
                        reference=picking.display_name,
                    )
                srm.set_master_package(net_weight, 1)

                # Ask the shipping to fedex
                request = srm.process_shipment()
                warnings = request.get('warnings_message')
                if warnings:
                    _logger.info(warnings)

                if not request.get('errors_message'):

                    if _convert_curr_iso_fdx(order_currency.name) in request['price']:
                        carrier_price = request['price'][_convert_curr_iso_fdx(order_currency.name)]
                    else:
                        _logger.info("Preferred currency has not been found in FedEx response")
                        company_currency = picking.company_id.currency_id
                        if _convert_curr_iso_fdx(company_currency.name) in request['price']:
                            amount = request['price'][_convert_curr_iso_fdx(company_currency.name)]
                            carrier_price = company_currency._convert(
                                amount, order_currency, company, order.date_order or fields.Date.today())
                        else:
                            amount = request['price']['USD']
                            carrier_price = company_currency._convert(
                                amount, order_currency, company, order.date_order or fields.Date.today())
                    picking.package_ids[:1].carrier_tracking_ref = request['tracking_number']
                    carrier_tracking_ref = request['tracking_number']
                    logmessage = (_("Shipment created into Fedex <br/> <b>Tracking Number : </b>%s") % (carrier_tracking_ref))

                    fedex_labels = [('LabelFedex-%s-%s.%s' % (carrier_tracking_ref, index, self.fedex_label_file_type), label)
                                    for index, label in enumerate(srm._get_labels(self.fedex_label_file_type))]
                    picking.message_post(body=logmessage, attachments=fedex_labels)
                    shipping_data = {'exact_price': carrier_price,
                                     'tracking_number': carrier_tracking_ref and carrier_tracking_ref.split(',')[0] or carrier_tracking_ref}
                    res = res + [shipping_data]
                else:
                    raise UserError(request['errors_message'])

            ##############
            # No package #
            ##############
            else:
                raise UserError(_('No packages for this picking'))
            if self.return_label_on_delivery:
                self.get_return_label(picking, tracking_number=request['tracking_number'], origin_date=request['date'])
            commercial_invoice = srm.get_document()
            if commercial_invoice:
                fedex_documents = [('DocumentFedex.pdf', commercial_invoice)]
                picking.message_post(body='Fedex Documents', attachments=fedex_documents)
        return res

    def fedex_rate_shipment(self, order):
        max_weight = self._fedex_convert_weight(self.fedex_default_packaging_id.max_weight, self.fedex_weight_unit)
        price = 0.0
        is_india = order.partner_shipping_id.country_id.code == 'IN' and order.company_id.partner_id.country_id.code == 'IN'

        # Estimate weight of the sales order; will be definitely recomputed on the picking field "weight"
        est_weight_value = sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line if
                                not line.display_type]) or 0.0
        weight_value = self._fedex_convert_weight(est_weight_value, self.fedex_weight_unit)

        # Some users may want to ship very lightweight items; in order to give them a rating, we round the
        # converted weight of the shipping to the smallest value accepted by FedEx: 0.01 kg or lb.
        # (in the case where the weight is actually 0.0 because weights are not set, don't do this)
        if weight_value > 0.0:
            weight_value = max(weight_value, 0.01)

        order_currency = order.currency_id
        superself = self.sudo()

        # Authentication stuff
        srm = FedexRequest(self.log_xml, request_type="rating", prod_environment=self.prod_environment)
        srm.web_authentication_detail(superself.fedex_developer_key, superself.fedex_developer_password)
        srm.client_detail(superself.fedex_account_number, superself.fedex_meter_number)

        # Build basic rating request and set addresses
        srm.transaction_detail(order.name)
        srm.shipment_request(
            self.fedex_droppoff_type,
            self.fedex_service_type,
            self.fedex_default_packaging_id.shipper_package_code,
            self.fedex_weight_unit,
            self.fedex_saturday_delivery,
        )
        pkg = self.fedex_default_packaging_id

        srm.set_currency(_convert_curr_iso_fdx(order_currency.name))
        srm.set_shipper(order.company_id.partner_id, order.warehouse_id.partner_id)
        srm.set_recipient(order.partner_shipping_id)

        # if max_weight and weight_value > max_weight:
        #     total_package = int(weight_value / max_weight)
        #     last_package_weight = weight_value % max_weight
        count= 0
        for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type):
            for sequence in range(1, int(line.product_uom_qty) + 1):
                count+=1
                srm.add_package(
                    line.product_id.weight,
                    package_code=line.product_id.default_code,
                    package_height=line.product_id.height,
                    package_width=line.product_id.width,
                    package_length=line.product_id.length,
                    sequence_number=sequence,
                    mode='rating',
                )

        srm.set_master_package(weight_value, count)
        # Commodities for customs declaration (international shipping)
        if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or is_india:
            total_commodities_amount = 0.0
            commodity_country_of_manufacture = order.warehouse_id.partner_id.country_id.code

            for line in order.order_line.filtered(
                    lambda l: l.product_id.type in ['product', 'consu'] and not l.display_type):
                commodity_amount = line.price_reduce_taxinc
                total_commodities_amount += (commodity_amount * line.product_uom_qty)
                commodity_description = line.product_id.name
                commodity_number_of_piece = '1'
                commodity_weight_units = self.fedex_weight_unit
                commodity_weight_value = self._fedex_convert_weight(line.product_id.weight * line.product_uom_qty,
                                                                    self.fedex_weight_unit)
                commodity_quantity = line.product_uom_qty
                commodity_quantity_units = 'EA'
                commodity_harmonized_code = line.product_id.hs_code or ''
                srm.commodities(_convert_curr_iso_fdx(order_currency.name), commodity_amount, commodity_number_of_piece,
                                commodity_weight_units, commodity_weight_value, commodity_description,
                                commodity_country_of_manufacture, commodity_quantity, commodity_quantity_units,
                                commodity_harmonized_code)
            srm.customs_value(_convert_curr_iso_fdx(order_currency.name), total_commodities_amount, "NON_DOCUMENTS")
            srm.duties_payment(order.warehouse_id.partner_id, superself.fedex_account_number,
                               superself.fedex_duty_payment)

        request = srm.rate()

        warnings = request.get('warnings_message')
        if warnings:
            _logger.info(warnings)

        if not request.get('errors_message'):
            price = self._get_request_price(request['price'], order, order_currency)
        else:
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error:\n%s') % request['errors_message'],
                    'warning_message': False}

        if order.is_ship_collect:
            price = 0.0
        return {'success': True,
                'price': price,
                'error_message': False,
                'warning_message': _('Warning:\n%s') % warnings if warnings else False}

        return res


#    def fedex_get_return_label(self, picking, tracking_number=None, origin_date=None):
#        srm = FedexRequest(self.log_xml, request_type="shipping", prod_environment=self.prod_environment)
#        superself = self.sudo()
#        srm.web_authentication_detail(superself.fedex_developer_key, superself.fedex_developer_password)
#        srm.client_detail(superself.fedex_account_number, superself.fedex_meter_number)

#        srm.transaction_detail(picking.id)

#        package_type = picking.package_ids and picking.package_ids[0].packaging_id.shipper_package_code or self.fedex_default_packaging_id.shipper_package_code
#        srm.shipment_request(self.fedex_droppoff_type, self.fedex_service_type, package_type, self.fedex_weight_unit, self.fedex_saturday_delivery)
#        srm.set_currency(_convert_curr_iso_fdx(picking.company_id.currency_id.name))
#        srm.set_shipper(picking.partner_id, picking.partner_id)
#        srm.set_recipient(picking.company_id.partner_id)

#        if picking.partner_id.is_ship_collect:
#            srm.shipping_charges_payment_ship_collect(picking.shipper_number)
#        else:
#            srm.shipping_charges_payment(superself.fedex_account_number)

#        srm.shipment_label('COMMON2D', self.fedex_label_file_type, self.fedex_label_stock_type, 'TOP_EDGE_OF_TEXT_FIRST', 'SHIPPING_LABEL_FIRST')
#        estimated_weight = sum([move.product_qty * move.product_id.weight for move in picking.move_lines])
#        net_weight = self._fedex_convert_weight(picking.shipping_weight, self.fedex_weight_unit) or self._fedex_convert_weight(picking.weight, self.fedex_weight_unit)
#        packaging = packaging = picking.package_ids[:1].packaging_id or picking.carrier_id.fedex_default_packaging_id
#        order = picking.sale_id
#        po_number = order.display_name or False
#        dept_number = False
#        srm._add_package(
#            net_weight,
#            package_code=packaging.shipper_package_code,
#            package_height=packaging.height,
#            package_width=packaging.width,
#            package_length=packaging.length,
#            reference=picking.display_name,
#            po_number=po_number,
#            dept_number=dept_number,
#        )
#        srm.set_master_package(net_weight, 1)
#        if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or (picking.partner_id.country_id.code == 'IN' and picking.picking_type_id.warehouse_id.partner_id.country_id.code == 'IN'):

#            order_currency = picking.sale_id.currency_id or picking.company_id.currency_id
#            commodity_currency = order_currency
#            total_commodities_amount = 0.0
#            commodity_country_of_manufacture = picking.picking_type_id.warehouse_id.partner_id.country_id.code

#            for operation in picking.move_line_ids:
#                commodity_amount = operation.move_id.sale_line_id.price_unit or operation.product_id.list_price
#                total_commodities_amount += (commodity_amount * operation.qty_done)
#                commodity_description = operation.product_id.name
#                commodity_number_of_piece = '1'
#                commodity_weight_units = self.fedex_weight_unit
#                if operation.state == 'done':
#                    commodity_weight_value = self._fedex_convert_weight(operation.product_id.weight * operation.qty_done, self.fedex_weight_unit)
#                    commodity_quantity = operation.qty_done
#                else:
#                    commodity_weight_value = self._fedex_convert_weight(operation.product_id.weight * operation.product_uom_qty, self.fedex_weight_unit)
#                    commodity_quantity = operation.product_uom_qty
#                commodity_quantity_units = 'EA'
#                commodity_harmonized_code = operation.product_id.hs_code or ''
#                srm.commodities(_convert_curr_iso_fdx(commodity_currency.name), commodity_amount, commodity_number_of_piece, commodity_weight_units, commodity_weight_value, commodity_description, commodity_country_of_manufacture, commodity_quantity, commodity_quantity_units, commodity_harmonized_code)
#            srm.customs_value(_convert_curr_iso_fdx(commodity_currency.name), total_commodities_amount, "NON_DOCUMENTS")
#            # We consider that returns are always paid by the company creating the label
#            srm.duties_payment(picking.picking_type_id.warehouse_id.partner_id, superself.fedex_account_number, 'SENDER')
#        srm.return_label(tracking_number, origin_date)
#        response = srm.process_shipment()
#        if not response.get('errors_message'):
#            fedex_labels = [('%s-%s-%s.%s' % (self.get_return_label_prefix(), response['tracking_number'], index, self.fedex_label_file_type), label)
#                            for index, label in enumerate(srm._get_labels(self.fedex_label_file_type))]
#            picking.message_post(body='Return Label', attachments=fedex_labels)
#        else:
#            raise UserError(response['errors_message'])

    def ups_send_shipping(self, pickings):
        res = []
        superself = self.sudo()
        
        ResCurrency = self.env['res.currency']
        for picking in pickings:
            if picking.is_ship_collect:
                srm = UPSRequestRef(self.log_xml, superself.ups_username, superself.ups_passwd, picking.shipper_number, superself.ups_access_number, self.prod_environment)
            else:
                srm = UPSRequestRef(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
            packages = []
            package_names = []
            if picking.package_ids:
                # Create all packages
                for package in picking.package_ids:
                    packages.append(Package(self, package.shipping_weight, quant_pack=package.packaging_id, name=package.name))
                    package_names.append(package.name)
            # Create one package with the rest (the content that is not in a package)
            if picking.weight_bulk:
                packages.append(Package(self, picking.weight_bulk))

            invoice_line_total = 0
            for move in picking.move_lines:
                invoice_line_total += picking.company_id.currency_id.round(move.product_id.lst_price * move.product_qty)

            shipment_info = {
                'description': picking.origin,
                'total_qty': sum(sml.qty_done for sml in picking.move_line_ids),
                'ilt_monetary_value': '%d' % invoice_line_total,
                'itl_currency_code': self.env.company.currency_id.name,
                'phone': picking.partner_id.mobile or picking.partner_id.phone or picking.sale_id.partner_id.mobile or picking.sale_id.partner_id.phone,
            }
            if picking.sale_id and picking.sale_id.carrier_id != picking.carrier_id:
                ups_service_type = picking.carrier_id.ups_default_service_type or picking.ups_service_type or self.ups_default_service_type
            else:
                ups_service_type = picking.ups_service_type or self.ups_default_service_type
            ups_carrier_account = picking.ups_carrier_account

            if picking.carrier_id.ups_cod:
                cod_info = {
                    'currency': picking.partner_id.country_id.currency_id.name,
                    'monetary_value': picking.sale_id.amount_total,
                    'funds_code': self.ups_cod_funds_code,
                }
            else:
                cod_info = None

            check_value = srm.check_required_value(picking.company_id.partner_id, picking.picking_type_id.warehouse_id.partner_id, picking.partner_id, picking=picking)
            if check_value:
                raise UserError(check_value)

            package_type = picking.package_ids and picking.package_ids[0].packaging_id.shipper_package_code or self.ups_default_packaging_id.shipper_package_code

            # using customer's shipper number for UPS integration'
            if picking.is_ship_collect:
                srm.send_shipping(
                shipment_info=shipment_info, packages=packages, shipper=picking.company_id.partner_id, ship_from=picking.picking_type_id.warehouse_id.partner_id,
                ship_to=picking.partner_id, packaging_type=package_type, service_type=ups_service_type, duty_payment='RECIPIENT',
                label_file_type=self.ups_label_file_type, ups_carrier_account=picking.shipper_number, saturday_delivery=picking.carrier_id.ups_saturday_delivery,
                cod_info=cod_info, order=picking.sale_id)
            else:
                srm.send_shipping(
                    shipment_info=shipment_info, packages=packages, shipper=picking.company_id.partner_id, ship_from=picking.picking_type_id.warehouse_id.partner_id,
                    ship_to=picking.partner_id, packaging_type=package_type, service_type=ups_service_type, duty_payment=picking.carrier_id.ups_duty_payment,
                    label_file_type=self.ups_label_file_type, ups_carrier_account=ups_carrier_account, saturday_delivery=picking.carrier_id.ups_saturday_delivery,
                    cod_info=cod_info, order=picking.sale_id)
            result = srm.process_shipment()
            if result.get('error_message'):
                raise UserError(result['error_message'].__str__())

            order = picking.sale_id
            company = order.company_id or picking.company_id or self.env.company
            currency_order = picking.sale_id.currency_id
            if not currency_order:
                currency_order = picking.company_id.currency_id

            if currency_order.name == result['currency_code']:
                price = float(result['price'])
            else:
                quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
                price = quote_currency._convert(
                    float(result['price']), currency_order, company, order.date_order or fields.Date.today())
            
            package_labels = []
            for track_number, label_binary_data in result.get('label_binary_data').items():
                package_labels = package_labels + [(track_number, label_binary_data)]
            
            carrier_tracking_ref = "+".join([pl[0] for pl in package_labels])
            #writing tracking reference to respective packages
            for index, package in enumerate(picking.package_ids):
                package.carrier_tracking_ref = carrier_tracking_ref.split('+')[index]
            
            logmessage = _("Shipment created into UPS<br/>"
                           "<b>Tracking Numbers:</b> %s<br/>"
                           "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join(package_names))
            if self.ups_label_file_type != 'GIF':
                attachments = [('LabelUPS-%s.%s' % (pl[0], self.ups_label_file_type), pl[1]) for pl in package_labels]
            if self.ups_label_file_type == 'GIF':
                attachments = [('LabelUPS.pdf', pdf.merge_pdf([pl[1] for pl in package_labels]))]
            picking.message_post(body=logmessage, attachments=attachments)
            shipping_data = {
                'exact_price': price,
                'tracking_number': carrier_tracking_ref and carrier_tracking_ref.split('+')[0] or carrier_tracking_ref}
            res = res + [shipping_data]
            if self.return_label_on_delivery:
                self.ups_get_return_label(picking)
        return res
        
#    def ups_rate_shipment(self, order):
#        res = super(Provider, self).ups_rate_shipment(order)
#        if order.is_ship_collect:
#            res.update({'price': 0.0})
#        return res

    def ups_rate_shipment(self, order):
        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
        ResCurrency = self.env['res.currency']
        max_weight = self.ups_default_packaging_id.max_weight
        packages = []
        total_qty = 0
        total_weight = 0
        for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type):
            total_qty += line.product_uom_qty
            total_weight += line.product_id.weight * line.product_qty

#        if max_weight and total_weight > max_weight:
#            total_package = int(total_weight / max_weight)
#            last_package_weight = total_weight % max_weight

#            for seq in range(total_package):
#                packages.append(Package(self, max_weight, quant_pack=package.packaging_id))
#            if last_package_weight:
#                packages.append(Package(self, last_package_weight))
#        else:
#            packages.append(Package(self, total_weight))
        count= 0
        for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type):
            for sequence in range(1, int(line.product_uom_qty) + 1):
                count+=1
                pack = Package(self, line.product_id.weight)
                pack.dimension.update({'length': line.product_id.length, 'width': line.product_id.width, 'height': line.product_id.height})
                packages.append(pack)
        shipment_info = {
            'total_qty': total_qty  # required when service type = 'UPS Worldwide Express Freight'
        }

        if self.ups_cod:
            cod_info = {
                'currency': order.partner_id.country_id.currency_id.name,
                'monetary_value': order.amount_total,
                'funds_code': self.ups_cod_funds_code,
            }
        else:
            cod_info = None

        check_value = srm.check_required_value(order.company_id.partner_id, order.warehouse_id.partner_id, order.partner_shipping_id, order=order)
        if check_value:
            return {'success': False,
                    'price': 0.0,
                    'error_message': check_value,
                    'warning_message': False}
        ups_service_type = order.ups_service_type or self.ups_default_service_type
        result = srm.get_shipping_price(
            shipment_info=shipment_info, packages=packages, shipper=order.company_id.partner_id, ship_from=order.warehouse_id.partner_id,
            ship_to=order.partner_shipping_id, packaging_type=self.ups_default_packaging_id.shipper_package_code, service_type=ups_service_type,
            saturday_delivery=self.ups_saturday_delivery, cod_info=cod_info)
        if result.get('error_message'):
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error:\n%s') % result['error_message'],
                    'warning_message': False}

        if order.currency_id.name == result['currency_code']:
            price = float(result['price'])
        else:
            quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
            price = quote_currency._convert(
                float(result['price']), order.currency_id, order.company_id, order.date_order or fields.Date.today())

        if self.ups_bill_my_account and order.ups_carrier_account:
            # Don't show delivery amount, if ups bill my account option is true
            price = 0.0
        
        if order.is_ship_collect:
            price = 0.0
        return {'success': True,
                'price': price,
                'error_message': False,
                'warning_message': False}

Provider()

def _convert_curr_iso_fdx(code):
    return FEDEX_CURR_MATCH.get(code, code)
    

