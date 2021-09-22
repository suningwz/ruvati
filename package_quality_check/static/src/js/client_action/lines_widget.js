odoo.define('package_quality_check.picking_quality_lines_widget', function (require) {
'use strict';

var concurrency = require('web.concurrency');
var core = require('web.core');
var AbstractAction = require('web.AbstractAction');
var BarcodeParser = require('barcodes.BarcodeParser');

var ViewsWidget = require('stock_barcode.ViewsWidget');
var HeaderWidget = require('stock_barcode.HeaderWidget');
var LinesWidget = require('stock_barcode.LinesWidget');
var SettingsWidget = require('stock_barcode.SettingsWidget');
var QWeb = core.qweb;

//var core = require('web.core');
//var PickingQualityCheckClientAction = require('stock_barcode.picking_client_action');

var _t = core._t;
var Session = require('web.session');

LinesWidget.include({

    init: function (parent, page, pageIndex, nbPages) {
        this._super.apply(this, arguments);
        this.pack_done = false;
        this.current_pick_lines = parent.currentState.move_line_ids;
        var qc_pattern = /^[K]\d{7}$/
        if (parent.currentState.name.match(qc_pattern)) {
            this.qc_pick = true;
        }
    },

    _highlightValidateButtonIfNeeded: function () {
           var is_highlight =  this._super();
           var self = this;
            var lines = this.current_pick_lines;
            var all_qty_done = true;
             self.pack_done = false;

             _.each(lines, function (line) {
                if (line.qty_done != line.product_uom_qty){
                    all_qty_done = false;
                    self.pack_done = true;

                }

            });

           if (all_qty_done == true && this.pack_done == false){
        this.trigger_up('validate');

           }


           return is_highlight;

    },



    /**
     * Highlight and scroll to a specific line in the current page after removing the highlight on
     * the other lines.
     *
     * @private
     * @param {Jquery} $line
     */
    _highlightLine: function ($line, doNotClearLineHighlight) {
        var $body = this.$el.filter('.o_barcode_lines');
        if (! doNotClearLineHighlight) {
            this.clearLineHighlight();
        }
        // Highlight `$line`.
        $line.toggleClass('o_highlight', true);
        $line.parents('.o_barcode_lines').toggleClass('o_js_has_highlight', true);

        var isReservationProcessed;
        if ($line.find('.o_barcode_scanner_qty').text().indexOf('/') === -1) {
            isReservationProcessed = false;
        } else {
            isReservationProcessed = this._isReservationProcessedLine($line);
        }
        if (isReservationProcessed === 1) {
            $line.toggleClass('o_highlight_green', false);
            $line.toggleClass('o_highlight_red', true);
        } else {
            $line.toggleClass('o_highlight_green', true);
            $line.toggleClass('o_highlight_red', false);
        }

        // Scroll to `$line`.
        if ($line.length && $line.position()){
            $body.animate({
                scrollTop: $body.scrollTop() + $line.position().top - $body.height()/2 + $line.height()/2
            }, 500);
        }

    },
    
    /**
     * Render the header and the body of this widget. It is called when rendering a page for the
     * first time. Once the page is rendered, the modifications will be made by `incrementProduct`
     * and `addProduct`. When another page should be displayed, the parent will destroy the current
     * instance and create a new one. This method will also toggle the display of the control
     * button.
     *
     * @private
     * @param {Object} linesDescription: description of the current page
     * @param {Number} pageIndex: the index of the current page
     * @param {Number} nbPages: the total number of pages
     */
     _renderLines: function () {
         if (this.mode === 'done') {
             if (this.model === 'stock.picking') {
                if (this.qc_pick) {
                    this._toggleScanMessage('qc_already_done');
                }
                else {
                    this._toggleScanMessage('picking_already_done');
                 }
             } else if (this.model === 'stock.inventory') {
                 this._toggleScanMessage('inv_already_done');
             }
             return;
         } else if (this.mode === 'cancel') {
            if (this.qc_pick) {
                this._toggleScanMessage('qc_already_cancelled');
            }
            else {
                this._toggleScanMessage('picking_already_cancelled');
            }
             return;
         }

        // Render and append the page summary.
        var $header = this.$el.filter('.o_barcode_lines_header');
        var $pageSummary = $(QWeb.render('stock_barcode_summary_template', {
            locationName: this.page.location_name,
            locationDestName: this.page.location_dest_name,
            nbPages: this.nbPages,
            pageIndex: this.pageIndex + 1,
            mode: this.mode,
            model: this.model,
        }));
        $header.append($pageSummary);

        // Render and append the lines, if any.
        var $body = this.$el.filter('.o_barcode_lines');
        if (this.page.lines.length) {
            var $lines = $(QWeb.render('stock_barcode_lines_template', {
                lines: this.getProductLines(this.page.lines),
                packageLines: this.getPackageLines(this.page.lines),
                model: this.model,
                groups: this.groups,
            }));
            $body.prepend($lines);
            $lines.on('click', '.o_edit', this._onClickEditLine.bind(this));
            $lines.on('click', '.o_package_content', this._onClickTruckLine.bind(this));
        }
        // Toggle and/or enable the control buttons. At first, they're all displayed and enabled.
        var $next = this.$('.o_next_page');
        var $previous = this.$('.o_previous_page');
        var $validate = this.$('.o_validate_page');
        if (this.nbPages === 1) {
            $next.prop('disabled', true);
            $previous.prop('disabled', true);
        }
        if (this.pageIndex + 1 === this.nbPages) {
            $next.toggleClass('o_hidden');
            $next.prop('disabled', true);
        } else {
            $validate.toggleClass('o_hidden');
        }

        if (! this.page.lines.length && this.model !== 'stock.inventory') {
            $validate.prop('disabled', true);
        }

        this._handleControlButtons();

        if (this.mode === 'receipt') {
            this._toggleScanMessage('scan_products');
        } else if (['delivery', 'inventory'].indexOf(this.mode) >= 0) {
            this._toggleScanMessage('scan_src');
        } else if (this.mode === 'internal') {
            this._toggleScanMessage('scan_src');
        } else if (this.mode === 'no_multi_locations') {
            this._toggleScanMessage('scan_products');
        }

         var $summary_src = this.$('.o_barcode_summary_location_src');
         var $summary_dest = this.$('.o_barcode_summary_location_dest');

         if (this.mode === 'receipt') {
             $summary_dest.toggleClass('o_barcode_summary_location_highlight', true);
         } else if (this.mode === 'delivery' || this.mode === 'internal') {
             $summary_src.toggleClass('o_barcode_summary_location_highlight', true);
         }
     },
     
     /**
     * Displays an help message at the bottom of the widget.
     *
     * @private
     * @param {string} message
     */
    _toggleScanMessage: function (message) {
        this.$('.o_scan_message').toggleClass('o_hidden', true);
        this.$('.o_scan_message_' + message).toggleClass('o_hidden', false);
        this.$('.o_barcode_pic').toggleClass(
            'o_js_has_warning_msg',
            _.indexOf([ "picking_already_done", "picking_already_cancelled", "inv_already_done", "qc_already_done", "qc_already_cancelled"], message) > -1
        );
    },



});

});
