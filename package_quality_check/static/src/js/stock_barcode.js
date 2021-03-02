odoo.define('package_quality_check.picking_quality_check_main_menu', function (require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var Dialog = require('web.Dialog');
var Session = require('web.session');

var _t = core._t;
var MainMenu = require('stock_barcode.MainMenu');


var PickingQualityCheckMainMenu = MainMenu.MainMenu.include({

    _onBarcodeScanned: function(barcode) {
        var self = this;
        if (!$.contains(document, this.el) && (!barcode.includes('OUT')) && (!barcode.includes('PICK')) &&(!barcode.includes('IN')) && (!barcode.includes('QC'))) {
            return;
        }
        Session.rpc('/stock_barcode/scan_from_main_menu', {
            barcode: barcode,
        }).then(function(result) {
            if (result.action) {
                self.do_action(result.action);
            } else if (result.warning) {
                self.do_warn(result.warning);
            }
        });
    },

});
return PickingQualityCheckMainMenu;
});

