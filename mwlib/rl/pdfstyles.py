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
STANDARDFONTSIZE = 10
SMALLFONTSIZE = 8
BIGFONTSIZE = 12
########## / REGISTER FONTS


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

    lastscript = standardFont  
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
leftIndent = 25 # indentation of paragraphs...
rightIndent = 25 # indentation of paragraphs...
listIndent = 12 # indentation of lists per level

showPageHeader = True 
showPageFooter = True
showTitlePageFooter = True

pagefooter = 'All Articles originate from @WIKITITLE@  (@WIKIURL@)'
titlepagefooter = '@WIKITITLE@ book - Generated using the open source mwlib toolkit - <br/>see http://code.pediapress.com for more information'


######### /PAGE CONFIGURATION


######### TEXT CONFIGURATION

class BaseStyle(PropertySet):
    defaults = {
        'fontName': standardFont,
        'fontSize': STANDARDFONTSIZE,
        'leading': 15,
        'autoLeading':'max',
        'leftIndent':0,
        'rightIndent':0,
        'firstLineIndent':0,
        'alignment':TA_LEFT,
        'spaceBefore':3,
        'spaceAfter':0,
        'bulletFontName':standardFont,
        'bulletFontSize':10,
        'bulletIndent':0,
        'textColor': black,
        'backColor':None,
        'wordWrap':None,
        }
        
class BaseHeadingStyle(PropertySet):
    defaults = {
        'fontName': standardSansSerif,
        'fontSize': 12,
        'leading': 15,
        'autoLeading':'max',
        'leftIndent':0,
        'rightIndent':0,
        'firstLineIndent':0,
        'alignment':TA_CENTER,
        'spaceBefore':12,
        'spaceAfter':6,
        'bulletFontName':standardFont,
        'bulletFontSize':12,
        'bulletIndent':0,
        'textColor': black,
        'backColor':None,
        'wordWrap':None,
        }
    

def p_indent_style(indent):
    return BaseStyle(name='p_indent_%d' % indent,
                     #alignment=TA_JUSTIFY,
                     leftIndent=indent*leftIndent
                     )

p_style = BaseStyle(name='p_style',
                    #alignment=TA_JUSTIFY,
                    )

p_blockquote_style = BaseStyle(name='p_blockquote_style',
                               leftIndent = leftIndent,
                               rightIndent = rightIndent,
                    )


p_center_style = BaseStyle(name='p_style',
                           alignment=TA_CENTER,
                    )          
dl_style = BaseStyle(name='dl_style',
                     #alignment=TA_JUSTIFY,
                     spaceBefore = 8,
                     )
table_p_style = BaseStyle(name='table_p_style',
                          #alignment=TA_JUSTIFY,
                          )    

table_p_style_small = BaseStyle(name='table_p_style_small',
                                #alignment=TA_JUSTIFY,
                                fontSize=8,
                                leading=10,
                                )

footer_style = BaseStyle(name='footer_style',
                         fontSize=8,
                         leading=8,
                         alignment=TA_CENTER,
                         )

figure_caption_style = BaseStyle(name='figure_caption',
                                 fontSize=8,
                                 leading=11,
                                 spaceBefore = 4,
                                 alignment = TA_CENTER,
                                 )             
def li_style(lvl):
    return BaseStyle(name='li_style_%d' % lvl,
                     leftIndent = listIndent * lvl,
                     bulletIndent = listIndent * max(0, lvl-1),
                     spaceBefore = 0,
                     #alignment=TA_JUSTIFY,
                     )

reference_style = BaseStyle(name='reference_style',
                            #leftIndent=leftIndent, 
                            )          

pre_style = BaseStyle(name='pre_style',
                           fontName=standardMonoFont,
                           leftIndent=15,
                           spaceAfter=3,
                           )

pre_style_small =  BaseStyle(name='pre_style',
                           fontName=standardMonoFont,
                           fontSize=8,
                           leading=11,
                           leftIndent=15,
                           spaceAfter=3,
                           )

license_title_style = BaseStyle(name='license_title_style',
                                fontName = standardMonoFont,
                                fontSize = 14,
                                leading = 16,
                                spaceAfter = 10,                                
                                )

license_heading_style = BaseStyle(name='license_heading_style',
                                  fontName = standardMonoFont,
                                  fontSize = 12,
                                  leading = 14,
                                  spaceAfter = 8,
                                  spaceBefore = 8,
                                  )

license_text_style = BaseStyle(name='license_text_style',
                               fontName = standardMonoFont,
                               fontSize = 8,
                               leading = 10,
                               spaceAfter = 4,
                               alignment = TA_JUSTIFY,
                               )

license_li_style = BaseStyle(name='license_text_style',
                             fontName = standardMonoFont,
                             fontSize = 8,
                             leading = 10,
                             spaceAfter = 4,
                             leftIndent = 15,
                             bulletFontName = standardMonoFont,
                             bulletFontSize = 8,
                             alignment = TA_JUSTIFY,
                             )                                


chapter_style = BaseHeadingStyle(name='chapter_style',
                                 fontSize=26,
                                 leading=30,
                                 )

articleTitle_style = BaseHeadingStyle(name='articleTitle_style',
                                      fontSize=22,
                                      leading=26,
                                      spaceBefore = 20,
                                      spaceAfter = 2,
                                      alignment=TA_LEFT,
                                      )

h1_style = BaseHeadingStyle(name='h1_style',
                            fontSize=18,
                            leading=22,
                            spaceBefore=20,
                            alignment=TA_LEFT,
                     )

h2_style = BaseHeadingStyle(name='h2_style',
                            fontSize=16,
                            leading=19,
                            spaceAfter=0,
                            spaceBefore=18,
                            alignment=TA_LEFT,
                           )

h3_style = BaseHeadingStyle(name='h3_style',
                            fontSize=14,
                            leading=16,
                            spaceBefore=16,
                            alignment=TA_LEFT,
                            )

h4_style =BaseHeadingStyle(name='h4_style',
                           fontSize=12,
                           leading=14,
                           spaceBefore=14,
                           alignment=TA_LEFT,
                           )

hr_style= BaseStyle(name='hr_style',
                         spaceBefore=0,
                         spaceAfter=8,
                         )

heading_styles = [h1_style, h2_style, h3_style, h4_style]


table_style = {'spaceBefore': 0.25*cm,
               'spaceAfter': 0.25*cm}


bookTitle_style = BaseHeadingStyle(name='bookTitle_style',
                                   fontSize=36,
                                   leading=40,
                                   spaceBefore=16
                                   )

bookSubTitle_style = BaseHeadingStyle(name='bookSubTitle_style',
                                     fontSize=24,
                                     leading=30,
                                     )

bookAuthor_style = BaseHeadingStyle(name='bookAuthor_style',
                                    fontSize=18,
                                    leading=22,
                                    )




