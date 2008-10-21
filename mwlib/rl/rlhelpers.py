#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.


from pdfstyles import standardFont


breakChars = ['/', '.', '+', '-', '_', '?']
zws = '<font fontSize="1"> </font>'
def filterText(txt, defaultFont=standardFont, breakLong=False):  
    if isinstance(txt,list):
        txt = ''.join(txt)

    t = []   
    def getScript(letter):
        o = ord(letter)
        if o <= 592:  
            return defaultFont
        elif (o > 592 and o < 11904):
            return "DejaVuSans"
        elif (o >= 11904 and o <= 12591) \
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
        if breakLong and l in breakChars:
            t.append(l+zws)
            continue
        if l in [" ",u"\u200B"]: # dont switch font for spacelike chars 
            t.append(l)
            continue
        _script = getScript(l)
        if _script != lastscript:
            if switchedFont:
                t.append('</font>')
            else:
                switchedFont = True
            t.append('<font name="%s">' % _script)
            lastscript = _script
        t.append(l)
    if switchedFont:
        t.append('</font>')
    return ''.join(t)

