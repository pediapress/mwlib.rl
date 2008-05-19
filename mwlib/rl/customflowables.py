#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import string 

from reportlab.platypus.flowables import *
from reportlab.platypus.paragraph import *
from reportlab.lib.colors import Color

class Figure(Flowable):

    def __init__(self,imgFile, captionTxt, captionStyle, imgWidth=None, imgHeight=None, margin=(0,0,0,0), padding=(0,0,0,0), align=None, borderColor=(0.75,0.75,0.75)):
        imgFile = imgFile 
        self.imgPath = imgFile
        self.i = Image(imgFile, width=imgWidth, height=imgHeight)
        self.imgWidth = imgWidth
        self.imgHeight = imgHeight
        self.c = Paragraph(captionTxt, style=captionStyle)
        self.margin = margin # 4-tuple. margins in order: top, right, bottom, left
        self.padding = padding # same as above
        self.borderColor = borderColor
        self.align = align
        self.cs = captionStyle
        self.captionTxt = captionTxt
        self.availWidth = None
        self.availHeight = None
        
    def draw(self):
        canv = self.canv
        if self.align == "center":
            canv.translate((self.availWidth-self.width)/2,0)
        canv.saveState()
        canv.setStrokeColor(Color(self.borderColor[0],self.borderColor[1], self.borderColor[2]))
        canv.rect(self.margin[3], self.margin[2], self.boxWidth, self.boxHeight)
        canv.restoreState()
        canv.translate(self.margin[3] + self.padding[3], self.margin[2] + self.padding[2] - 2)
        self.c.canv = canv
        self.c.draw()
        canv.translate( (self.boxWidth - self.padding[1] - self.padding[3] - self.i.drawWidth)/2, self.captionHeight +2)
        self.i.canv = canv
        self.i.draw()       
        
    def wrap(self, availWidth, availHeight):
        self.availWidth = availWidth
        self.availHeight = availHeight
        contentWidth = max(self.i.drawWidth,self.c.wrap(self.i.drawWidth,availHeight)[0])
        self.boxWidth = contentWidth + self.padding[1] + self.padding[3]  
        (self.captionWidth,self.captionHeight) = self.c.wrap(contentWidth, availHeight)
        self.captionHeight += self.cs.spaceBefore + self.cs.spaceAfter
        self.boxHeight = self.i.drawHeight + self.captionHeight + self.padding[0] + self.padding[2] 
        self.width = self.boxWidth + self.margin[1] + self.margin[3]
        self.height = self.boxHeight + self.margin[0] + self.margin[2]
        return (self.width, self.height)    


class FiguresAndParagraphs(Flowable):
    """takes a list of figures and paragraphs and floats the figures
    next to the paragraphs.
    current limitations:
     * all figures are floated on the same side as the first image
     * the biggest figure-width is used as the text-margin
    """
    def __init__(self, figures, paragraphs, figure_margin=(0,0,0,0)):
        self.fs = figures
        self.figure_margin = figure_margin
        for f in self.fs:
            f.margin = figure_margin
        self.ps = paragraphs
        self.figAlign = figures[0].align # fixme: all figures will be aligned like the first figure
        self.wfs = [] #width of figures
        self.hfs = [] # height of figures

    def _getVOffset(self):
        for p in self.ps:
            if hasattr(p, 'style') and hasattr(p.style, 'spaceBefore'):
                return p.style.spaceBefore
        return 0
    
    def wrap(self,availWidth,availHeight):
        maxWf = 0
        self.wfs = []
        self.hfs = []
        self.horizontalRuleOffsets = []
        totalHf = self._getVOffset()        
        for f in self.fs:
            wf, hf = f.wrap(availWidth,availHeight)
            totalHf += hf
            maxWf = max(maxWf, wf)
            self.wfs.append(wf) 
            self.hfs.append(hf) 
            
        self.paraHeights = []
        self._offsets = []
        for p in self.ps:
            if isinstance(p, HRFlowable):
                self.paraHeights.append(1) # fixme: whats the acutal height of a HRFlowable?
                self._offsets.append(0)
                if (totalHf - (sum(self.paraHeights))) > 0: # behave like the associated heading
                    self.horizontalRuleOffsets.append(maxWf)
                else:
                    self.horizontalRuleOffsets.append(0)
                continue
            fullWidth = availWidth - p.style.leftIndent - p.style.rightIndent
            floatWidth = fullWidth - maxWf
            nfloatLines = max(0, int((totalHf - (sum(self.paraHeights)))/p.style.leading)) 
            p.width = 0
            p.blPara = p.breakLines(nfloatLines*[floatWidth] + [fullWidth])
            if self.figAlign=='left':
                self._offsets.append([maxWf]*(nfloatLines) + [0])
            if hasattr(p, 'style'):
                autoLeading = getattr(p.style, 'autoLeading')
            else:
                autoLeading = ''
            if hasattr(p, 'style') and autoLeading == 'max' and p.blPara.kind == 1:
                pHeight = 0
                for l in p.blPara.lines:
                    pHeight += max(l.ascent - l.descent, p.style.leading) * 1.025 #magic factor! autoLeading==max increases line-height
            else:
                if autoLeading=='max':
                    pHeight = len(p.blPara.lines)*max(p.style.leading, 1.2*p.style.fontSize) # used to be 1.2 instead of 1.0
                else:
                    pHeight = len(p.blPara.lines)*p.style.leading
            self.paraHeights.append(pHeight + p.style.spaceBefore + p.style.spaceAfter)                        

        self.width = availWidth
        self.height =  max(sum(self.paraHeights), totalHf)
        return (availWidth,self.height)

    def draw(self):
        canv = self.canv
        canv.saveState()
        vertical_offset = self._getVOffset()
        if self.figAlign == 'left':
            horizontal_offsets = [0]*len(self.fs)
        else: 
            horizontal_offsets = [self.width-wf for wf in self.wfs]

        for (i,f) in enumerate(self.fs):
            vertical_offset += self.hfs[i]
            f.drawOn(canv,horizontal_offsets[i], self.height - vertical_offset )

        canv.translate(0, self.height)
       
        #bulletIndent = li_style.bulletIndent
        lastSpace = 0
        for (count,p) in enumerate(self.ps):
            if self.figAlign == 'left':
                p._offsets = self._offsets[count]
                if hasattr(p, 'style') and hasattr(p.style, 'bulletIndent'):
                    p.style.bulletIndent = p._offsets[0]
            if isinstance(p, HRFlowable):
                p.canv = canv
                widthOffset = self.horizontalRuleOffsets.pop(0)
                if self.figAlign == 'left':
                    canv.translate(widthOffset,0)                    
                p.wrap(self.width - widthOffset , self.height)
                p.draw()
            else:
                canv.translate(0,-p.style.spaceBefore)
                p.canv = canv
                p.draw()
                canv.translate(0, - self.paraHeights[count] + p.style.spaceBefore )
        #li_style.bulletIndent = bulletIndent
        canv.restoreState()

    def split(self, availWidth, availheight):
        if not hasattr(self,'hfs') or len(self.hfs)==0:
            self.wrap(availWidth, availheight)
        height = self._getVOffset()
        if self.hfs[0] + height > availheight:
            return [PageBreak()] + [FiguresAndParagraphs(self.fs, self.ps, figure_margin=self.figure_margin )]
        fittingFigures = []
        nextFigures = []
        for (i, f) in enumerate(self.fs):
            if (height + self.hfs[i]) < availheight:
                fittingFigures.append(f)
            else:
                nextFigures.append(f)
            height += self.hfs[i]

        fittingParas = []
        nextParas = []
        height = 0
        splittedParagraph=False
        for (i,p) in enumerate(self.ps):
            if (height + self.paraHeights[i]) < availheight:
                fittingParas.append(p)
            else:
                # inter-paragraph splitting can be avoided by uncommenting the following
                #nextParas.append(p)
                #height += self.paraHeights[i]
                #continue
                if splittedParagraph:
                    nextParas.append(p)
                    continue
                paraFrags = p.split(availWidth, availheight - height - p.style.spaceBefore - p.style.spaceAfter - p.style.leading) # one line-height "safety margin"
                splittedParagraph=True
                if len(paraFrags) == 2:
                    fittingParas.append(paraFrags[0])
                    nextParas.append(paraFrags[1])
                elif len(paraFrags) < 2:
                    nextParas.append(p)
                else: # fixme: not sure if splitting a paragraph can yield more than two elements...
                    pass
            height += self.paraHeights[i]
        
        if nextFigures:
            if nextParas:
                nextElements = [FiguresAndParagraphs(nextFigures, nextParas, figure_margin=self.figure_margin)]
            else:
                nextElements = nextFigures
        else:
            if nextParas:
                nextElements = nextParas
            else:
                nextElements = []        

        return [FiguresAndParagraphs(fittingFigures, fittingParas, figure_margin=self.figure_margin)] + nextElements
                
class PreformattedBox(Preformatted):
    def __init__(self, text, style, margin=4, padding=4, borderwidth=0.1, **kwargs):
        Preformatted.__init__(self, text, style, **kwargs)
        self.margin = margin
        self.padding = padding
        self.borderwidth = borderwidth

    def wrap(self, availWidth, availHeight):
        w,h = Preformatted.wrap(self,availWidth, availHeight)
        return ( w+self.margin+self.borderwidth+self.padding*2, h+self.margin+self.borderwidth+self.padding*2)

    def draw(self):
        self.canv.saveState()
        self.canv.setLineWidth(self.borderwidth)
        self.canv.translate(0,self.margin)
        self.canv.rect(0,0,self.width, self.height+self.padding*2)
        self.canv.translate(0, self.style.spaceAfter)
        Preformatted.draw(self)
        self.canv.restoreState()

    def split(self, availWidth, availHeight):
        if availHeight < self.style.leading:
            return []

        linesThatFit = int((availHeight-self.padding-self.margin) * 1.0 / self.style.leading)

        text1 = string.join(self.lines[0:linesThatFit], '\n')
        text2 = string.join(self.lines[linesThatFit:], '\n')
        style = self.style
        if style.firstLineIndent != 0:
            style = deepcopy(style)
            style.firstLineIndent = 0
        return [PreformattedBox(text1, style, margin=self.margin, padding=self.padding, borderwidth=self.borderwidth), 
                PreformattedBox(text2, style, margin=self.margin, padding=self.padding, borderwidth=self.borderwidth)]  
