odoo.define('package_quality_check.picking_quality_check_client_action', function (require) {
'use strict';

var concurrency = require('web.concurrency');
var core = require('web.core');
var AbstractAction = require('web.AbstractAction');
var BarcodeParser = require('barcodes.BarcodeParser');

var ViewsWidget = require('stock_barcode.ViewsWidget');
var HeaderWidget = require('stock_barcode.HeaderWidget');
var LinesWidget = require('stock_barcode.LinesWidget');
var SettingsWidget = require('stock_barcode.SettingsWidget');


//var core = require('web.core');
//var PickingQualityCheckClientAction = require('stock_barcode.picking_client_action');

var _t = core._t;
var Session = require('web.session');

var PickingQualityCheckClientAction = require('stock_barcode.ClientAction')

var PickingQualityCheckClientAction = PickingQualityCheckClientAction.include({
//    this._super.apply(this, arguments);

    /**
     * Main method called when a quantity needs to be incremented or a lot set on a line.
     * it calls `this._findCandidateLineToIncrement` first, if nothing is found it may use
     * `this._makeNewLine`.
     *
     * @private
     * @param {Object} params information needed to find the potential candidate line
     * @param {Object} params.product
     * @param {Object} params.lot_id
     * @param {Object} params.lot_name
     * @param {Object} params.package_id
     * @param {Object} params.result_package_id
     * @param {Boolean} params.doNotClearLineHighlight don't clear the previous line highlight when
     *     highlighting a new one
     * @return {object} object wrapping the incremented line and some other informations
     */
    _incrementLines: function (params) {
        var line = this._findCandidateLineToIncrement(params);
        var isNewLine = false;
        if (line) {
            // Update the line with the processed quantity.
            if (params.product.tracking === 'none' ||
                params.lot_id ||
                params.lot_name
                ) {
                if (this.actionParams.model === 'stock.picking') {
                    line.qty_done += params.product.qty || 1;
                } else if (this.actionParams.model === 'stock.inventory') {
                    line.product_qty += params.product.qty || 1;
                }
            }
        } else {
            return {'discard': true,};  // returns if a non belonging product is scanned and thrown an error.
//            isNewLine = true;
//            // Create a line with the processed quantity.
//            if (params.product.tracking === 'none' ||
//                params.lot_id ||
//                params.lot_name
//                ) {
//                line = this._makeNewLine(params.product, params.barcode, params.product.qty || 1, params.package_id, params.result_package_id);
//            } else {
//                line = this._makeNewLine(params.product, params.barcode, 0, params.package_id, params.result_package_id);
//            }
//            this._getLines(this.currentState).push(line);
//            this.pages[this.currentPageIndex].lines.push(line);
        }
        if (this.actionParams.model === 'stock.picking') {
            if (params.lot_id) {
                line.lot_id = [params.lot_id];
            }
            if (params.lot_name) {
                line.lot_name = params.lot_name;
            }
        } else if (this.actionParams.model === 'stock.inventory') {
            if (params.lot_id) {
                line.prod_lot_id = [params.lot_id, params.lot_name];
            }
        }
        return {
            'id': line.id,
            'virtualId': line.virtual_id,
            'lineDescription': line,
            'isNewLine': isNewLine,
        };
    },
    
    /**
     * Handle what needs to be done when a product is scanned.
     *
     * @param {string} barcode scanned barcode
     * @param {Object} linesActions
     * @returns {Promise}
     */
    _step_product: function (barcode, linesActions) {
        var self = this;
        this.currentStep = 'product';
        var errorMessage;
        var allowScan = false;
        var product = this._isProduct(barcode);
        if (product) {
            if (product.tracking !== 'none') {
                this.currentStep = 'lot';
            }
            var res = this._incrementLines({'product': product, 'barcode': barcode});
            self._save().then(function () {
                self._rpc({
                    'model': self.actionParams.model,
                    'method': 'action_validate_qc',
                    'args': [[self.actionParams.pickingId]],
                })
            });
            
            // throws an error if the scanned product is not upto this picking.
            if (res.discard) {
                errorMessage = _t("You are expected to scan products belongs to this picking");
                return Promise.reject(errorMessage);
            }
            if (res.isNewLine) {
                if (this.actionParams.model === 'stock.inventory') {
                    // FIXME sle: add owner_id, prod_lot_id, owner_id, product_uom_id
                    return this._rpc({
                        model: 'product.product',
                        method: 'get_theoretical_quantity',
                        args: [
                            res.lineDescription.product_id.id,
                            res.lineDescription.location_id.id,
                        ],
                    }).then(function (theoretical_qty) {
                        res.lineDescription.theoretical_qty = theoretical_qty;
                        linesActions.push([self.linesWidget.addProduct, [res.lineDescription, self.actionParams.model]]);
                        self.scannedLines.push(res.id || res.virtualId);
                        return Promise.resolve({linesActions: linesActions});
                    });
                } else {
                    linesActions.push([this.linesWidget.addProduct, [res.lineDescription, this.actionParams.model]]);
                }
            } else {
                if (product.tracking === 'none') {
                    linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, product.qty || 1, this.actionParams.model]]);
                } else {
                    linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, 0, this.actionParams.model]]);
                }
            }
            this.scannedLines.push(res.id || res.virtualId);
            return Promise.resolve({linesActions: linesActions});
        } else {
//            var barcode_split = barcode.split('/');
//            var barcode = barcode.toLowerCase( )
//            var n = str.includes("world");
//            if (barcode_split.length > 1) {
//            if (barcode_split[1] == 'PICK' || barcode_split[1] == 'QC') {
//                allowScan = true;
//            }
            // if the scanned reference is either of PICK or QC picking, it should redirect to that picking.
            if (barcode.includes("pick") || barcode.includes("qc") || barcode.includes("PICK") || barcode.includes("QC")) {
                allowScan = true;
            }
            self.scannedLines = []
            
            var success = function (res) {
                return Promise.resolve({linesActions: res.linesActions});
            };
            var fail = function (specializedErrorMessage) {
//                self.currentStep = 'product';
                if (specializedErrorMessage){
                    return Promise.reject(specializedErrorMessage);
                }
                if (! self.scannedLines.length) {
                    // if the scanned reference is either of PICK or QC picking, throws a warning and redirects to new scanned picking by saving current page data and also invokes method to create batch qc process.
                    if (allowScan) {
                        errorMessage = _t('You have scanned a picking instead of a product, redirecting to new picking.');
                        self._save();
//                        self._rpc({
//                            'model': 'stock.picking',
//                            'method': 'action_create_batch_qc',
//                            'args': [self.actionParams.pickingId],
//                        })
                        Session.rpc('/stock_barcode/scan_from_main_menu', {
                            barcode: barcode,
                        }).then(function(result) {
                            if (result.action) {
                                self.do_action(result.action);
                            } else if (result.warning) {
                                self.do_warn(result.warning);
                            }
                        });
                    }
                    else if (self.groups.group_tracking_lot) {
                        errorMessage = _t("You are expected to scan one or more products or a package available at the picking's location");
                    } else {
                        errorMessage = _t('You are expected to scan one or more products.');
                    }
                    return Promise.reject(errorMessage);
                }

//                var destinationLocation = self.locationsByBarcode[barcode];
//                if (destinationLocation) {
//                    return self._step_destination(barcode, linesActions);
//                } else {
//                    errorMessage = _t('You are expected to scan more products or a destination location.');
//                    return Promise.reject(errorMessage);
//                }
            };
            return self._step_lot(barcode, linesActions).then(success, function () {
                return self._step_package(barcode, linesActions).then(success, fail);
            });
        }
    },
    
    


//    custom_events: _.extend({}, PickingClientAction.prototype.custom_events, {
//        'picking_check_quality_done': '_onCheckQualityDone',
//    }),

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

//    _checkQualityDone: function () {
//        var self = this;
//        this.mutex.exec(function () {
//            return self._save().then(function () {
//                return self._rpc({
//                    'model': 'stock.picking',
//                    'method': 'check_quality_done',
//                    'args': [[self.actionParams.pickingId]],
//                }).then(function(res) {
//                    var exitCallback = function () {
//                        self.trigger_up('reload');
//                    };
//                    if (_.isObject(res)) {
//                        var options = {
//                            on_close: exitCallback,
//                        };
//                        return self.do_action(res, options)
//                    } else {
//                        console.log(_.isObject(res))
//                        self.do_notify(_t("No more quality checks"), _t("All the quality checks have been done."));
//                    }
//                });
//            });
//        });
//    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

//    _onCheckQualityDone: function (ev) {
//        ev.stopPropagation();
//        this._checkQualityDone();
//    },

});
return PickingQualityCheckClientAction;

});
