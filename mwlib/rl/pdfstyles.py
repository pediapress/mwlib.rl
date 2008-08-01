#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY #,TA_RIGHT
from reportlab.lib.units import cm
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4


########## REGISTER FONTS

def fontpath(n):
    import mwlib.fonts
    fp = os.path.dirname(mwlib.fonts.__file__)
    return os.path.join(fp, n)

pdfmetrics.registerFont(TTFont('DejaVuSans',  fontpath('DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', fontpath('DejaVuSans-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-Italic', fontpath('DejaVuSans-Oblique.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-BoldItalic', fontpath('DejaVuSans-BoldOblique.ttf')))

addMapping('DejaVuSans', 0, 0, 'DejaVuSans')    
addMapping('DejaVuSans', 0, 1, 'DejaVuSans-Italic')
addMapping('DejaVuSans', 1, 0, 'DejaVuSans-Bold')
addMapping('DejaVuSans', 1, 1, 'DejaVuSans-BoldItalic')

pdfmetrics.registerFont(TTFont('DejaVuSansMono',  fontpath('DejaVuSansMono.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-Bold', fontpath('DejaVuSansMono-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-Italic', fontpath('DejaVuSansMono-Oblique.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-BoldItalic', fontpath('DejaVuSansMono-BoldOblique.ttf')))

addMapping('DejaVuSansMono', 0, 0, 'DejaVuSansMono')
addMapping('DejaVuSansMono', 0, 1, 'DejaVuSansMono-Italic')
addMapping('DejaVuSansMono', 1, 0, 'DejaVuSansMono-Bold')
addMapping('DejaVuSansMono', 1, 1, 'DejaVuSansMono-BoldItalic')

pdfmetrics.registerFont(TTFont('DejaVuSerif',  fontpath('DejaVuSerif.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-Bold', fontpath('DejaVuSerif-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-Italic', fontpath('DejaVuSerif-Italic.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-BoldItalic', fontpath('DejaVuSerif-BoldItalic.ttf')))

addMapping('DejaVuSerif', 0, 0, 'DejaVuSerif')
addMapping('DejaVuSerif', 0, 1, 'DejaVuSerif-Italic')
addMapping('DejaVuSerif', 1, 0, 'DejaVuSerif-Bold')
addMapping('DejaVuSerif', 1, 1, 'DejaVuSerif-BoldItalic')

from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light')) #CHS
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium')) #KOR

standardFont =  "DejaVuSerif"
standardSansSerif = "DejaVuSans"
standardMonoFont = "DejaVuSansMono"
########## / REGISTER FONTS

### TABLE CONFIG

tableOverflowTolerance = 20  # max width overflow for tables    unit: pt 


######### PAGE CONFIGURATION

pageWidth, pageHeight = A4   # roughly: pW= 21*cm pH=29*cm

pageMarginHor = 2 * cm
pageMarginVert= 2 * cm

headerMarginHor = 1.5 * cm
headerMarginVert= 1.5 * cm

printWidth = pageWidth - 2*pageMarginHor
printHeight = pageHeight - 2*pageMarginVert

footerMarginHor = 1.5 * cm
footerMarginVert= 1.5 * cm

showPageHeader = True 
showPageFooter = True
showTitlePageFooter = True
pageBreakAfterArticle = False



# NOTE: strings can contain reportlab styling tags the text needs to be xml excaped.
# more information is available in the reportlab user documentation (http://www.reportlab.com/docs/userguide.pdf)
# check the section 6.2 "Paragraph XML Markup Tags"
# since the documenatition is not guaranteed to be up to date, you might also want to check the docsting of the
# Paragraph class (reportlab/platypus/paragraph.py --> class Paragraph())
# e.g. the use of inline images is not included in the official documenation of reportlab
pagefooter = u'All Articles originate from @WIKITITLE@  (@WIKIURL@)'
titlepagefooter = u'@WIKITITLE@ book - Generated using the open source mwlib toolkit - <br/>see http://code.pediapress.com for more information'


######### IMAGE CONFIGURATION

max_img_width = 9 # max size in cm 
max_img_height = 12 
min_img_dpi = 75 # scaling factor in respect to the thumbnail-size in the wikimarkup which limits image-size
inline_img_dpi = 100 # scaling factor for inline images. 100 dpi should be the ideal size in relation to 10pt text size 

######### TEXT CONFIGURATION
FONTSIZE = 10
LEADING = 15

SMALLFONTSIZE = 8
SMALLLEADING = 12

BIGFONTSIZE = 12
BIGLEADING = 17

LEFTINDENT = 25 # indentation of paragraphs...
RIGHTINDENT = 25 # indentation of paragraphs...
LISTINDENT = 12 # indentation of lists per level

maxCharsInSourceLine = 72 # if printing a source node, the maximum number of chars in one line

class BaseStyle(ParagraphStyle):

    def __init__(self, name, parent=None, **kw):
        ParagraphStyle.__init__(self, name=name, parent=parent, **kw)
        self.fontName = standardFont
        self.fontSize = FONTSIZE
        self.leading = LEADING
        self.autoLeading = 'max'
        self.leftIndent = 0
        self.rightIndent = 0
        self.firstLineIndent = 0
        self.alignment = TA_LEFT        
        self.spaceBefore = 3
        self.spaceAfter = 0
        self.bulletFontName = standardFont
        self.bulletFontSize = FONTSIZE
        self.bulletIndent = 0
        self.textColor = black
        self.backcolor = None
        self.wordWrap = None
        self.textTransform = None
            
def text_style(mode='p', indent_lvl=0, in_table=0, relsize='normal'):
    """
    mode: p (normal paragraph), blockquote, center (centered paragraph), footer, figure (figure caption text),
          preformatted, list
    relsize: relative text size: small, normal, big  (currently only used for preformatted nodes
    indent_lvl: level of indentation in lists or indented paragraphs
    in_table: 0 - outside table
              1 or above - inside table (nesting level of table)
    """

    style = BaseStyle(name='text_style_%s_indent_%d_table_%d_size_%s' % (mode, indent_lvl, in_table, relsize))
    style.flowable = True # needed for "flowing" paragraphs around figures

    if in_table or mode in ['footer', 'figure'] or (mode=='preformatted' and relsize=='small'):
        style.fontSize=SMALLFONTSIZE
        style.bulletFontSize = SMALLFONTSIZE
        style.leading = SMALLLEADING
        if relsize == 'small':
            style.fontSize -= 1
        elif relsize == 'big':
            style.fontSize += 1

    if mode == 'blockquote':
        style.rightIndent = RIGHTINDENT
        indent_lvl += 1

    if mode in ['footer', 'figure', 'center']:
        style.alignment = TA_CENTER

    if mode == 'preformatted':
        style.spaceAfter = 3
        style.fontName = standardMonoFont
        indent_lvl += 1
        style.backColor = '#eeeeee'

    if mode == 'source':
        style.spaceAfter = 3
        style.fontName = standardMonoFont       
        style.backColor = '#eeeeee'
        
    if mode == 'list':
        style.spaceBefore = 0
        style.bulletIndent = LISTINDENT * max(0, indent_lvl-1)
        style.leftIndent = LISTINDENT * indent_lvl
    else:
        style.leftIndent = indent_lvl*LEFTINDENT

    if mode == 'booktitle':
        style.fontSize = 36
        style.leading = 40
        style.spaceBefore = 16
        style.fontName= standardSansSerif

    if mode == 'booksubtitle':
        style.fontSize = 24
        style.leading = 30
        style.fontName= standardSansSerif
        
    return style

table_style = {'spaceBefore': 0.25*cm,
               'spaceAfter': 0.25*cm}


class BaseHeadingStyle(ParagraphStyle):

    def __init__(self, name, parent=None, **kw):
        ParagraphStyle.__init__(self, name=name, parent=parent, **kw)
        self.fontName = standardSansSerif
        self.fontSize = BIGFONTSIZE
        self.leading = LEADING
        self.autoLeading = 'max'
        self.leftIndent = 0
        self.rightIndent = 0
        self.firstLineIndent = 0
        self.alignment = TA_LEFT        
        self.spaceBefore = 12
        self.spaceAfter = 6
        self.bulletFontName = standardFont
        self.bulletFontSize = BIGFONTSIZE
        self.bulletIndent = 0
        self.textColor = black
        self.backcolor = None
        self.wordWrap = None
        self.textTransform = None
        
def heading_style(mode='chapter', lvl=1):

    style = BaseHeadingStyle(name='heading_style_%s_%d' % (mode, lvl))

    if mode == 'chapter':
        style.fontSize = 26
        style.leading = 30
        style.alignment = TA_CENTER
    elif mode == 'article':
        style.fontSize = 22
        style.leading = 26
        style.spaceBefore = 20
        style.spaceAfter = 2
    elif mode == 'section':
        lvl = max(min(5,lvl), 1)  
        style.fontSize = 18 - (lvl - 1) * 2
        style.leading = style.fontSize + max(2, min(int(style.fontSize / 5), 3)) # magic: increase in leading is between 2 and 3 depending on fontsize...
        style.spaceBefore = min(style.leading, 20)
        if lvl > 1: # needed for "flowing" paragraphs around figures
            style.flowable = True
            
    return style
    

# import custom configuration to override configuration values
# if doing so, you need to be careful not to break things...
try:
    from customconfig import *
except ImportError:
    pass
