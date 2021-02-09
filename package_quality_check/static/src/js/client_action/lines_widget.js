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


//var core = require('web.core');
//var PickingQualityCheckClientAction = require('stock_barcode.picking_client_action');

var _t = core._t;
var Session = require('web.session'); 



var PickingQualityCheckLinesWidget = LinesWidget.include({
    
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
        if ($line.length){
            $body.animate({
                scrollTop: $body.scrollTop() + $line.position().top - $body.height()/2 + $line.height()/2
            }, 500);
        }
        
    },
    
    
});
return PickingQualityCheckLinesWidget;

});
