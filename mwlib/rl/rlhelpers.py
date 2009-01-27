#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.


import os
from mwlib.fontswitcher import FontSwitcher
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


class RLFontSwitcher(FontSwitcher):

    def __init__(self):
        FontSwitcher.__init__(self)
        self.font_path = None
        self.default_fontpath = None
        self.force_font = None
        
    def registerFontDefinitionList(self, font_list):
        for font in font_list:
            if not font['name']:
                continue
            self.registerFont(font['name'], code_points=font.get('code_points'))
                     
    def fakeHyphenate(self, font_list):
        breakChars = ['/', '.', '+', '-', '_', '?']
        zws = '<font fontSize="1"> </font>'        
        res = []
        for txt, font in font_list:
            for breakChar in breakChars:
                txt = txt.replace(breakChar, breakChar + zws)
            res.append((txt, font))
        return res
    
    def fontifyText(self, txt, defaultFont='', breakLong=False):
        if self.force_font:
            return '<font name="%s">%s</font>' % (self.force_font, txt)
        font_list = self.getFontList(txt)
        if breakLong:
            font_list = self.fakeHyphenate(font_list)

        res = []
        for txt, font in font_list:
            if font != self.default_font:
                res.append('<font name="%s">%s</font>' % (font, txt))
            else:
                res.append(txt)

        return ''.join(res)
        

    def registerReportlabFonts(self, font_list):
        font_variants = ['', 'bold', 'italic', 'bolditalic']
        for font in font_list:
            if not font.get('name'):
                continue
            if font.get('type') == 'ttf':
                for (i, font_variant) in enumerate(font_variants):
                    if i == len(font.get('file_names')):
                        break
                    full_font_name = font['name'] + font_variant
                    pdfmetrics.registerFont(TTFont(full_font_name,  os.path.join(self.default_fontpath, font.get('file_names')[i])))
                    italic = font_variant in ['italic', 'bolditalic']
                    bold = font_variant in ['bold', 'bolditalic']
                    addMapping(font['name'], bold, italic, full_font_name)
            elif font.get('type') == 'cid':
                pdfmetrics.registerFont(UnicodeCIDFont(font['name']))
