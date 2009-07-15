#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import subprocess
import shutil

import mwlib.ext
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.tables import Table

from mwlib.rl import pdfstyles
from mwlib.rl import fontconfig
from mwlib.rl.formatter import RLFormatter


class TocRenderer(object):

    def __init__(self):
        font_switcher = fontconfig.RLFontSwitcher()
        font_switcher.font_paths = fontconfig.font_paths
        font_switcher.registerDefaultFont(pdfstyles.default_font)
        font_switcher.registerFontDefinitionList(fontconfig.fonts)
        font_switcher.registerReportlabFonts(fontconfig.fonts)

        
    def build(self, pdfpath, toc_entries):
        outpath = os.path.dirname(pdfpath)
        tocpath = os.path.join(outpath, 'toc.pdf')
        finalpath = os.path.join(outpath, 'final.pdf')
        self.renderToc(tocpath, toc_entries)
        return self.combinePdfs(pdfpath, tocpath, finalpath)

    def _getColWidths(self):
        p = Paragraph('<b>%d</b>' % 9999, pdfstyles.text_style(mode='toc_article', text_align='right'))        
        w, h = p.wrap(0, pdfstyles.print_height)
        # subtracting 30pt below is *probably* necessary b/c of the table margins
        return [pdfstyles.print_width - w - 30, w]
    
    def renderToc(self, tocpath, toc_entries):
        doc = SimpleDocTemplate(tocpath)
        elements = []
        elements.append(Paragraph(_('Contents'), pdfstyles.heading_style(mode='chapter', text_align='left')))
        toc_table =[]
        col_widths = self._getColWidths()
        for lvl, txt, page_num in toc_entries:
            page_num = '<b>%d</b>' % (page_num) if lvl != 'article' else str(page_num)
            toc_table.append([
                Paragraph(txt, pdfstyles.text_style(mode='toc_%s' % str(lvl), text_align='left')),
                Paragraph(page_num, pdfstyles.text_style(mode='toc_article', text_align='right'))
                ])
        elements.append(Table(toc_table, colWidths=col_widths))
        doc.build(elements)

    def combinePdfs(self, pdfpath, tocpath, finalpath):

        cmd =  ['pdftk',
                'A=%s' % pdfpath,
                'B=%s' % tocpath,
                'cat', 'A1', 'B', 'A2-end',
                'output','%s' % finalpath,
                ]
        try:
            retcode = subprocess.call(cmd)
        except OSError:
            retcode = 1
        if retcode == 0:
            shutil.move(finalpath, pdfpath)
        return retcode
