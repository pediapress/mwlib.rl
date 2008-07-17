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
from mwlib.rl.pdfstyles import pageMarginHor, pageMarginVert, headerMarginHor, headerMarginVert, footerMarginHor, footerMarginVert
from mwlib.rl.pdfstyles import pageWidth, pageHeight, pagefooter, titlepagefooter, showPageHeader, showPageFooter, showTitlePageFooter , standardFont
from reportlab.lib.pagesizes import  A3

from mwlib.rl.pdfstyles import text_style
from mwlib.rl.rlhelpers import filterText


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

    def __init__(self,title=None, wikititle='undefined', wikiurl='undefined', id=None, onPage=_doNothing, onPageEnd=_doNothing,
                 pagesize=defaultPageSize):
        """
        @type title: unicode
        """
        
        id = title.encode('utf-8')
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)
        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)

        self.title = title
        self.wikititle = wikititle
        self.wikiurl = wikiurl
        
    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(standardFont,10)      
        canvas.saveState()
        #header
        canvas.line(headerMarginHor, pageHeight - headerMarginVert, pageWidth - headerMarginHor, pageHeight - headerMarginVert )
        if showPageHeader:
            canvas.saveState()
            canvas.resetTransforms()
            canvas.translate(headerMarginHor, pageHeight - headerMarginVert - 0.1*cm)
            p = Paragraph(filterText(self.title), text_style())
            p.canv = canvas
            p.wrap(pageWidth - headerMarginHor*2.5, pageHeight) # add an extra 0.5 margin to have enough space for page number
            p.drawPara()
            canvas.restoreState()
            
        canvas.drawRightString(pageWidth - headerMarginHor, pageHeight - headerMarginVert + 0.1 * cm, "%d" % doc.page)

        #Footer
        canvas.saveState()
        canvas.setFont(standardFont,8)
        canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
        if showPageFooter:
            footertext = filterText(pagefooter.replace('@WIKITITLE@', self.wikititle).replace('@WIKIURL@', self.wikiurl))
            p = Paragraph(footertext, text_style())
            p.canv = canvas
            w,h = p.wrap(pageWidth - footerMarginHor*2.5, pageHeight) 
            canvas.translate(headerMarginHor, footerMarginVert-h - 0.1*cm)
            p.drawPara()
            

            
        canvas.restoreState()
    


class TitlePage(PageTemplate):

    def __init__(self, wikititle='undefined', cover=None, id=None, onPage=_doNothing, onPageEnd=_doNothing,
                 pagesize=defaultPageSize):

        id = 'TitlePage'
        frames = Frame(pageMarginHor,pageMarginVert,pageWidth - 2*pageMarginHor, pageHeight - 2*pageMarginVert)        
        PageTemplate.__init__(self,id=id, frames=frames,onPage=onPage,onPageEnd=onPageEnd,pagesize=pagesize)
        self.cover = cover
        self.wikititle = wikititle

    def beforeDrawPage(self,canvas,doc):
        canvas.setFont(standardFont,8)
        canvas.saveState()
        if showTitlePageFooter:
            canvas.line(footerMarginHor, footerMarginVert, pageWidth - footerMarginHor, footerMarginVert )
            footertext = titlepagefooter.replace('@WIKITITLE@', self.wikititle)
            p = Paragraph(filterText(footertext), text_style(mode='footer'))           
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
