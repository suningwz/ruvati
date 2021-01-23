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

var QualityCheckClientAction = require('stock_barcode.ClientAction');

var PickingQualityCheckClientAction = QualityCheckClientAction.include({
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
            if (this.actionParams.model === 'stock.picking') {
                return {'discard': true,};  // returns if a non belonging product is scanned and thrown an error.
            }
            isNewLine = true;
            // Create a line with the processed quantity.
            if (params.product.tracking === 'none' ||
                params.lot_id ||
                params.lot_name
                ) {
                line = this._makeNewLine(params.product, params.barcode, params.product.qty || 1, params.package_id, params.result_package_id);
            } else {
                line = this._makeNewLine(params.product, params.barcode, 0, params.package_id, params.result_package_id);
            }
            this._getLines(this.currentState).push(line);
            this.pages[this.currentPageIndex].lines.push(line);
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
            // throws an error if the scanned product is not upto this picking.
            if (res.discard) {
                errorMessage = _t("You are expected to scan products belongs to this picking");
                return Promise.reject(errorMessage);
            }
            // auto validate the QC if all the products are quality check pass.
            if (this.actionParams.model === 'stock.picking') {
                self._save().then(function () {
                    self._rpc({
                        'model': self.actionParams.model,
                        'method': 'action_validate_qc',
                        'args': [[self.actionParams.pickingId]],
                    })
                });
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
            // destroy current page before redirecting to another picking if it is PICK or QC.
            if (barcode.includes("pick") || barcode.includes("qc") || barcode.includes("PICK") || barcode.includes("QC")) {
                self.destroy();
            }
            var success = function (res) {
                return Promise.resolve({linesActions: res.linesActions});
            };
            var fail = function (specializedErrorMessage) {
                self.currentStep = 'product';
                if (specializedErrorMessage){
                    return Promise.reject(specializedErrorMessage);
                }
                if (! self.scannedLines.length) {
                    if (self.groups.group_tracking_lot) {
                        errorMessage = _t("You are expected to scan one or more products or a package available at the picking's location");
                    } else {
                        errorMessage = _t('You are expected to scan one or more products.');
                    }
                    return Promise.reject(errorMessage);
                }

                var destinationLocation = self.locationsByBarcode[barcode];
                if (destinationLocation) {
                    return self._step_destination(barcode, linesActions);
                } else {
                    errorMessage = _t('You are expected to scan more products or a destination location.');
                    return Promise.reject(errorMessage);
                }
            };
            return self._step_lot(barcode, linesActions).then(success, function () {
                return self._step_package(barcode, linesActions).then(success, fail);
            });
        }
    },
    

});
return PickingQualityCheckClientAction;

});
