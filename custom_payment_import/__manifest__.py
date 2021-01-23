# -*- coding: utf-8 -*-

{
    "name": "Import csv/excel",
    "version": "13.0",
    'summary': "This module is used to import csv/excel files",
    "category": 'Accounting',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'website': 'http://www.confianzit.com',

    "depends":['account','scs_rma'],

    'data': [
            "wizard/import_payment_receipt_wizard.xml",
            "views/account_journal_view.xml",
             "views/res_company_view.xml",
    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}


