#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, 2008, 2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import subprocess
import shutil

import mwlib.ext
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.platypus.tables import Table

from mwlib.rl import pdfstyles
from mwlib.rl import fontconfig


class TocRenderer(object):

    def __init__(self):
        font_switcher = fontconfig.RLFontSwitcher()
        font_switcher.font_paths = fontconfig.font_paths
        font_switcher.registerDefaultFont(pdfstyles.default_font)
        font_switcher.registerFontDefinitionList(fontconfig.fonts)
        font_switcher.registerReportlabFonts(fontconfig.fonts)

        
    def build(self, pdfpath, toc_entries, has_title_page=False, rtl=False):
        outpath = os.path.dirname(pdfpath)
        tocpath = os.path.join(outpath, 'toc.pdf')
        finalpath = os.path.join(outpath, 'final.pdf')
        self.renderToc(tocpath, toc_entries, rtl=rtl)
        return self.combinePdfs(pdfpath, tocpath, finalpath, has_title_page)

    def _getColWidths(self):
        p = Paragraph('<b>%d</b>' % 9999, pdfstyles.text_style(mode='toc_article', text_align='right'))        
        w, h = p.wrap(0, pdfstyles.print_height)
        # subtracting 30pt below is *probably* necessary b/c of the table margins
        return [pdfstyles.print_width - w - 30, w]
    
    def renderToc(self, tocpath, toc_entries, rtl):
        doc = SimpleDocTemplate(tocpath, pagesize=(pdfstyles.page_width, pdfstyles.page_height))
        elements = []
        elements.append(Paragraph(_('Contents'), pdfstyles.heading_style(mode='chapter', text_align='left' if not rtl else 'right')))
        toc_table =[]
        styles = []
        col_widths = self._getColWidths()
        for row_idx, (lvl, txt, page_num) in enumerate(toc_entries):
            if lvl == 'article':
                page_num = str(page_num)
            elif lvl == 'chapter':
                page_num = '<b>%d</b>' % page_num
                styles.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 10))
            elif lvl == 'group':
                page_num = ' '
                styles.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 10))

            toc_table.append([
                Paragraph(txt, pdfstyles.text_style(mode='toc_%s' % str(lvl), text_align='left')),
                Paragraph(page_num, pdfstyles.text_style(mode='toc_article', text_align='right'))
                ])
        t = Table(toc_table, colWidths=col_widths)
        t.setStyle(styles)
        elements.append(t)
        doc.build(elements)

    def combinePdfs(self, pdfpath, tocpath, finalpath, has_title_page):

        cmd =  ['pdftk',
                'A=%s' % pdfpath,
                'B=%s' % tocpath,
                ]        
        if not has_title_page:
            cmd.extend(['cat', 'B', 'A'])
        else:
            cmd.extend(['cat', 'A1', 'B', 'A2-end'])
        cmd.extend(['output','%s' % finalpath])

        try:
            retcode = subprocess.call(cmd)
        except OSError:
            retcode = 1
        if retcode == 0:
            shutil.move(finalpath, pdfpath)
        if os.path.exists(tocpath):
            os.unlink(tocpath)
        return retcode
