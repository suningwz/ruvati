# -*- coding: utf-8 -*-

{
    "name": "Package Quality Check",
    "version": "13.0",
    'summary': "This module is used to quality check to avoid any mispackaging of the product",
    "category": 'Delivery',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'website': 'http://www.confianzit.com',

    "depends": ['sale','stock','delivery','stock_barcode'],

    'data': [
        'views/stock_barcode_templates.xml',
    ],
    'qweb': [
#        "static/src/xml/qweb_templates.xml",
    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}


