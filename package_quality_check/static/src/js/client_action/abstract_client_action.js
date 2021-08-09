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

function isChildOf(locationParent, locationChild) {
    return _.str.startsWith(locationChild.parent_path, locationParent.parent_path);
}

var QualityCheckClientAction = require('stock_barcode.ClientAction');
var PickingQualityCheckClientAction = QualityCheckClientAction.include({

//events:  {
//            'click #b_submit': '_onClickSub'
//        },
//      _onClickSub : function(){
//      this._onBarcodeScanned($('#b_code').val());},


    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.is_location_scanned = false;
    },

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

     _process_pick_operation : function(params){

        var product = params.product;
        var lotId = params.lot_id;
        var lotName = params.lot_name;
        var packageId = params.package_id;
        var currentPage = this.pages[this.currentPageIndex];
        if (currentPage.lines.length ==0){
                var currentPageData = this.pages[0];
        }
        else{
            var currentPageData = this.pages[this.currentPageIndex];
        }

        var res = false;
        var loop_time = currentPageData.lines.length;
        for (var z = 0; z < loop_time; z++) {
            var lineInCurrentPage = currentPageData.lines[z];
            if (lineInCurrentPage.qty_done===1){
            continue;
            }
            if (lineInCurrentPage.product_id.id === product.id) {
                // If the line is empty, we could re-use it.
                if (
                    (this.actionParams.model === 'stock.picking' &&
                     ! lineInCurrentPage.lot_id &&
                     ! lineInCurrentPage.lot_name &&
                     ! lineInCurrentPage.package_id
                    ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     ! lineInCurrentPage.product_qty &&
                     ! lineInCurrentPage.prod_lot_id
                    )
                ) {
                    res = lineInCurrentPage;
//                    res['is_updated'] = 1;
                    if(this.currentPageIndex > 0){
                        currentPage.lines.splice(z,1);
                        res.location_id = {'id':currentPage.location_id,'display_name':currentPage.location_name};
                        currentPage.lines.push(res);
                    }
                    break;

                }

                if (product.tracking === 'serial' &&
                    ((this.actionParams.model === 'stock.picking' &&
                      lineInCurrentPage.qty_done > 0
                     ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     lineInCurrentPage.product_qty > 0
                    ))) {
                    continue;
                }
                if (lineInCurrentPage.qty_done &&
                (this.actionParams.model === 'stock.inventory' ||
                lineInCurrentPage.location_dest_id.id === currentPage.location_dest_id) &&
                this.scannedLines.indexOf(lineInCurrentPage.virtual_id || lineInCurrentPage.id) === -1 &&
                lineInCurrentPage.qty_done >= lineInCurrentPage.product_uom_qty) {
                    continue;
                }
                if (lotId &&
                    ((this.actionParams.model === 'stock.picking' &&
                     lineInCurrentPage.lot_id &&
                     lineInCurrentPage.lot_id[0] !== lotId
                     ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     lineInCurrentPage.prod_lot_id &&
                     lineInCurrentPage.prod_lot_id[0] !== lotId
                    )
                )) {
                    continue;
                }
                if (lotName &&
                    lineInCurrentPage.lot_name &&
                    lineInCurrentPage.lot_name !== lotName
                    ) {
                    continue;
                }
                if (packageId &&
                    (! lineInCurrentPage.package_id ||
                    lineInCurrentPage.package_id[0] !== packageId[0])
                    ) {
                    continue;
                }
                if(lineInCurrentPage.product_uom_qty && lineInCurrentPage.qty_done >= lineInCurrentPage.product_uom_qty) {
                    continue;
                }
                res = lineInCurrentPage;
                break;
            }
        }
        return res;
     },

     _findCandidateLineToIncrement: function (params) {
        console.log("sssssssssssssssssssssssssss")
         var picking_type_code = this.currentState.picking_type_code;
        if (this.actionParams.model === 'stock.picking' && picking_type_code ==='internal'){
            var process_result = this._process_pick_operation(params);

            return process_result
        }
        var product = params.product;
        var lotId = params.lot_id;
        var lotName = params.lot_name;
        var packageId = params.package_id;
        var currentPage = this.pages[this.currentPageIndex];
        var res = false;

        for (var z = 0; z < currentPage.lines.length; z++) {
            var lineInCurrentPage = currentPage.lines[z];
            if (lineInCurrentPage.product_id.id === product.id) {
                // If the line is empty, we could re-use it.
                if (lineInCurrentPage.virtual_id &&
                    (this.actionParams.model === 'stock.picking' &&
                     ! lineInCurrentPage.qty_done &&
                     ! lineInCurrentPage.product_uom_qty &&
                     ! lineInCurrentPage.lot_id &&
                     ! lineInCurrentPage.lot_name &&
                     ! lineInCurrentPage.package_id
                    ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     ! lineInCurrentPage.product_qty &&
                     ! lineInCurrentPage.prod_lot_id
                    )
                ) {
                    res = lineInCurrentPage;
                    break;
                }

                if (product.tracking === 'serial' &&
                    ((this.actionParams.model === 'stock.picking' &&
                      lineInCurrentPage.qty_done > 0
                     ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     lineInCurrentPage.product_qty > 0
                    ))) {
                    continue;
                }
                if (lineInCurrentPage.qty_done &&
                (this.actionParams.model === 'stock.inventory' ||
                lineInCurrentPage.location_dest_id.id === currentPage.location_dest_id) &&
                this.scannedLines.indexOf(lineInCurrentPage.virtual_id || lineInCurrentPage.id) === -1 &&
                lineInCurrentPage.qty_done >= lineInCurrentPage.product_uom_qty) {
                    continue;
                }
                if (lotId &&
                    ((this.actionParams.model === 'stock.picking' &&
                     lineInCurrentPage.lot_id &&
                     lineInCurrentPage.lot_id[0] !== lotId
                     ) ||
                    (this.actionParams.model === 'stock.inventory' &&
                     lineInCurrentPage.prod_lot_id &&
                     lineInCurrentPage.prod_lot_id[0] !== lotId
                    )
                )) {
                    continue;
                }
                if (lotName &&
                    lineInCurrentPage.lot_name &&
                    lineInCurrentPage.lot_name !== lotName
                    ) {
                    continue;
                }
                if (packageId &&
                    (! lineInCurrentPage.package_id ||
                    lineInCurrentPage.package_id[0] !== packageId[0])
                    ) {
                    continue;
                }
                if(lineInCurrentPage.product_uom_qty && lineInCurrentPage.qty_done >= lineInCurrentPage.product_uom_qty) {
                    continue;
                }
                res = lineInCurrentPage;
                break;
            }
        }
        return res;
    },

    _incrementLines: function (params) {
        var picking_type_code = this.currentState.picking_type_code;
        var line = this._findCandidateLineToIncrement(params);
        var isNewLine = false;
        if (line) {
            // Update the line with the processed quantity.
            if (params.product.tracking === 'none' ||
                params.lot_id ||
                params.lot_name
                ) {
                if (this.actionParams.model === 'stock.picking') {
                    if (picking_type_code === 'internal'){
                        line.qty_done = params.product.qty || 1;
                    }
                    else{
                        line.qty_done += params.product.qty || 1;
                    }

                } else if (this.actionParams.model === 'stock.inventory') {
                    line.product_qty += params.product.qty || 1;
                }
            }
        } else {
            if (this.actionParams.model === 'stock.picking') {
                // returns if a non belonging product is scanned and thrown an error.
//               var prod_id = false;
//               return params.product.then(function (result) {
//                     prod_id = result.id
                    if (_.filter(params.picking_product, function(pid){return pid == params.product.id}).length == 0){
                    return {'discard': true,};
                }
                else{
                return {'all_scan': true,};
                }

//               });

            }
       if (this.actionParams.model === 'stock.picking' && picking_type_code !=='internal'){
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
    _step_product: async function (barcode, linesActions) {
        var self = this;
        this.currentStep = 'product';
        var errorMessage;
        var allowScan = false;
        var product = await this._isProduct(barcode);
        if (product) {
            if (self.currentState.name.includes('PICK') && !this.is_location_scanned) {
                errorMessage = _t("You are expected to scan a source location before scanning a product");
                return Promise.reject(errorMessage);
            }
            self.is_location_scanned = false;
            
            if (product.tracking !== 'none') {
                this.currentStep = 'lot';
            }
            
            // Make an rpc to get the products belongs to current picking.
            return this._rpc({
                'model': 'stock.picking',
                'method': 'get_all_picking_products',
                'args': [self.actionParams.pickingId],
            }).then(function (result) {
            var res = self._incrementLines({'product': product, 'barcode': barcode, 'picking_product': result});
            // throws an error if the scanned product is not upto this picking.
            if (res.discard) {
                errorMessage = _t("You are expected to scan products belongs to this picking");
                return Promise.reject(errorMessage);
            }
            if (res.all_scan) {
                errorMessage = _t("You may scanned all lines");
                return Promise.reject(errorMessage);
            }
//            else {
//                self._save();
//            }
            // auto validate the QC if all the products are quality check pass.
            if (self.actionParams.model === 'stock.picking') {
                self._save().then(function () {
                    self._rpc({
                        'model': self.actionParams.model,
                        'method': 'action_validate_qc',
                        'args': [[self.actionParams.pickingId]],
                    });
                });
            }
            if (res.isNewLine) {
                if (self.actionParams.model === 'stock.inventory') {
                    // FIXME sle: add owner_id, prod_lot_id, owner_id, product_uom_id
                    return self._rpc({
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
                    linesActions.push([self.linesWidget.addProduct, [res.lineDescription, self.actionParams.model]]);
                }
            } else {
                self._save().then(function(){
                    self._reloadLineWidget(self.currentPageIndex);
                })
                
                if (product.tracking === 'none') {
                    linesActions.push([self.linesWidget.incrementProduct, [res.id || res.virtualId, product.qty || 1, self.actionParams.model]]);
                } else {
                    linesActions.push([self.linesWidget.incrementProduct, [res.id || res.virtualId, 0, self.actionParams.model]]);
                }
            }
            self.scannedLines.push(res.id || res.virtualId);
            return Promise.resolve({linesActions: linesActions});
                
            });
            
            
        } else {
            // destroy current page before redirecting to another picking if it is PICK or QC.
            var qc_pattern = /^[K]\d{7}$/;
            var pick_pattern = /^[C]\d{7}$/;
            var in_pattern = /RE\d{6}$/;
            if (barcode.match(pick_pattern) || barcode.match(qc_pattern) || barcode.includes("OUT") || barcode.match(in_pattern)) {
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
    
    /**
     * Handle what needs to be done when a source location is scanned.
     *
     * @param {string} barcode scanned barcode
     * @param {Object} linesActions
     * @returns {Promise}
     */
    _step_source: function (barcode, linesActions) {
        var self = this;
        this.currentStep = 'source';
        var errorMessage;

        /* Bypass this step in the following cases:
           - the picking is a receipt
           - the multi location group isn't active
        */
        var sourceLocation = this.locationsByBarcode[barcode];
        if (sourceLocation  && ! (this.mode === 'receipt' || this.mode === 'no_multi_locations')) {
            const locationId = this._getLocationId();
            if (locationId && !isChildOf(locationId, sourceLocation)) {
                errorMessage = _t('This location is not a child of the main location.');
                return Promise.reject(errorMessage);
            } else {
                // There's nothing to do on the state here, just mark `this.scanned_location`.
                linesActions.push([this.linesWidget.highlightLocation, [true]]);
                if (this.actionParams.model === 'stock.picking') {
                    linesActions.push([this.linesWidget.highlightDestinationLocation, [false]]);
                }
                this.scanned_location = sourceLocation;
                this.is_location_scanned = true;
                this.currentStep = 'product';
                return Promise.resolve({linesActions: linesActions});
            }
        }
        /* Implicitely set the location source in the following cases:
            - the user explicitely scans a product
            - the user explicitely scans a lot
            - the user explicitely scans a package
        */
        // We already set the scanned_location even if we're not sure the
        // following steps will succeed. They need scanned_location to work.
        this.scanned_location = {
            id: this.pages ? this.pages[this.currentPageIndex].location_id : this.currentState.location_id.id,
            display_name: this.pages ? this.pages[this.currentPageIndex].location_name : this.currentState.location_id.display_name,
        };
        linesActions.push([this.linesWidget.highlightLocation, [true]]);
        if (this.actionParams.model === 'stock.picking') {
            linesActions.push([this.linesWidget.highlightDestinationLocation, [false]]);
        }

        return this._step_product(barcode, linesActions).then(function (res) {
            return Promise.resolve({linesActions: res.linesActions});
        }, function (specializedErrorMessage) {
            delete self.scanned_location;
            self.currentStep = 'source';
            if (specializedErrorMessage){
                return Promise.reject(specializedErrorMessage);
            }
            var errorMessage = _t('You are expected to scan a source location.');
            return Promise.reject(errorMessage);
        });
    },
    
    
        /**
     * Handle what needs to be done when a destination location is scanned.
     *
     * @param {string} barcode scanned barcode
     * @param {Object} linesActions
     * @returns {Promise}
     */
    _step_destination: function (barcode, linesActions) {
        var errorMessage;

        // Bypass the step if needed.
        // allow internal transfers to scan source location.
        if (this.mode === 'internal' || this.mode === 'delivery' || this.actionParams.model === 'stock.inventory') {
            this._endBarcodeFlow();
            return this._step_source(barcode, linesActions);
        }
        var destinationLocation = this.locationsByBarcode[barcode];
        var location_change = false;
        if (! isChildOf(this.currentState.location_dest_id, destinationLocation)) {
            errorMessage = _t('This location is not a child of the main location.');
            return Promise.reject(errorMessage);
        } else {
            if (this.mode === 'no_multi_locations') {
                if (this.groups.group_tracking_lot) {
                    errorMessage = _t("You are expected to scan one or more products or a package available at the picking's location");
                } else {
                    errorMessage = _t('You are expected to scan one or more products.');
                }
                return Promise.reject(errorMessage);
            }
            
            if (! this.scannedLines.length || this.mode === 'no_multi_locations') {
                this.location_change = true;
                this.scannedLines.push(this._getLines(this.currentState)[0].id);
            }
            var self = this;
            // FIXME: remove .uniq() once the code is adapted.
            _.each(_.uniq(this.scannedLines), function (idOrVirtualId) {
                var currentStateLine = _.find(self._getLines(self.currentState), function (line) {
                    return line.virtual_id &&
                           line.virtual_id.toString() === idOrVirtualId ||
                           line.id  === idOrVirtualId;
                });
                
                if (!self.location_change && currentStateLine.qty_done - currentStateLine.product_uom_qty >= 0) {
                    // Move the line.
                    currentStateLine.location_dest_id.id = destinationLocation.id;
                    currentStateLine.location_dest_id.display_name = destinationLocation.display_name;
                } 
                else {
                    var current_state_line = _.find(self._getLines(self.currentState), function (line) {
                        return line.location_dest_id.id == destinationLocation.id;
                    });
                    if (!current_state_line) {
                        var newLine = $.extend(true, {}, currentStateLine);
                        newLine.qty_done = 0;
                        
                        newLine.location_dest_id.id = destinationLocation.id;
                        newLine.location_dest_id.display_name = destinationLocation.display_name;
                        
                        
                        newLine.product_uom_qty = 0;
                        var virtualId = self._getNewVirtualId();
                        newLine.virtual_id = virtualId;
                        delete newLine.id;
                        self._getLines(self.currentState).push(newLine);
                    }
                    
                    // Split the line.
//                    var qty = currentStateLine.qty_done;
//                    currentStateLine.qty_done -= qty;
                }
            });
            
            linesActions.push([this.linesWidget.clearLineHighlight, [undefined]]);
            linesActions.push([this.linesWidget.highlightLocation, [true]]);
            linesActions.push([this.linesWidget.highlightDestinationLocation, [true]]);
            this.scanned_location_dest = destinationLocation;
            return Promise.resolve({linesActions: linesActions});
        }
    },

});
return PickingQualityCheckClientAction;

});
