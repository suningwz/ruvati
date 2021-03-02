# -*- coding: utf-8 -*-

{
    "name": "Sale Amazon Extension",
    "version": "13.0",
    "category": 'Sales',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'website': 'http://www.confianzit.com',

    "depends": ['sale','sale_amazon', 'edi_module'],

    'data': [
            'views/amazone_account_view.xml',
            'views/sale_view.xml',
            'views/partner_view.xml'
    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

