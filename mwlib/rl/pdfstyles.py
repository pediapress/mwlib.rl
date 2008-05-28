#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os

from reportlab.lib.styles import PropertySet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY #TA_RIGHT
from reportlab.lib.units import cm
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4

#from reportlab.rl_config import defaultPageSize


########## REGISTER FONTS

def fontpath(n):
    import mwlib.fonts
    fp = os.path.dirname(mwlib.fonts.__file__)
    return os.path.join(fp, n)

pdfmetrics.registerFont(TTFont('DejaVuSans',  fontpath('DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', fontpath('DejaVuSans-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-Italic', fontpath('DejaVuSans-Oblique.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSans-BoldItalic', fontpath('DejaVuSans-BoldOblique.ttf')))

addMapping('DejaVuSans', 0, 0, 'DejaVuSans')    #normal
addMapping('DejaVuSans', 0, 1, 'DejaVuSans-Italic')    #italic
addMapping('DejaVuSans', 1, 0, 'DejaVuSans-Bold')    #bold
addMapping('DejaVuSans', 1, 1, 'DejaVuSans-BoldItalic')    #italic and bold

pdfmetrics.registerFont(TTFont('DejaVuSansMono',  fontpath('DejaVuSansMono.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-Bold', fontpath('DejaVuSansMono-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-Italic', fontpath('DejaVuSansMono-Oblique.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono-BoldItalic', fontpath('DejaVuSansMono-BoldOblique.ttf')))

addMapping('DejaVuSansMono', 0, 0, 'DejaVuSansMono')    #normal
addMapping('DejaVuSansMono', 0, 1, 'DejaVuSansMono-Italic')    #italic
addMapping('DejaVuSansMono', 1, 0, 'DejaVuSansMono-Bold')    #bold
addMapping('DejaVuSansMono', 1, 1, 'DejaVuSansMono-BoldItalic')    #italic and bold

pdfmetrics.registerFont(TTFont('DejaVuSerif',  fontpath('DejaVuSerif.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-Bold', fontpath('DejaVuSerif-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-Italic', fontpath('DejaVuSerif-Italic.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSerif-BoldItalic', fontpath('DejaVuSerif-BoldItalic.ttf')))

addMapping('DejaVuSerif', 0, 0, 'DejaVuSerif')    #normal
addMapping('DejaVuSerif', 0, 1, 'DejaVuSerif-Italic')    #italic
addMapping('DejaVuSerif', 1, 0, 'DejaVuSerif-Bold')    #bold
addMapping('DejaVuSerif', 1, 1, 'DejaVuSerif-BoldItalic')    #italic and bold

from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light')) #CHS
#pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3')) #JPN
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium')) #KOR

standardFont =  "DejaVuSerif"
standardSansSerif = "DejaVuSans"
standardMonoFont = "DejaVuSansMono"
########## / REGISTER FONTS

### TABLE CONFIG

tableOverflowTolerance = 20  # max width overflow for tables    unit: pt 

########## FONT SWITCHER METHOD -- DONT CHANGE UNLESS YOU KNOW WHAT YOU ARE DOING

                
def filterText(txt, defaultFont=standardFont):   
    if isinstance(txt,list):
        txt = ''.join(txt)

    t = []   
    def getScript(letter):
        o = ord(letter)
        if o <= 592:  
            return defaultFont
        elif (o > 592 and o < 11904):
            return "DejaVuSans"
        elif (o >= 11904 and o <= 12255) \
            or (o >= 12272 and o <= 12287) \
            or (o >= 12352 and o <= 12591) \
            or (o >= 12704 and o <= 12735) \
            or (o >= 13312 and o <= 19903) \
            or (o >= 19968 and o <= 40895) \
            or (o >= 65104 and o <= 65135):
            return "STSong-Light" # --> Chinese Simplified
        elif (o >= 63744 and o <= 64255) \
            or (o >= 12592 and o <= 12687) \
            or (o >= 44032 and o <= 55215):
            return "HYSMyeongJo-Medium"  #--> Korean    
        return "DejaVuSans"

    lastscript = defaultFont  
    switchedFont = False
    for l in txt:
        if l in [" ",u"\u200B"]: # dont switch font for spacelike chars 
            t.append(l)
            continue
        _script = getScript(l)
        if _script != lastscript:
            if switchedFont:
                t.append('</font>')
            else:
                switchedFont = True
            t.append('<font name=%s>' % _script)
            lastscript = _script
        t.append(l)
    if switchedFont:
        t.append('</font>')
    return ''.join(t)

########## / FONT SWITCHER METHOD

######### PAGE CONFIGURATION

pageWidth, pageHeight = A4

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

pagefooter = 'All Articles originate from @WIKITITLE@  (@WIKIURL@)'
titlepagefooter = '@WIKITITLE@ book - Generated using the open source mwlib toolkit - <br/>see http://code.pediapress.com for more information'


######### /PAGE CONFIGURATION


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


class BaseStyle(PropertySet):
    defaults = {
        'fontName': standardFont,
        'fontSize': FONTSIZE,
        'leading': LEADING,
        'autoLeading':'max',
        'leftIndent':0,
        'rightIndent':0,
        'firstLineIndent':0,
        'alignment':TA_LEFT,
        'spaceBefore':3,
        'spaceAfter':0,
        'bulletFontName':standardFont,
        'bulletFontSize':FONTSIZE,
        'bulletIndent':0,
        'textColor': black,
        'backColor':None,
        'wordWrap':None,
        }
            
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
	
    if mode == 'list':
	style.spaceBefore = 0
	style.bulletIndent = LISTINDENT * max(0, indent_lvl-1)
	style.leftIndent = LISTINDENT * indent_lvl
    else:
	style.leftIndent = indent_lvl*LEFTINDENT
	
    return style

table_style = {'spaceBefore': 0.25*cm,
               'spaceAfter': 0.25*cm}


class BaseHeadingStyle(PropertySet):
    defaults = {
        'fontName': standardSansSerif,
        'fontSize': BIGFONTSIZE,
        'leading': LEADING,
        'autoLeading':'max',
        'leftIndent':0,
        'rightIndent':0,
        'firstLineIndent':0,
        'alignment':TA_LEFT,
        'spaceBefore':12,
        'spaceAfter':6,
        'bulletFontName':standardFont,
        'bulletFontSize':BIGFONTSIZE,
        'bulletIndent':0,
        'textColor': black,
        'backColor':None,
        'wordWrap':None,
        }

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
    

bookTitle_style = BaseHeadingStyle(name='bookTitle_style',
                                   fontSize=36,
                                   leading=40,
                                   spaceBefore=16
                                   )

bookSubTitle_style = BaseHeadingStyle(name='bookSubTitle_style',
                                     fontSize=24,
                                     leading=30,
                                     )

