#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

from PIL import Image

from reportlab.platypus.paragraph import Paragraph
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import PageTemplate
from reportlab.platypus.frames import Frame
from mwlib.rl.pdfstyles import pageMarginHor, pageMarginVert, headerMarginHor, headerMarginVert, footerMarginHor, footerMarginVert
from mwlib.rl.pdfstyles import pageWidth, pageHeight, pagefooter, titlepagefooter, showPageHeader, showPageFooter, showTitlePageFooter , serif_font
from mwlib.rl import pdfstyles

from reportlab.lib.pagesizes import  A3

from mwlib.rl.pdfstyles import text_style
from mwlib.rl.rlhelpers import RLFontSwitcher 

font_switcher = RLFontSwitcher()
font_switcher.registerDefaultFont(pdfstyles.default_font)        
font_switcher.registerFontDefinitionList(pdfstyles.fonts)
        
def _doNothing(canvas, doc):
    "Dummy callback for onPage"
    pass

class SimplePage(PageTemplate):
    def __init__(self, pageSize=A3):
        id = 'simplepage'
        #frames = Frame(0, 0, pageSize[0], pageSize[1])
        pw = pageSize[0]
        ph = pageSize[1]
        frames = Frame(pageMarginHor,pageMarginVert, pw - 2*pageMarginHor, ph - 2*pageMarginVert)

        PageTemplate.__init__(self, id=id, frames=frames, pagesize=pageSize)
        
class WikiPage(PageTemplate):

    def __init__(self,title=None, id=None, wikititle=u'undefined', wikiurl=u'undefined', onPage=_doNothing, onPageEnd=_doNothing, pagesize=(pageWidth, pageHeight)):
        """
        @type title: unicode
        """
        
        id = title.encode('utf-8')
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)
        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)

        self.title = title
    
    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(serif_font,10)      
        canvas.setLineWidth(0)
        canvas.saveState()
        #header
        canvas.line(headerMarginHor, pageHeight - headerMarginVert, pageWidth - headerMarginHor, pageHeight - headerMarginVert )
        if showPageHeader:
            canvas.saveState()
            canvas.resetTransforms()
            canvas.translate(headerMarginHor, pageHeight - headerMarginVert - 0.1*cm)
            p = Paragraph(font_switcher.fontifyText(self.title), text_style())
            p.canv = canvas
            p.wrap(pageWidth - headerMarginHor*2.5, pageHeight) # add an extra 0.5 margin to have enough space for page number
            p.drawPara()
            canvas.restoreState()
            
        canvas.drawRightString(pageWidth - headerMarginHor, pageHeight - headerMarginVert + 0.1 * cm, "%d" % doc.page)

        #Footer
        canvas.saveState()
        canvas.setFont(serif_font,8)
        canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
        if showPageFooter:
            p = Paragraph(font_switcher.fontifyText(pagefooter), text_style())
            p.canv = canvas
            w,h = p.wrap(pageWidth - headerMarginHor*2.5, pageHeight)
            p.drawOn(canvas, footerMarginHor, footerMarginVert - 10 - h)
        canvas.restoreState()
    


class TitlePage(PageTemplate):

    def __init__(self, wikititle=u'undefined', wikiurl=u'undefined', cover=None, id=None,
        onPage=_doNothing, onPageEnd=_doNothing, pagesize=(pageWidth, pageHeight)):

        id = 'TitlePage'
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)
        self.wikititle = wikititle
        self.wikiurl = wikiurl
        self.cover = cover
    
    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(serif_font,8)
        canvas.saveState()
        if showTitlePageFooter:
            canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
            footertext = _(titlepagefooter).replace('@WIKITITLE@', self.wikititle).replace('@WIKIURL@', self.wikiurl)
            p = Paragraph(font_switcher.fontifyText(footertext), text_style(mode='footer'))           
            w,h = p.wrap(pageWidth - 2*pageMarginHor,pageHeight-pageMarginVert)
            canvas.translate( (pageWidth-w)/2.0, 0.2*cm)
            p.canv = canvas
            p.draw()
        canvas.restoreState()
        if self.cover:
            width = 12 * cm
            img = Image.open(self.cover)
            w,h = img.size
            height = width/w*h 
            x = (pageWidth - width) / 2.0
            y = (pageHeight - height) / 2.0
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
        
    def progressCB(self, typ, value):
        if typ == 'SIZE_EST':
            self.estimatedDuration = int(value)
        if typ == 'PROGRESS':
            self.progress = 100 * int(value) / self.estimatedDuration
        if typ == 'PAGE':
            self.status_callback(progress=self.progress, page=value)
        
    def _startBuild(self, filename=None, canvasmaker=canvas.Canvas):
        BaseDocTemplate._startBuild(self, filename=filename, canvasmaker=canvasmaker)

        type2lvl = {'chapter': 0,
                    'article': 1,
                    'heading': 2}
        got_chapter = False
        for (bm_id, (bm_title, bm_type)) in enumerate(self.bookmarks):            
            lvl = type2lvl[bm_type]
            if bm_type== 'chapter':
                got_chapter = True
            elif not got_chapter: # outline-lvls can't start above zero
                lvl -= 1
            self.canv.addOutlineEntry(bm_title, str(bm_id), lvl, bm_type == 'article')

    def afterFlowable(self, flowable):
        """Our rule for the table of contents is simply to take
        the text of H1, H2 and H3 elements. We broadcast a
        notification to the DocTemplate, which should inform
        the TOC and let it pull them out."""
        if not self.tocCallback:
            return
        if hasattr(flowable, 'style'):
            n = flowable.style.name

            if n == 'heading_style_chapter_1':
                self.tocCallback((0, flowable.getPlainText(), self.page))
            elif n == 'heading_style_article_1':
                self.tocCallback((1, flowable.getPlainText(), self.page))
        
