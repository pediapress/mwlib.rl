#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import subprocess
import shutil

import mwlib.ext
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.lib.styles import ParagraphStyle

class TocRenderer(object):

    def __init__(self):
        pass

    def build(self, pdfpath, toc_entries):
        outpath = os.path.dirname(pdfpath)
        tocpath = os.path.join(outpath, 'toc.pdf')
        finalpath = os.path.join(outpath, 'final.pdf')
        self.renderToc(tocpath, toc_entries)
        self.combinePdfs(pdfpath, tocpath, finalpath)
        
    def renderToc(self, tocpath, toc_entries):
        doc = SimpleDocTemplate(tocpath)
        elements = []
        for lvl, txt, page_num in toc_entries:
            p = Paragraph('%s - %d' % (txt, page_num), ParagraphStyle('Normal'))
            elements.append(p)
        doc.build(elements)

    def combinePdfs(self, pdfpath, tocpath, finalpath):

        cmd =  ['pdftk',
                'A=%s' % pdfpath,
                'B=%s' % tocpath,
                'cat', 'A1', 'B', 'A2-end',
                'output','%s' % finalpath,
                ]
        retcode = subprocess.call(cmd)
        if retcode != 0:
            raise Exception('pdf and toc could not be combined')
        shutil.move(finalpath, pdfpath)
