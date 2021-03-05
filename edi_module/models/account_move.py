from odoo import models, fields
import json
import requests
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    transaction_id = fields.Char("Transaction ID")

    def send_data(self, data):
        configuration = self.env['edi.configuration'].search([], limit=1)
        if not configuration:
            raise UserError("Please Configure the EDI post url")
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
        #post data
        post_url = configuration.post_url
        response = requests.post(post_url, data=json.dumps(data), headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
        self.transaction_id = response.content and json.loads(response.content)

    def _get_tracking_numbers(self):
        tracking = []
        sale_order = self.env['sale.order'].search([('name', '=', self.invoice_origin)])
        picking_ids = sale_order.picking_ids
        carrier_id = picking_ids and picking_ids[0].carrier_id
        shipping_id = picking_ids and picking_ids[0].partner_id
        for picking in picking_ids:
            tracking_ids = picking.carrier_tracking_ref and picking.carrier_tracking_ref.split(',') or []
            for track in tracking_ids:
                tracking.append({'id': track})

        return tracking, carrier_id, shipping_id

    def _get_lines(self):
        lines = []
        for line in self.invoice_line_ids:
            customer_item = line.product_id.edi_customer_ids.filtered(lambda l: l.customer_id== line.partner_id.customer_id)
            lines.append({
                'item_no': line.product_id.default_code,
                'qty_ordered': line.quantity,
                'unit_price': line.price_unit,
                'net_price': line.price_subtotal,
                'unit_of_measure': "EA",
                'customer_item_no': customer_item and customer_item.sku_product_id or '',
                'item_description_1': line.name
            })
        return lines

    def post(self):
        res = super(AccountMove, self).post()
        for move in self:
            sale_order = self.env['sale.order'].search([('name', '=', move.invoice_origin)])
            if not sale_order.edi_order:
                break
            if move.is_invoice():
                lines = move._get_lines()
                tracking_numbers, carrier_id, shipping_id = move._get_tracking_numbers()
                # path = ''
                shipment_data = {
                    "BSISerObjects.bsiinvoice": {

                        'invoice_no': move.name,
                        'customer_number': move.partner_id.customer_id,
                        'invoice_date': move.invoice_date.strftime('%Y-%m-%d'),
                        "invoice_due_date": move.invoice_date_due.strftime('%Y-%m-%d'),
                        "terms_description": move.invoice_payment_term_id.name,
                        "total_invoice_amount": move.amount_total,
                        "ship_via_description": carrier_id.name,
                        'billing_address': {
                            "name": move.partner_id.name,
                            "address_1": move.partner_id.street,
                            "address_2": move.partner_id.street2,
                            "city": move.partner_id.city,
                            "state": move.partner_id.state_id.code,
                            "zip": move.partner_id.zip,
                            "country": move.partner_id.country_id.code,

                        },
                        "ship_to_address": {
                            "name": shipping_id.name,
                            "address_1": shipping_id.street,
                            "address_2": shipping_id.street2,
                            "city": shipping_id.city,
                            "state": shipping_id.state_id.code,
                            "zip": shipping_id.zip,
                            "country": shipping_id.country_id.code,

                        },
                        "remit_to_address": {
                            "name": move.company_id.name,
                            "address_1": move.company_id.street,
                            "address_2": move.company_id.street2,
                            "city": move.company_id.city,
                            "state": move.company_id.state_id.code,
                            "zip": move.company_id.zip,
                            "country": move.company_id.country_id.code,

                        },
                        'tracking_numbers': tracking_numbers,
                        "lines": lines

                    }
                }
                move.send_data(shipment_data)
                # json.dump(shipment_data, so_file, indent=2)

        return res
