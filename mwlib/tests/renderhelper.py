#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import tempfile

from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import BaseDocTemplate, NextPageTemplate
from mwlib.rl.pagetemplates import WikiPage

from mwlib import uparser
from mwlib.rl.rlwriter import RlWriter
from mwlib.treecleaner import TreeCleaner
from mwlib import advtree

def renderElements(elements, filesuffix=None):
    """ takes a list of reportlab flowables and renders them to a test.pdf file"""
    margin = 2 * cm
    if filesuffix:
        fn = 'test_' + filesuffix + '.pdf'
    else:
        fn = 'test.pdf'       
    doc = BaseDocTemplate(fn, topMargin=margin, leftMargin=margin, rightMargin=margin, bottomMargin=margin)
    pt = WikiPage('Title', wikiurl='http://test.com', wikititle='Title')
    doc.addPageTemplates(pt)
    elements.insert(0, NextPageTemplate('Title'))   
    doc.build(elements)

def renderMW(txt, filesuffix=None):
    parseTree = uparser.parseString(title='Test', raw=txt)

    advtree.buildAdvancedTree(parseTree)
    tc = TreeCleaner(parseTree)
    tc.cleanAll()
    
    rw = RlWriter()
    rw.wikiTitle = 'testwiki'
    rw.tmpdir = tempfile.mkdtemp()
    elements = rw.write(parseTree)
    renderElements(elements, filesuffix)

