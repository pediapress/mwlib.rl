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
from reportlab.rl_config import defaultPageSize
from mwlib.rl.pdfstyles import pageMarginHor, pageMarginVert, headerMarginHor, headerMarginVert, footerMarginHor, footerMarginVert, pageWidth, pageHeight, pagefooter, titlepagefooter, showPageHeader, showPageFooter, showTitlePageFooter , standardFont, footer_style

def _doNothing(canvas, doc):
    "Dummy callback for onPage"
    pass

class WikiPage(PageTemplate):

    def __init__(self,title=None,id=None,onPage=_doNothing, onPageEnd=_doNothing,
                 pagesize=defaultPageSize):

        id = title.encode('utf-8')
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)
        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)

        self.title = title

    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(standardFont,10)      
        canvas.saveState()
        #header
        canvas.line(headerMarginHor, pageHeight - headerMarginVert, pageWidth - headerMarginHor, pageHeight - headerMarginVert )
        if showPageHeader:
            canvas.drawString(headerMarginHor, pageHeight - headerMarginVert + 0.1 * cm, self.title)
        canvas.drawRightString(pageWidth - headerMarginHor, pageHeight - headerMarginVert + 0.1 * cm, "%d" % doc.page)

        #Footer
        canvas.setFont(standardFont,8)
        canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
        if showPageFooter:
            canvas.drawCentredString(pageWidth/2.0, footerMarginVert - 0.5*cm, pagefooter)
        canvas.restoreState()
    


class TitlePage(PageTemplate):

    def __init__(self,title=None, subTitle=None, author=None, cover=None, id=None,onPage=_doNothing, onPageEnd=_doNothing,
                 pagesize=defaultPageSize):

        id = 'TitlePage'
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)
        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)

        self.title = title
        self.subTitle = subTitle
        self.author =author
        self.cover = cover

    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(standardFont,8)
        canvas.saveState()
        if showTitlePageFooter:
            canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
            p = Paragraph(titlepagefooter,footer_style)           
            w,h = p.wrap(pageWidth - 2*pageMarginHor,pageHeight-pageMarginVert)
            canvas.translate( (pageWidth-w)/2.0, h)
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
