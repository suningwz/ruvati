# -*- coding: utf-8 -*-

{
    "name": "Delivery Extension Ruvati",
    "version": "13.0",
    'summary': "This module is used to create Label before delivey validation, enable ship collect feature",
    "category": 'Delivery',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'website': 'http://www.confianzit.com',

    "depends": ['sale','stock','delivery','delivery_fedex','delivery_ups'],

    'data': [
            "views/stock_view.xml",
            "views/res_partner_view.xml",
            "views/sale_order_view.xml"
    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}


