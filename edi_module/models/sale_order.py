from odoo import models, fields, api
import requests
import json
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_id = fields.Char("Customer ID")
    state = fields.Selection(selection_add=[('to_review', 'To Review')])
    edi_sale_id = fields.Char('Edi ID')
    edi_order = fields.Boolean("Edi Order", default=False, copy=False)
    pro_number = fields.Char("PRO Number")
    doc_date = fields.Date("Doc Date")
    doc_due_date = fields.Date("Doc Due Date")
    bill_of_lading_number = fields.Char("Bill Of Lading")
    transportation_method_code = fields.Char("Transportation Code")
    ship_via_description = fields.Selection([('UPS', 'UPS'), ('Fedex', 'Fedex')], string="Ship Via")
    # order_shipment_status = fields.Selection([('P', 'P')], string="Shipment Status")
    order_card_id = fields.Char('Order Card ID')

    def order_to_review(self):
        if all(line.price_unit == line.sale_approved_price for line in self.order_line) and self.state == 'to_review':
            self.write({'state': 'draft'})
        elif any(line.price_unit != line.sale_approved_price for line in self.order_line) and self.state == 'draft':
            self.write({'state': 'to_review'})

    # def write(self, vals):
    #     res = super(SaleOrder, self).write(vals)
    #     if self.edi_order:
    #         self.order_to_review()
    #     return res

    def process_order_data(self, order_data):
        data = order_data.get('PullSalesOrdersOutResult', {})
        if data:
            ship_to_code = data.get('CardCode', False)
            customer_po = data.get('NumAtCard', False)
            doc_date = data.get('DocDate', False)
            doc_due_date = data.get('DocDueDate', False)
            item_lines = data.get('DocumentLines', False)
            partner_id = self.env['res.partner'].search([('customer_id', '=', ship_to_code)], limit=1)
            card_name = data.get('CardName', False)
            AddressExtension = data.get('AddressExtension', False)
            ship_to_state = AddressExtension.get('ShipToState', False)
            ship_to_city = AddressExtension.get('ShipToCity', False)
            ship_to_zip = AddressExtension.get('ShipToZipCode', False)
            address = data.get('Address', False)
            state = self.env['res.country.state'].search([('code', '=ilike', ship_to_state)],limit=1)
            partner_ship_id = False

            if card_name and address and state and ship_to_city and partner_id:
                partner_ship_id = self.env['res.partner'].create({'name': card_name,
                                                                  'street': address,
                                                                  'city': ship_to_city,
                                                                  'state_id': state.id,
                                                                  'country_id':state.country_id.id,
                                                                  'zip': ship_to_zip,
                                                                  'parent_id': partner_id.id,
                                                                  'type': 'delivery'
                                                                  })
            if not partner_id:
                return False
            line_list = []
            for line in item_lines:
                name = line.get('ItemDescription', False)
                item_code = line.get('ItemCode', False)
                price = line.get('UnitPrice', False)
                quantity = line.get('Quantity', False)
                ship_date = line.get('ShipDate', False)
                unit_price = 0
                if price and quantity:
                    unit_price = float(price)
                edi_record = self.env['edi.customer'].search([('sku_product_id', '=', item_code),
                                                              ('customer_id', '=', ship_to_code)], limit=1)

                if not edi_record:
                    return False
                line_list.append((0, 0, {
                    'name': name,
                    'product_id': edi_record.product_id.id,
                    'ship_date': ship_date and datetime.strptime(ship_date, '%m/%d/%Y'),
                    'price_unit': unit_price,
                    'product_uom_qty': quantity

                }))
            carrier = self.env['delivery.carrier'].search(
                [('delivery_type', '=', 'ups'), ('ups_default_service_type', '=', '03')])

            order_id = self.env['sale.order'].create({
                'partner_id': partner_id.id,
                'partner_shipping_id': partner_ship_id and partner_ship_id.id or partner_id.id,
                'customer_id': ship_to_code,
                'doc_date': doc_date and datetime.strptime(doc_date, '%m/%d/%Y'),
                'order_card_id': self._context.get('order_card_id', ''),
                'doc_due_date': doc_due_date and datetime.strptime(doc_due_date, '%m/%d/%Y'),
                'edi_order': True,
                'client_order_ref': customer_po,
                'is_ship_collect': partner_id.is_ship_collect,
                'shipper_number': partner_id.is_ship_collect and partner_id.shipper_number or '',
                'carrier_id': partner_id.carrier_id.id or carrier.id,
                'order_line': line_list
            })
            if order_id:
                order_id.action_confirm()

            return order_id

        return False

    def _cron_pull_edi_orders(self):
        configuration = self.env['edi.configuration'].search([], limit=1)
        exchange_token_url = configuration.exchange_token_url
        uid = configuration.uid
        password = configuration.password
        auth_token = configuration.auth_token
        client_id = configuration.client_id
        response = requests.get(exchange_token_url,
                                headers={'UID': uid, 'PWORD': password,
                                         'AUTHTOKEN': auth_token,
                                         'CLIENTID': client_id})
        content = json.loads(response.content)
        access_token = content['ExchangeTokenResult']['access_token']
        # refresh = requests.get('https://restsvc1.bsiedi.com/BSIEDIREST.svc/RefreshToken',headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
        # refresh_content = json.loads(refresh.content)
        # access_token = refresh_content['RefreshTokenResult']['access_token']
        if configuration.mode == 'production':
            production_list_url = configuration.order_list_url
            order_url = configuration.order_url
            order_list_response = requests.get(production_list_url,
                                    headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
            if order_list_response.content:
                list_data = json.loads(order_list_response.content)
                order_list = list_data.get('PullSalesOrdersOutListResult', [])
                for order_id in order_list:
                    order_id_url = order_url + str(order_id)
                    if self.env['sale.order'].search([('order_card_id', '=', str(order_id))]):
                        continue
                    try:
                        order_response = requests.get(order_id_url, headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
                    except Exception as e:
                        continue
                    order_data = json.loads(order_response.content)
                    order_id = self.with_context({'order_card_id': str(order_id)}).process_order_data(order_data)
                    if order_id:
                        try:
                            delete_response = requests.delete(order_id_url, headers={"ACCESSTOKEN": access_token,
                                                                                 "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
                        except Exception as e:
                            continue



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sale_approved_price = fields.Float("Approved Price")
    ship_date = fields.Date("Ship Date")

    @api.onchange('product_id')
    def _onchange_product_id_edi(self):
        for rec in self:
            edi_customer = rec.product_id.edi_customer_ids.filtered(lambda l:l.customer_id == rec.order_id.customer_id)
            rec.sale_approved_price = edi_customer and edi_customer[0].sale_approved_price

    @api.model
    def create(self, vals):
        res = super(SaleOrderLine, self).create(vals)
        if res.order_id.edi_order:
            res.order_id.order_to_review()

        return res
