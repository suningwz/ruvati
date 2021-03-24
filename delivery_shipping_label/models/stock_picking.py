from odoo import models, _, fields, api
import base64
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import io
from odoo.exceptions import UserError, ValidationError
#from zplgrf import GRF


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    picking_type_id_code = fields.Char('Picking Type Code', related='picking_type_id.sequence_code', readonly=True)
    is_back_order = fields.Boolean(string="Back Order", compute="_compute_back_order",inverse="_inverse_back_order", store=True, copy=False, readonly=False)

    @api.depends('sale_id.is_back_order')
    def _compute_back_order(self):
        for rec in self:
            rec.is_back_order = rec.sale_id.is_back_order

    def _inverse_back_order(self):
        for rec in self:
            rec.sale_id.update({'is_back_order': rec.is_back_order})

    def action_done(self):
        for rec in self:
            if rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id:
                if not rec.has_packages:
                    rec.put_in_pack()
        return super(StockPicking, self).action_done()

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        for rec in self:
            if rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id:
                if not rec.has_packages:
                    rec.with_context({'assign': True}).put_in_pack()
        return res

    # def put_in_pack(self):
    #     self.ensure_one()
    #     if self.state not in ('done', 'cancel'):
    #         picking_move_lines = self.move_line_ids
    #         if (
    #             not self.picking_type_id.show_reserved
    #             and not self.env.context.get('barcode_view')
    #         ):
    #             picking_move_lines = self.move_line_nosuggest_ids
    #
    #         move_line_ids = picking_move_lines.filtered(lambda ml:
    #             float_compare(ml.qty_done, 0.0, precision_rounding=ml.product_uom_id.rounding) > 0
    #             and not ml.result_package_id
    #         )
    #         if not move_line_ids:
    #             move_line_ids = picking_move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, 0.0,
    #                                  precision_rounding=ml.product_uom_id.rounding) > 0 and float_compare(ml.qty_done, 0.0,
    #                                  precision_rounding=ml.product_uom_id.rounding) == 0)
    #         if move_line_ids:
    #             res = self._pre_put_in_pack_hook(move_line_ids)
    #
    #             res = self._put_in_pack(move_line_ids)
    #             return res
    #         else:
    #             raise UserError(_("Please add 'Done' qantitites to the picking to create a new pack."))

    def put_in_pack(self):
        self.ensure_one()
        if self.state not in ('done', 'cancel'):
            picking_move_lines = self.move_line_ids
            if (
                    not self.picking_type_id.show_reserved
                    and not self.env.context.get('barcode_view')
            ):
                picking_move_lines = self.move_line_nosuggest_ids

            move_line_ids = picking_move_lines.filtered(lambda ml:
                                                        float_compare(ml.qty_done, 0.0,
                                                                      precision_rounding=ml.product_uom_id.rounding) > 0
                                                        and not ml.result_package_id
                                                        )
            if not move_line_ids:
                move_line_ids = picking_move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, 0.0,
                                                                                     precision_rounding=ml.product_uom_id.rounding) > 0 and float_compare(
                    ml.qty_done, 0.0,
                    precision_rounding=ml.product_uom_id.rounding) == 0)
            if move_line_ids:
                res = self._pre_put_in_pack_hook(move_line_ids)

                res = self._put_in_pack(move_line_ids)
                return res
            else:
                if self._context.get('assign',False):
                    return {}
                raise UserError(_("Please add 'Done' qantitites to the picking to create a new pack."))

    def _put_in_pack(self, move_line_ids):
        package = False
        for pick in self:
            move_lines_to_pack = self.env['stock.move.line']
            # package = self.env['stock.quant.package'].create({})

            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            if float_is_zero(move_line_ids[0].qty_done, precision_digits=precision_digits):
                for line in move_line_ids:
                    line.qty_done = line.product_uom_qty

            for ml in move_line_ids:
                if float_compare(ml.qty_done, ml.product_uom_qty,
                                 precision_rounding=ml.product_uom_id.rounding) >= 0:
                    move_lines_to_pack |= ml
                else:
                    quantity_left_todo = float_round(
                        ml.product_uom_qty - ml.qty_done,
                        precision_rounding=ml.product_uom_id.rounding,
                        rounding_method='UP')
                    done_to_keep = ml.qty_done
                    new_move_line = ml.copy(
                        default={'product_uom_qty': 0, 'qty_done': ml.qty_done})
                    ml.write({'product_uom_qty': quantity_left_todo, 'qty_done': 0.0})
                    new_move_line.write({'product_uom_qty': done_to_keep})
                    move_lines_to_pack |= new_move_line
            for pack_line in move_lines_to_pack:
                pack_line_count = 1
                for line_range in range(int(pack_line.product_uom_qty)):
                    new_pack_line = pack_line
                    if pack_line.product_uom_qty > 1 and pack_line_count != pack_line.product_uom_qty:
                        pack_line_count += 1
                        new_pack_line = pack_line.copy(
                            default={'product_uom_qty': 0, 'qty_done': 0})
                        # pack_line.write({'product_uom_qty': 1, 'qty_done': 1})
                        new_pack_line.write({'product_uom_qty': 1})

                    package = self.env['stock.quant.package'].create({
                        'shipping_weight': pack_line.product_id.weight,
                        'height': pack_line.product_id.height,
                        'width': pack_line.product_id.width,
                        'length': pack_line.product_id.length
                    })
                    packaging_id = self.env['product.packaging'].create({
                        'name': package.name,
                        'height': pack_line.product_id.height,
                        'width': pack_line.product_id.width,
                        'length': pack_line.product_id.length
                    })
                    package.packaging_id = packaging_id.id

                    package_level = self.env['stock.package_level'].create({
                        'package_id': package.id,
                        'picking_id': pick.id,
                        'location_id': False,
                        'location_dest_id': move_line_ids.mapped('location_dest_id').id,
                        'move_line_ids': [(6, 0, new_pack_line.id)],
                        'company_id': pick.company_id.id,
                    })
                    new_pack_line.write({
                        'result_package_id': package.id,
                    })
                if pack_line.product_uom_qty >= 1:
                    pack_line.write({'product_uom_qty': 1, 'qty_done': 0})

        return package

    def generate_shipping_label(self):
        packing_slip = self.env.ref('delivery_shipping_label.action_report_packslip').render_qweb_pdf(self.id)[0]
        if self.carrier_id.delivery_type == 'fedex':
            return_label_ids = self.env['ir.attachment'].search(
                [('res_model', '=', 'stock.picking'), ('res_id', '=', self.id),
                 ('name', 'like', '%s%%' % 'LabelFedex')])
            if not return_label_ids:
                raise UserError("Shipping labels not generated")
            return_labels = [return_label_ids and base64.b64decode(return_label_ids[0].datas)]
        else:
            return_label = self.env.ref('delivery_shipping_label.action_report_labelslip').render_qweb_pdf(self.id)[0]
            return_labels = [return_label]
        packing_slips = [packing_slip]
        delivery_type = self.carrier_id.delivery_type
        merged_pdf = self.with_context(delivery_type=delivery_type).merge_pdfs(packing_slips, return_labels)
        # with open('LabelFedex.PDF', 'rb') as pdf:
        #     pages = GRF.from_pdf(pdf.read(), 'DEMO', center_of_pixel=False)
        # grf_merged = ''
        # for grf in pages:
        #     grf.optimise_barcodes()
        #     grf_merged += grf.to_zpl()
        # str.encode(grf_merged)
        attachment_id = self.env['ir.attachment'].create({
            'name': "Shipping_Label.pdf",
            'type': 'binary',
            'datas': base64.encodestring(merged_pdf),
            'res_model': self._name,
            'res_id': self.id
        })
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/web/content/%s?download=true' % attachment_id.id,
        }

    def merge_pdfs(self, packing_slips, return_labels):
        ''' Merge a collection of PDF documents in one
        :param list pdf_data: a list of PDF datastrings
        :return: a unique merged PDF datastring
        '''
        writer = PdfFileWriter()
        for document in packing_slips:
            reader_packing = PdfFileReader(io.BytesIO(document), strict=False)
            reader_label = PdfFileReader(io.BytesIO(return_labels[0]), strict=False)
            for page in range(0, reader_label.getNumPages()):
                page_rec = reader_packing.getPage(page)
                page_label = reader_label.getPage(page)
                if self._context.get('delivery_type') == 'fedex':
                    page_label.cropBox.setLowerRight((321, 120))
                    page_label.cropBox.setUpperRight((321, 610))
                    page_label.cropBox.setLowerLeft((31, 120))
                    page_label.cropBox.setUpperLeft((31, 610))
                    page_label_clockwise = page_label.rotateClockwise(270)
                else:
                    # page_label.scaleTo(6*72, 4*72)
                    page_label_clockwise = page_label
                writer.addPage(page_label_clockwise)
                writer.addPage(page_rec)

        _buffer = io.BytesIO()
        writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()
        return merged_pdf
        
    def get_order(self):
        """to get the QC picking name for the packing slip barcode
        """
        cr = self._cr
        cr.execute("select move_dest_id from stock_move_move_rel where move_orig_id = %s" % (self.move_lines[0].id))
        pick_move_ids = [x[0] for x in cr.fetchall()]
        qc_picking = self.env['stock.move'].browse(pick_move_ids)[0].picking_id
        if self.picking_type_id.warehouse_id.delivery_steps == 'pick_pack_ship' and qc_picking and qc_picking.origin == self.origin and qc_picking.picking_type_id == self.picking_type_id.warehouse_id.pack_type_id:
            return qc_picking.name
        return self.name


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'
        
    def generate_shipping_label(self):
        """Prints the Shipping label-Packing slip report for the batch.
        """
        attachments = []
        attachment_ids = []
#        picking_ids = self.picking_ids.filtered(lambda r: r.state == 'done')
#        if not picking_ids:
#            raise ValidationError("Please validate the picking to print lablel")
        for picking in self.picking_ids:
            attachments.append(picking.generate_shipping_label())
        for attachment in attachments:
            url = attachment['url'].split('?')
            pick_attachment_id = url[0].split('/')[-1]
            pick_attachment = self.env['ir.attachment'].browse(int(pick_attachment_id))
            attachment_ids.append(pick_attachment)
        merged_pdf = self.merge_packing_slip(attachment_ids)
        attachment_id = self.env['ir.attachment'].create({
            'name': "Shipping_Label.pdf",
            'type': 'binary',
            'datas': base64.encodestring(merged_pdf),
            'res_model': self._name,
            'res_id': self.id
        })
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '/web/content/%s?download=true' % attachment_id.id,
        }
        
    def merge_packing_slip(self, attachment_ids):
        """ Merges the Shipping label-Packing slip report of all pickings in the batch.
        :param attachment_ids: list of PDF datastrings to merge
        :return: a unique merged PDF datastring
        """
        writer = PdfFileWriter()
        for document in attachment_ids:
            pdf_doc = [document and base64.b64decode(document.datas)]
            reader_attachment = PdfFileReader(io.BytesIO(pdf_doc[0]), strict=False)
            for page in range(0, reader_attachment.getNumPages()):
                page_rec = reader_attachment.getPage(page)
                writer.addPage(page_rec)
        _buffer = io.BytesIO()
        writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()
        return merged_pdf

    def action_create_label(self):
        """ Creates shipping label for batch of picking
        """
        picking_ids = self.picking_ids.filtered(lambda r: r.is_create_label)
        if not picking_ids:
            raise ValidationError("Label is created for all pickings.")
        for rec in picking_ids:
            rec.action_create_label()

