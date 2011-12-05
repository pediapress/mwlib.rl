#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

from PIL import Image
from time import gmtime, strftime

from reportlab.platypus.paragraph import Paragraph
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import PageTemplate
from reportlab.platypus.frames import Frame
from mwlib.rl.pdfstyles import page_margin_left, page_margin_right, page_margin_top, page_margin_bottom
from mwlib.rl.pdfstyles import page_width, page_height, print_height, print_width
from mwlib.rl.pdfstyles import header_margin_hor, header_margin_vert, footer_margin_hor, footer_margin_vert
from mwlib.rl.pdfstyles import pagefooter, titlepagefooter, serif_font
from mwlib.rl import pdfstyles
from mwlib.rl.customflowables import TocEntry

from reportlab.lib.pagesizes import  A3

from mwlib.rl.pdfstyles import text_style

from mwlib.rl import fontconfig
from mwlib.rl.formatter import RLFormatter
font_switcher = fontconfig.RLFontSwitcher()
font_switcher.font_paths = fontconfig.font_paths
font_switcher.registerDefaultFont(pdfstyles.default_font)
font_switcher.registerFontDefinitionList(fontconfig.fonts)

formatter = RLFormatter(font_switcher=font_switcher)

def _doNothing(canvas, doc):
    "Dummy callback for onPage"
    pass

class SimplePage(PageTemplate):
    def __init__(self, pageSize=A3):
        id = 'simplepage'
        #frames = Frame(0, 0, pageSize[0], pageSize[1])
        pw = pageSize[0]
        ph = pageSize[1]
        frames = Frame(page_margin_left, page_margin_bottom, pw-page_margin_left-page_margin_right, ph-page_margin_top-page_margin_bottom)

        PageTemplate.__init__(self, id=id, frames=frames, pagesize=pageSize)

class WikiPage(PageTemplate):

    def __init__(self,
                 title=None,
                 id=None,
                 onPage=_doNothing,
                 onPageEnd=_doNothing,
                 pagesize=(page_width, page_height),
                 rtl=False,
                 ):
        """
        @type title: unicode
        """

        id = title.encode('utf-8')
        frames = Frame(page_margin_left,page_margin_bottom, print_width, print_height)

        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)

        self.title = title
        self.rtl = rtl

    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(serif_font,10)
        canvas.setLineWidth(0)
        #header
        canvas.line(header_margin_hor, page_height - header_margin_vert, page_width - header_margin_hor, page_height - header_margin_vert )
        if pdfstyles.show_page_header:
            canvas.saveState()
            canvas.resetTransforms()
            if not self.rtl:
                h_offset = header_margin_hor
            else:
                h_offset = 1.5*header_margin_hor
            canvas.translate(h_offset, page_height - header_margin_vert - 0.1*cm)
            p = Paragraph(self.title, text_style())
            p.canv = canvas
            p.wrap(page_width - header_margin_hor*2.5, page_height) # add an extra 0.5 margin to have enough space for page number
            p.drawPara()
            canvas.restoreState()

        if not self.rtl:
            h_pos =  page_width - header_margin_hor
            d = canvas.drawRightString
        else:
            h_pos = header_margin_hor
            d = canvas.drawString
        d(h_pos, page_height - header_margin_vert + 0.1 * cm, "%d" % doc.page)

        #Footer
        canvas.saveState()
        canvas.setFont(serif_font,8)
        canvas.line(footer_margin_hor, footer_margin_vert, page_width - footer_margin_hor, footer_margin_vert )
        if pdfstyles.show_page_footer:
            p = Paragraph(formatter.cleanText(pagefooter, escape=False), text_style())
            p.canv = canvas
            w,h = p.wrap(page_width - header_margin_hor*2.5, page_height)
            p.drawOn(canvas, footer_margin_hor, footer_margin_vert - 10 - h)
        canvas.restoreState()



class TitlePage(PageTemplate):

    def __init__(self, cover=None, id=None,
        onPage=_doNothing, onPageEnd=_doNothing, pagesize=(page_width, page_height)):

        id = 'TitlePage'
        frames = Frame(page_margin_left, page_margin_bottom, print_width, print_height)
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)
        self.cover = cover

    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(serif_font,8)
        canvas.saveState()
        if pdfstyles.show_title_page_footer:
            canvas.line(footer_margin_hor, footer_margin_vert, page_width - footer_margin_hor, footer_margin_vert )
            footertext = [_(titlepagefooter)]
            if pdfstyles.show_creation_date:
                footertext.append('PDF generated at: %s' % strftime("%a, %d %b %Y %H:%M:%S %Z", gmtime()))
            p = Paragraph('<br/>'.join([formatter.cleanText(line, escape=False) for line in footertext]),
                          text_style(mode='footer'))
            w,h = p.wrap(print_width, print_height)
            canvas.translate( (page_width-w)/2.0, 0.2*cm)
            p.canv = canvas
            p.draw()
        canvas.restoreState()
        if self.cover:
            width = 12 * cm
            img = Image.open(self.cover)
            w,h = img.size
            height = width/w*h
            x = (page_width - width) / 2.0
            y = (page_height - height) / 2.0
            canvas.drawImage(self.cover, x, y, width , height)

from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.pdfgen import canvas

class PPDocTemplate(BaseDocTemplate):

    def __init__(self, output, status_callback=None, tocCallback=None, **kwargs):
        self.bookmarks = []
        BaseDocTemplate.__init__(self, output, **kwargs)
        if status_callback:
            self.estimatedDuration = 0
            self.progress = 0
            self.setProgressCallBack(self.progressCB)
            self.status_callback = status_callback
        self.tocCallback=tocCallback
        self.title = kwargs['title']

    def progressCB(self, typ, value):
        if typ == 'SIZE_EST':
            self.estimatedDuration = int(value)
        if typ == 'PROGRESS':
            self.progress = 100 * int(value) / self.estimatedDuration
        if typ == 'PAGE':
            self.status_callback(progress=self.progress, page=value)

    def beforeDocument(self):
        if self.title:
            self.page = -1

    def _startBuild(self, filename=None, canvasmaker=canvas.Canvas):
        BaseDocTemplate._startBuild(self, filename=filename, canvasmaker=canvasmaker)

        type2lvl = {'chapter': 0,
                    'article': 1,
                    'heading2': 2,
                    'heading3': 3,
                    'heading4': 4,
                    }
        got_chapter = False
        last_lvl =  0
        for (bm_id, (bm_title, bm_type)) in enumerate(self.bookmarks):
            lvl = type2lvl[bm_type]
            if bm_type== 'chapter':
                got_chapter = True
            elif not got_chapter: # outline-lvls can't start above zero
                lvl -= 1
            lvl = min(lvl, last_lvl + 1)
            last_lvl = lvl
            self.canv.addOutlineEntry(bm_title, str(bm_id), lvl, bm_type == 'article')

    def afterFlowable(self, flowable):
        """Our rule for the table of contents is simply to take
        the text of H1, H2 and H3 elements. We broadcast a
        notification to the DocTemplate, which should inform
        the TOC and let it pull them out."""
        if not self.tocCallback:
            return
        if flowable.__class__ == TocEntry:
            self.tocCallback((flowable.lvl, flowable.txt, self.page))

