#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

import sys
import os
import re
import urllib
import traceback
import tempfile
import htmlentitydefs
import shutil
import inspect
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
    
from xml.sax.saxutils import escape as xmlescape
from PIL import Image as PilImage

from pygments import highlight
from pygments  import lexers
from rlsourceformatter import ReportlabFormatter

from mwlib.utils import all

def _check_reportlab():
    from reportlab.pdfbase.pdfdoc import PDFDictionary
    try:
        PDFDictionary.__getitem__
    except AttributeError:
        raise ImportError("you need to have the svn version of reportlab installed")
_check_reportlab()


#import reportlab
#reportlab.rl_config.platypus_link_underline = 1

#from reportlab.rl_config import defaultPageSize
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import BaseDocTemplate

from pagetemplates import PPDocTemplate

from reportlab.platypus.doctemplate import NextPageTemplate, NotAtTopPageBreak, PageTemplate
from reportlab.platypus.tables import Table
from reportlab.platypus.flowables import Spacer, HRFlowable, PageBreak, KeepTogether, Image
from reportlab.platypus.xpreformatted import XPreformatted
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
from reportlab.platypus.doctemplate import LayoutError
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

from customflowables import Figure, FiguresAndParagraphs

from pdfstyles import text_style, heading_style, table_style

from pdfstyles import pageMarginHor, pageMarginVert, standardSansSerif, standardMonoFont, standardFont
from pdfstyles import printWidth, printHeight, SMALLFONTSIZE, BIGFONTSIZE, FONTSIZE
from pdfstyles import tableOverflowTolerance
from pdfstyles import max_img_width, max_img_height, min_img_dpi, inline_img_dpi
from pdfstyles import maxCharsInSourceLine
import pdfstyles 
from mwlib import styleutils


import rltables
from pagetemplates import WikiPage, TitlePage, SimplePage

from mwlib import parser, log, uparser, metabook

from mwlib.rl.rlhelpers import filterText
log = log.Log('rlwriter')

try:
    import pyfribidi
    useFriBidi = True
except ImportError:
    #log.warning('pyfribidi not installed - rigth-to-left text not typeset correctly')
    useFriBidi = False

from mwlib.rl import debughelper
from mwlib.rl import version as rlwriterversion
from mwlib._version import version as  mwlibversion
try:
    from mwlib import _extversion
except ImportError:
    pass

from mwlib import advtree, writerbase
from mwlib.treecleaner import TreeCleaner

def flatten(x):
    result = []
    for el in x:
        if hasattr(el, "__iter__") and not isinstance(el, basestring):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result    

def isInline(objs):
    for obj in flatten(objs):
        if not (isinstance(obj, unicode) or isinstance(obj,str)):
            return False
    return True


def buildPara(txtList, style=text_style()):
    _txt = ''.join(txtList)
    _txt = _txt.strip()
    if len(_txt) > 0:
        try:
            return [Paragraph(_txt, style)]
        except:
            traceback.print_exc()
            log.warning('reportlab paragraph error:', repr(_txt))
            return []
    else:
        return []

def serializeStyleInfo(styleHash):
    res =  {}
    for k,v in styleHash.items():
        if isinstance(v,dict):
            for _k,_v in v.items():
                if isinstance(_v, basestring):
                    res[_k.lower()] = _v.lower() 
                else:
                    res[_k.lower()]= _v
        else:
            if isinstance(v, basestring):
                res[k.lower()] = v.lower() 
            else:
                res[k.lower()] = v
    return res

class ReportlabError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    

class RlWriter(object):

    def __init__(self, env=None, strict=False, debug=False, mathcache=None):
        self.env = env
        if self.env is not None:
            self.book = self.env.metabook
            self.imgDB = env.images
        else:
            self.imgDB = None
        self.strict = strict
        self.debug = debug
        self.level = 0  # level of article sections --> similar to html heading tag levels
        self.references = []
        self.listIndentation = 0  # nesting level of lists
        self.listCounterID = 1
        self.tmpImages = set()
        self.namedLinkCount = 1
        self.nestingLevel = 0       
        self.sectionTitle = False
        self.tablecount = 0
        self.paraIndentLevel = 0
        self.preMode = False
        self.refmode = False
        self.linkList = []
        self.disable_group_elements = False

        self.sourceCount = 0
        self.sourcemode = False
        self.currentColCount = 0
        self.currentArticle = None
        self.math_cache_dir = mathcache or os.environ.get('MWLIBRL_MATHCACHE')
        self.tmpdir = tempfile.mkdtemp()
        self.bookmarks = []
        self.colwidth = 0
        
    def ignore(self, obj):
        return []
        

    def groupElements(self, elements):
        """Group reportlab flowables into KeepTogether flowables
        to achieve meaningful pagebreaks

        @type elements: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """

        groupedElements = []
        group = []

        def isHeading(e):
            return isinstance(e, HRFlowable) or (hasattr(e, 'style') and  e.style.name.startswith('heading_style') )
        groupHeight = 0
        while elements:
            if not group:
                if isHeading(elements[0]):
                    group.append(elements.pop(0))
                else:
                    groupedElements.append(elements.pop(0))
            else:
                last = group[-1]
                if not isHeading(last):
                    try:
                        w,h = last.wrap(printWidth,printHeight)
                    except:
                        h = 0
                    groupHeight += h
                    if groupHeight > printHeight / 10 or isinstance(elements[0], NotAtTopPageBreak): # 10 % of pageHeight               
                        groupedElements.append(KeepTogether(group))
                        group = []
                        groupHeight = 0
                    else:
                        group.append(elements.pop(0))
                else:
                    group.append(elements.pop(0))
        if group:
            groupedElements.append(KeepTogether(group))

        return groupedElements
                                
    def write(self, obj, required=None):
        if not obj.visible:
            return []
        m = "write" + obj.__class__.__name__
        if not hasattr(self, m):
            log.error('unknown node:', repr(obj.__class__.__name__))
            if self.strict:
                raise 'Unkown Node: %s ' % obj.__class__.__name__
            return []
        m=getattr(self, m)
        return m(obj)

    def writeBook(self, bookParseTree, output, removedArticlesFile=None,
                  coverimage=None):
        
        #if self.debug:
        #    debughelper.showParseTree(sys.stdout, bookParseTree)

        advtree.buildAdvancedTree(bookParseTree)
        tc = TreeCleaner(bookParseTree, save_reports=self.debug)
        tc.cleanAll()
        
        if self.debug:
            debughelper.showParseTree(sys.stdout, bookParseTree)
            print "*"*30
            print "TREECLEANER REPORTS:"
            print "\n".join([repr(r) for r in tc.getReports()])
            
        try:
            self.renderBook(bookParseTree, output, coverimage=coverimage)
            log.info('###### RENDERING OK')
            if hasattr(self, 'tmpdir'):
                shutil.rmtree(self.tmpdir, ignore_errors=True)
            return
        except Exception, err:
            traceback.print_exc()
            log.error('###### renderBookFailed: %s' % err)               
            try:
                (ok_count, fail_count, fail_articles) = self.flagFailedArticles(bookParseTree, output)

                if self.strict:
                    raise 'Error rendering articles: %s' % repr(' | '.join(fail_articles))
                
                self.renderBook(bookParseTree, output, coverimage=coverimage)
                log.info('###### RENDERING OK - SOME ARTICLES WRITTEN IN PLAINTEXT')
                log.info('ok count: %d fail count: %d failed articles: %s' % (ok_count, fail_count, ' '.join(fail_articles)))
                if hasattr(self, 'tmpdir'):
                    shutil.rmtree(self.tmpdir, ignore_errors=True)
                return
            except Exception, err: # cant render book
                traceback.print_exc()
                log.error('###### RENDERING FAILED:')
                log.error(err)
                if hasattr(self, 'tmpdir'):
                    shutil.rmtree(self.tmpdir, ignore_errors=True)
                raise

    def renderBook(self, bookParseTree, output, coverimage=None):
        elements = []
        try:
            extversion = 'mwlib.ext version: %s' % str(_extversion.version)
        except NameError:
            extversion = 'mwlib.ext not used'
            
        version = 'mwlib version: %s , rlwriter version: %s, %s' % (rlwriterversion, mwlibversion, extversion)
        self.doc = PPDocTemplate(output,
                                 topMargin=pageMarginVert,
                                 leftMargin=pageMarginHor,
                                 rightMargin=pageMarginHor,
                                 bottomMargin=pageMarginVert,
                                 title=self.book.get('title'),
                                 keywords=version
        )

        self.output = output
        
        elements.extend(self.writeTitlePage(coverimage=coverimage))
        try:
            for e in bookParseTree.children:
                r = self.write(e)
                elements.extend(r)
        except:
            traceback.print_exc()
            raise

        if not self.disable_group_elements:
            elements = self.groupElements(elements)

        for license in self.env.get_licenses():
            elements.append(NotAtTopPageBreak())
            elements.extend(self.writeArticle(uparser.parseString(
                title=license['title'],
                raw=license['wikitext'],
                wikidb=self.env.wiki,
            )))

        self.doc.bookmarks = self.bookmarks
        #debughelper.dumpElements(elements)

        if not bookParseTree.getChildNodesByClass(parser.Article):
            pt = WikiPage('')
            self.doc.addPageTemplates(pt)
            elements.append(Paragraph(' ', text_style()))

        log.info("start rendering: %r" % output)
        try:
            self.doc.build(elements)
            return 0
        except LayoutError, err: # do special handling for reportlab splitting errors
            log.error('layout error:\n', err)
            if len(err.args):
                exception_txt = err.args[0]
                if isinstance(exception_txt, basestring) and exception_txt.find('Splitting') >-1:
                    self.disable_group_elements = True
            raise
        except Exception, err:
            log.error('error rendering document:\n', err)
            traceback.print_exc()
            raise
    

    def flagFailedArticles(self, bookParseTree, output):
        ok_count = 0
        fail_count = 0
        fail_articles = []
        for (i,node) in enumerate(bookParseTree):
            if isinstance(node, advtree.Article):
                elements = []
                elements.extend(self.writeArticle(node))
                try:
                    testdoc = BaseDocTemplate(output,
                        topMargin=pageMarginVert,
                        leftMargin=pageMarginHor,
                        rightMargin=pageMarginHor,
                        bottomMargin=pageMarginVert,
                        title=self.book.get('title'),
                    )
                    testdoc.addPageTemplates(WikiPage(title=node.caption))
                    testdoc.build(elements)
                    ok_count += 1
                except Exception, err:
                    log.error('article failed:' , repr(node.caption))
                    tr = traceback.format_exc()
                    log.error(tr)
                    node.renderFailed = True
                    fail_count += 1
                    fail_articles.append(repr(node.caption))
        return (ok_count, fail_count, fail_articles)
    
    def writeTitlePage(self, coverimage=None):       
        # FIXME: clean this up. there seems to be quite a bit of deprecated here
        title = self.book.get('title')
        subtitle =  self.book.get('subtitle')

        if not title:
            return []
        firstArticle=None
        firstArticleTitle = None
        for item in metabook.get_item_list(self.book):
            if item['type'] == 'article':
                firstArticle = xmlescape(item['title'])
                firstArticleTitle = xmlescape(item.get('displaytitle', item['title']))
                break
        kwargs = {}
        if firstArticle and self.env is not None:
            src = self.env.wiki.getSource(firstArticle)
            if src:
                if src.get('name'):
                    kwargs['wikititle'] = src['name']
                if src.get('url'):
                    kwargs['wikiurl'] = src['url']                    
        self.doc.addPageTemplates(TitlePage(cover=coverimage, **kwargs))
        elements = [Paragraph(self.renderText(title), text_style(mode='booktitle'))]
        if subtitle:
            elements.append(Paragraph(self.renderText(subtitle), text_style(mode='booksubtitle')))
        if not firstArticle:
            return elements
        self.doc.addPageTemplates(WikiPage(firstArticleTitle, **kwargs))
        elements.append(NextPageTemplate(firstArticleTitle.encode('utf-8')))
        elements.append(PageBreak())
        return elements

    def writeChapter(self, chapter):
        hr = HRFlowable(width="80%", spaceBefore=6, spaceAfter=0, color=colors.black, thickness=0.5)

        title = self.renderText(chapter.caption)
        chapter_para = Paragraph('%s<a name="%s"/>' % (title, len(self.bookmarks)), heading_style('chapter'))
        self.bookmarks.append((title, 'chapter'))
        return [NotAtTopPageBreak(),
                hr,
                chapter_para,
                hr]

    def writeSection(self, obj):
        lvl = getattr(obj, "level", 4)
        headingStyle = heading_style('section', lvl=lvl+1)
        self.sectionTitle = True
        headingTxt = ''.join(self.renderInline(obj.children[0])).strip()
        self.sectionTitle = False
        if lvl <= 2:
            anchor = '<a name="%d"/>' % len(self.bookmarks)
            self.bookmarks.append((obj.children[0].getAllDisplayText(), 'heading'))
        else:
            anchor = ''
        elements = [Paragraph('<font name="%s"><b>%s</b></font>%s' % (standardSansSerif, headingTxt, anchor), headingStyle)]
        
        self.level += 1
        elements.extend(self.renderMixed(obj.children[1:]))
        self.level -= 1
        return elements

    def renderFailedNode(self, node, infoText):
        txt = node.getAllDisplayText()
        txt = xmlescape(txt)
        elements = []
        elements.extend([Spacer(0, 1*cm), HRFlowable(width="100%", thickness=2), Spacer(0,0.5*cm)])
        elements.append(Paragraph(infoText, text_style(in_table=False)))
        elements.append(Spacer(0,0.5*cm))
        elements.append(Paragraph(txt, text_style(in_table=False)))
        elements.extend([Spacer(0, 0.5*cm), HRFlowable(width="100%", thickness=2), Spacer(0,1*cm)])
        return elements


    def writeArticle(self, article):
        self.references = [] 
        
        title = self.renderText(article.caption)
        log.info('writing article: %r' % title)
        elements = []
        pt = WikiPage(title)
        if hasattr(self, 'doc'): # doc is not present if tests are run
            self.doc.addPageTemplates(pt)
            elements.append(NextPageTemplate(title.encode('utf-8'))) # pagetemplate.id cant handle unicode
            if pdfstyles.pageBreakAfterArticle and isinstance(article.getPrevious(), advtree.Article): # if configured and preceded by an article
                elements.append(NotAtTopPageBreak())

        title = filterText(title, defaultFont=standardSansSerif, breakLong=True)
        self.currentArticle = repr(title)

        heading_para = Paragraph('<b>%s</b><a name="%d"/>' % (title, len(self.bookmarks)), heading_style('article'))        
        elements.append(heading_para)
        self.bookmarks.append((article.caption, 'article'))

        elements.append(HRFlowable(width='100%', hAlign='LEFT', thickness=1, spaceBefore=0, spaceAfter=10, color=colors.black))

        if not hasattr(article, 'renderFailed'): # if rendering of the whole book failed, failed articles are flagged
            elements.extend(self.renderMixed(article))
        else:
            articleFailText = '<strong>WARNING: Article could not be rendered - ouputting plain text.</strong><br/>Potential causes of the problem are: (a) a bug in the pdf-writer software (b) problematic Mediawiki markup (c) table is too wide'
            elements.extend(self.renderFailedNode(article, articleFailText))

        # check for non-flowables
        elements = [e for e in elements if not isinstance(e,basestring)]                
        elements = self.floatImages(elements)
        elements = self.tabularizeImages(elements)

        if self.references:
            elements.append(Paragraph('<b>External links</b>', heading_style('section', lvl=3)))
            elements.extend(self.writeReferenceList())

        if getattr(article,'url', None):
            elements.extend([Spacer(0, 0.5*cm),
                            Paragraph('Source: %s' % filterText(xmlescape(article.url), breakLong=True), text_style())])
        if getattr(article, 'authors', None):
            elements.append(Paragraph('Principle Authors: %s' % filterText(', '.join(article.authors)), text_style()))
            
        return elements
    
    def writeParagraph(self,obj):
        return self.renderMixed(obj)

    def floatImages(self, nodes):
        """Floating images are combined with paragraphs.
        This is achieved by sticking images and paragraphs
        into a FiguresAndParagraphs flowable

        @type nodes: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """

        def getMargins(align):
            if align=='right':
                return pdfstyles.img_margins_float_right
            elif align=='left':
                return pdfstyles.img_margins_float_left
            return pdfstyles.img_margins_float

        combinedNodes = []
        floatingNodes = []
        figures = []
        lastNode = None

        def gotSufficientFloats(figures, paras):
            hf = 0
            hp = 0
            maxImgWidth = 0
            for f in figures:
                # assume 40 chars per line for caption text
                hf += f.imgHeight + f.margin[0] + f.margin[2] + f.padding[0] + f.padding[2] + f.cs.leading * max(int(len(f.captionTxt) / 40), 1) 
                maxImgWidth = max(maxImgWidth, f.imgWidth)
            for p in paras:
                if isinstance(p,Paragraph):
                    w,h = p.wrap(printWidth - maxImgWidth, printHeight)
                    h += p.style.spaceBefore + p.style.spaceAfter
                    hp += h
            if hp > hf - 10:
                return True
            else:
                return False
        
        for n in nodes: # FIXME: somebody should clean up this mess
            if isinstance(lastNode, Figure) and isinstance(n, Figure):
                if n.align != 'center':
                    figures.append(n)
                else:
                    combinedNodes.extend(figures)
                    combinedNodes.extend([Spacer(0, 0.5*cm), n])
                    figures = []
            else :
                if not figures:
                    if isinstance(n, Figure) and n.align!='center' : # fixme: only float images that are not centered
                        figures.append(n)
                    else:
                        combinedNodes.append(n)
                else:
                    if (hasattr(n, 'style') and n.style.flowable == True  and not gotSufficientFloats(figures, floatingNodes)): #newpara
                        floatingNodes.append(n)
                    else:                      
                        if len(floatingNodes) > 0:
                            if hasattr(floatingNodes[-1], 'style') and floatingNodes[-1].style.name.startswith('heading_style') and floatingNodes[-1].style.flowable==True: # prevent floating headings before nonFloatables
                                noFloatNode = floatingNodes[-1]
                                floatingNodes = floatingNodes[:-1]
                            else:
                                noFloatNode = None
                            if len(floatingNodes)==0:
                                combinedNodes.extend(figures)
                                figures = []
                                combinedNodes.append(noFloatNode)
                                if isinstance(n,Figure) and n.align!='center': 
                                    figures.append(n)
                                else:
                                    combinedNodes.append(n)
                                lastnode=n
                                continue
                            fm = getMargins(figures[0].align or 'right')
                            combinedNodes.append(FiguresAndParagraphs(figures,floatingNodes, figure_margin=fm ))
                            if noFloatNode:
                                combinedNodes.append(noFloatNode)
                            figures = []
                            floatingNodes = []
                            if isinstance(n, Figure) and n.align!='center':
                                figures.append(n)
                            else:
                                combinedNodes.append(n)                                                       
                        else:
                            combinedNodes.extend(figures)
                            figures = []
            lastNode = n

        if figures and floatingNodes:
            fm = getMargins(figures[0].align or 'right')
            combinedNodes.append(FiguresAndParagraphs(figures,floatingNodes, figure_margin=fm ))
        else:
            combinedNodes.extend(figures + floatingNodes)
                                 
        return combinedNodes

    def tabularizeImages(self, nodes):
        """consecutive images that couldn't be combined with paragraphs
        are put into a 2 column table
        """
        finalNodes = []
        figures = []
        for n in nodes:
            if isinstance(n,Figure):
                figures.append(n)
            else:
                if len(figures)>1:
                    data = [  [figures[i],figures[i+1]]  for i in range(int(len(figures)/2))]
                    if len(figures) % 2 != 0:
                        data.append( [figures[-1],''] )                   
                    table = Table(data)
                    finalNodes.append(table)
                    figures = []
                else:
                    if figures:
                        finalNodes.append(figures[0])
                        figures = []
                    finalNodes.append(n)
        if len(figures)>1:
            data = [  [figures[i],figures[i+1]]  for i in range(int(len(figures)/2))]
            if len(figures) % 2 != 0:
                data.append( [figures[-1],''] )                   
            table = Table(data)
            finalNodes.append(table)                    
        else:
            finalNodes.extend(figures)
        return finalNodes

    def writePreFormatted(self, obj):
        self.preMode = True
        txt = []
        txt.extend(self.renderInline(obj))
        t = ''.join(txt)
        t = re.sub( u'<br */>', u'\n', t)
        self.preMode = False
        if not len(t):
            return []
        
        maxCharOnLine = max( [ len(line) for line in t.split("\n")])
        char_limit = max(1, int(maxCharsInSourceLine / (max(1, self.currentColCount))))
        if maxCharOnLine > char_limit:
            t = self.breakLongLines(t, char_limit)
        pre = XPreformatted(t, text_style(mode='preformatted', in_table=self.nestingLevel))
        # fixme: we could check if the preformatted fits on the page, if we reduce the fontsize
        #pre = XPreformatted(t, text_style(mode='preformatted', relsize='small', in_table=self.nestingLevel))
        return [pre]

        
    def writeNode(self,obj):
        return self.renderMixed(obj)

    def transformEntities(self,s):
        if not s:
            return None
        entities = re.findall('&([a-zA-Z]{1,10});', s)
        if entities:
            for e in entities:         
                codepoint = htmlentitydefs.name2codepoint.get(e, None)
                if codepoint:
                    s = s.replace('&'+e+';', unichr(codepoint))
        return s

    def renderText(self, txt):
        if useFriBidi:
            return xmlescape(pyfribidi.log2vis(txt, base_direction=pyfribidi.LTR))
        else:
            return xmlescape(txt)

    def writeText(self,obj):
        txt = obj.caption
        if useFriBidi:
            txt = pyfribidi.log2vis(txt, base_direction=pyfribidi.LTR)
                
        if not txt:
            return []
        if self.sourcemode:
            return [txt]
        if not self.preMode:
            txt = self.transformEntities(txt)
        txt = xmlescape(txt)
        if self.sectionTitle:
            return [filterText(txt, defaultFont=standardSansSerif, breakLong=True)]
        if self.preMode:
            return [filterText(txt, defaultFont=standardMonoFont)]
        return [filterText(txt)]

    def renderInline(self, node):
        txt = []
        for child in node.children:
            res = self.write(child)
            if isInline(res): 
                txt.extend(res)
            else:
                log.warning(node.__class__.__name__, ' contained block element: ', child.__class__.__name__)
        return txt


    def renderMixed(self, node, para_style=None, textPrefix=None):
        if not para_style:
            para_style = text_style(in_table=self.nestingLevel)
        txt = []
        if textPrefix:
            txt.append(textPrefix)
        items = []
       
        if isinstance(node, advtree.Node): # set node styles like text/bg colors, alignment
            text_color = styleutils.rgbColorFromNode(node)
            background_color = styleutils.rgbBgColorFromNode(node)           
            if text_color:
                para_style.textColor = text_color
            if background_color:
                para_style.backColor = background_color
            align = styleutils.alignmentFromNode(node)
            if align in ['right', 'center', 'justify']:
                align_map = {'right': TA_RIGHT,
                             'center': TA_CENTER,
                             'justify': TA_JUSTIFY,}
                para_style.alignment = align_map[align]
            
        for c in node:
            res = self.write(c)
            if isInline(res):
                txt.extend(res)
            else:
                items.extend(buildPara(txt, para_style)) 
                items.extend(res)
                txt = []
        if not len(items):
            return buildPara(txt, para_style)
        else:
            items.extend(buildPara(txt, para_style)) 
            return items      
   
    def renderChildren(self, n):
        items = []
        for c in n:
            items.extend(self.write(c))
        return items

    def renderInlineTag(self, node, tag, tag_attrs=''):
        txt = ['<%s %s>' % (tag, tag_attrs)]
        txt.extend(self.renderInline(node))
        txt.append('</%s>' % tag)
        return txt
        
    def writeEmphasized(self, n):
        return self.renderInlineTag(n, 'i')

    def writeStrong(self, n):
        return self.renderInlineTag(n, 'b')

    def writeDefinitionList(self, n):
        return self.renderChildren(n)
        

    def writeDefinitionTerm(self, n):
        txt = self.writeStrong(n)
        return [Paragraph(''.join(txt), text_style(in_table=self.nestingLevel))]

    def writeDefinitionDescription(self, n):
        return self.writeIndented(n)

    def writeIndented(self, n):
        self.paraIndentLevel += getattr(n, 'indentlevel', 1)
        items = self.renderMixed(n, para_style=text_style(indent_lvl=self.paraIndentLevel, in_table=self.nestingLevel))
        self.paraIndentLevel -= getattr(n, 'indentlevel', 1)
        return items
        
    def writeBlockquote(self, n):
        self.paraIndentLevel += 1
        items = self.renderMixed(n, text_style(mode='blockquote', in_table=self.nestingLevel))
        self.paraIndentLevel -= 1
        return items     
        
    def writeOverline(self, n):
        pass

    def writeUnderline(self, n):
        return self.renderInlineTag(n, 'u')

    writeInserted = writeUnderline

    def writeSub(self, n):
        return self.renderInlineTag(n, 'sub')

    def writeSup(self, n):
        return self.renderInlineTag(n, 'super')
        
    def writeSmall(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % SMALLFONTSIZE)

    def writeBig(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % BIGFONTSIZE)
        
    def writeCite(self, n):
        return self.writeDefinitionDescription(n)

    def writeStyle(self, s):
        txt = []
        txt.extend(self.renderInline(s))
        log.warning('unknown tag node', repr(s))
        return txt

    def writeLink(self,obj):
        """ Link nodes are intra wiki links
        """
        href = obj.url # obj.url is a utf-8 string
        
        if not href:
            log.warning('no link target specified')
            if not obj.children:
                return []         
        else:
            href = href[:href.find('"')] 
        
        if obj.children:
            txt = self.renderInline(obj)
            t = ''.join(txt).strip()
            if not href:
                return [t]
        else:
            txt = [href]
            txt = [getattr(obj, 'full_target', None) or obj.target]
            t = filterText(''.join(txt).strip()).encode('utf-8')
            t = unicode(urllib.unquote(t), 'utf-8')
        t = '<link href="%s">%s</link>' % ( xmlescape(href), t.strip())
        return [t]

    def writeLangLink(self, obj):
        if obj.colon:
            return self.writeLink(obj)
        return []

    writeArticleLink = writeLink
    writeNamespaceLink = writeLink
    writeInterwikiLink = writeLink
    writeSpecialLink = writeLink
    
    def renderURL(self, url):
        url = xmlescape(url)        
        zws = '<font fontSize="1"> </font>'
        url = url.replace("/",u'/%s' % zws).replace('&amp;', u'&amp;%s' % zws).replace('.','.%s' % zws).replace('+', '+%s' % zws)
        return url
    
    def writeURL(self, obj):       
        href = obj.caption
        if href is not None:
            href = href[:href.find('"')]
        display_text = self.renderURL(href)
        href = xmlescape(href)
        if (self.nestingLevel and len(href) > 30) and not self.refmode:
            return self.writeNamedURL(obj)
        
        txt = '<link href="%s"><font fontName="%s">%s</font></link>' % (href, standardMonoFont, display_text)
        return [txt]
    
    def writeNamedURL(self,obj):
        href = obj.caption.strip()
        if not self.refmode:
            i = parser.Item()
            i.children = [advtree.URL(href)]
            self.references.append(i)
        else: # we are writing a reference section. we therefore directly print URLs
            txt = self.renderInline(obj)
            txt.append(' <font size="%d">(%s)</font>' % (SMALLFONTSIZE, self.renderURL(href)))
            return [''.join(txt)]           
            
        if not obj.children:
            linktext = '[%s]' % len(self.references)
        else:
            linktext = self.renderInline(obj)
            linktext.append(' <super><font size="10">[%s]</font></super> ' % len(self.references))           
            linktext = ''.join(linktext).strip()
        return linktext
               

    def writeCategoryLink(self,obj): 
        txt = []
        if obj.colon: # CategoryLink inside the article
            if obj.children:
                txt.extend(self.renderInline(obj))
            else:
                txt.append(obj.target)
        else: # category of the article which is suppressed
            return []
        txt = ''.join(txt)
        if txt.find("|") > -1:
            txt = txt[:txt.find("|")] # category links sometimes seem to have more than one element. throw them away except the first one
        return [''.join(txt)] #FIXME use writelink to generate clickable-link
    
    
    def writeImageLink(self,obj):
        if obj.colon == True:
            items = []
            for node in obj.children:
                items.extend(self.write(node))
            return items

        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(obj.target, size=800) # FIXME: size configurable etc.
            if imgPath:
                imgPath = imgPath.encode('utf-8')
                self.tmpImages.add(imgPath)
        else:
            imgPath = ''
        if not imgPath:
            if obj.target == None:
                obj.target = ''
            log.warning('invalid image url (obj.target: %r)' % obj.target)            
            return []
        def sizeImage(w,h):
            if obj.isInline():
                scale = 1 / (inline_img_dpi / 2.54)
            else:
                scale = 1 / (min_img_dpi / 2.54)
            _w = w * scale
            _h = h * scale
            if _w > max_img_width or _h > max_img_height:
                scale = min( max_img_width/w, max_img_height/h)
                return (w*scale*cm, h*scale*cm)
            else:
                return (_w*cm, _h*cm)

        (w,h) = (obj.width or 0, obj.height or 0)

        try:
            img = PilImage.open(imgPath)
            if img.info.get('interlace',0) == 1:
                log.warning("got interlaced PNG which can't be handeled by PIL")
                return []
        except IOError:
            log.warning('img can not be opened by PIL')
            return []
        try:
            d = img.load()
        except:
            log.warning('img data can not be loaded - img corrupt: %r' % obj.target)
            return []
        
        (_w,_h) = img.size
        del img
        if _h == 0 or _w == 0:
            return []
        aspectRatio = _w/_h                           
           
        if w>0 and not h>0:
            h = w / aspectRatio
        elif h>0 and not w>0:
            w = aspectRatio / h
        elif w==0 and h==0:
            w, h = _w, _h

        (width, height) = sizeImage( w, h)
        if self.colwidth:
            if width > self.colwidth:
                height = height * self.colwidth/width
                width = self.colwidth

        align = obj.align
        if advtree.Center  in [ p.__class__ for p in obj.getParents()]:
            align = 'center'
            
        txt = []
        for node in obj.children:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning('imageLink contained block element: %s' % type(res))

        is_inline = obj.isInline()
        #from mwlib import imgutils #fixme: check if we need "improved" inline detection of images
        #is_inline = imgutils.isInline(obj)           
        if  is_inline: 
            txt = '<img src="%(src)s" width="%(width)fin" height="%(height)fin" valign="%(align)s"/>' % {
                'src':unicode(imgPath, 'utf-8'),
                'width':width/100,
                'height':height/100,
                'align':'bottom',
                }
            return txt
        captionTxt = ''.join(txt)         
        figure = Figure(imgPath,
                        captionTxt=captionTxt,
                        captionStyle=text_style('figure', in_table=self.nestingLevel),
                        imgWidth=width,
                        imgHeight=height,
                        margin=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm),
                        padding=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm),
                        align=align)
        return [figure]
        

    def writeGallery(self,obj):
        data = []
        row = []
        if obj.children:
            self.colwidth = (printWidth - 20)/2 #20pt margin
        for node in obj.children:
            if isinstance(node,parser.ImageLink):
                node.align='center' # this is a hack. otherwise writeImage thinks this is an inline image
                res = self.write(node)
            else:
                res = self.write(node)
                try:
                    res = buildPara(res)
                except:
                    res = Paragraph('',text_style(in_table=self.nestingLevel))
            if len(row) == 0:
                row.append(res)
            else:
                row.append(res)
                data.append(row)
                row = []
        if len(row) == 1:
            row.append(Paragraph('',text_style(in_table=self.nestingLevel)))
            data.append(row)
        table = Table(data)
        return [table]

    def breakLongLines(self, txt, char_limit):
       broken_source = []
       for line in txt.split('\n'):
           if len(line) < char_limit:
               broken_source.append(line)
           else:
               words = line.split()
               while words:
                   new_line = [words.pop(0)]                   
                   while words and (len(' '.join(new_line)) + len(words[0]) + 1) < char_limit:
                       new_line.append(words.pop(0))
                   broken_source.append(' '.join(new_line))               
       return '\n'.join(broken_source)
        

    def _writeSourceInSourceMode(self, n, src_lang, lexer):        
        sourceFormatter = ReportlabFormatter(font_size=FONTSIZE, font_name='DejaVuSansMono', background_color='#eeeeee', line_numbers=False)
        sourceFormatter.encoding = 'utf-8'
        source = ''.join(self.renderInline(n))
        maxCharOnLine = max( [ len(line) for line in source.split("\n")])
        char_limit = max(1, int(maxCharsInSourceLine / (max(1, self.currentColCount))))

        if maxCharOnLine > char_limit:
            source = self.breakLongLines(source, char_limit)

        txt = ''
        try:
            txt = highlight(source, lexer, sourceFormatter)           
            return [XPreformatted(txt, text_style(mode='source', in_table=self.nestingLevel))]            
        except:
            log.error('unsuitable lexer for source code language: %s - Lexer: %s' % (repr(src_lang), lexer.__class__.__name__))
            return []

    def writeSource(self, n):
        langMap = {'lisp': lexers.CommonLispLexer()} #custom Mapping between mw-markup source attrs to pygement lexers if get_lexer_by_name fails
        def getLexer(name):
            try: 
                return lexers.get_lexer_by_name(name)    
            except lexers.ClassNotFound: 
                lexer = langMap.get(name)
                if lexer:
                    return lexer
                else:
                    traceback.print_exc()
                    log.error('unknown source code language: %s' % repr(name))
                    return None
                
        src_lang = n.vlist.get('lang', '').lower()
        lexer = getLexer(src_lang)
        if lexer:
            self.sourcemode = True
            res = self._writeSourceInSourceMode(n, src_lang, lexer)
            self.sourcemode = False
            if res:
                return res
        return self.writePreFormatted(n)


    def writeCode(self, n):
        return self.writeTeletyped(n)

    def writeTeletyped(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs='fontName=%s' % standardMonoFont)
        
    def writeBreakingReturn(self, n):
        return ['<br />']

    def writeHorizontalRule(self, n):
        return [HRFlowable(width="100%", spaceBefore=3, spaceAfter=6, color=colors.black, thickness=0.25)]

    def writeIndex(self, n):
        log.warning('unhandled Index Node - rendering child nodes')
        return self.renderChildren(n) #fixme: handle index nodes properly

    def writeReference(self, n, isLink=False):
        i = parser.Item()
        i.children = [c for c in n.children]
        self.references.append(i)
        if isLink:
            return ['[%s]' % len(self.references)]
        else:
            return ['<super><font size="10">[%s]</font></super> ' % len(self.references)]
    
    def writeReferenceList(self, n=None):
        if self.references:                
            self.refmode = True
            refList = self.writeItemList(self.references, style="referencelist")
            self.references = []
            self.refmode = False
            return refList
        else:
            return []

    def writeCenter(self, n):
        return self.renderMixed(n, text_style(mode='center', in_table=self.nestingLevel))

    def writeDiv(self, n):
        return self.renderMixed(n, text_style(indent_lvl=self.paraIndentLevel, in_table=self.nestingLevel)) 

    def writeSpan(self, n):
        return self.renderInline(n)

    def writeStrike(self, n):
        return self.renderInlineTag(n, 'strike')

    writeDeleted = writeStrike

    def writeImageMap(self, n):
        if n.imagemap.imagelink:
            return self.write(n.imagemap.imagelink)
        else:
            return []
    
    def writeTagNode(self,t):
        return self.renderChildren(t) # FIXME

    
    def writeItem(self, item, style='itemize', counterID=None, resetCounter=False):
        txt = []
        items = []
        if resetCounter:
            seqReset = '<seqreset id="liCounter%d" base="0" />' % (counterID)
        else:
            seqReset = ''

        # we append a &nbsp; after the itemPrefix. this is because reportlab does not render them, if no text follows
        if style=='itemize':
            itemPrefix = u'<bullet>\u2022</bullet>&nbsp;' 
        elif style == 'referencelist':
            itemPrefix = '<bullet>%s[<seq id="liCounter%d" />]</bullet>&nbsp;' % (seqReset,counterID)
        elif style== 'enumerate':
            itemPrefix = '<bullet>%s<seq id="liCounter%d" />.</bullet>&nbsp;' % (seqReset,counterID)
        elif style.startswith('enumerateLetter'):
            itemPrefix = '<bullet>%s<seqformat id="liCounter%d" value="%s"/><seq id="liCounter%d" />.</bullet>&nbsp;' % (seqReset,counterID, style[-1], counterID)
        else:
            log.warn('invalid list style:', repr(style))
            itemPrefix = ''

        listIndent = max(0,(self.listIndentation + self.paraIndentLevel))
        para_style = text_style(mode='list', indent_lvl=listIndent, in_table=self.nestingLevel)
        if resetCounter: # first list item gets extra spaceBefore
            para_style.spaceBefore = text_style().spaceBefore
        items =  self.renderMixed(item, para_style=para_style, textPrefix=itemPrefix)
        return items
        

    def writeItemList(self, lst, numbered=False, style='itemize'):
        self.listIndentation += 1
        items = []
        if not style=='referencelist':
            if numbered or lst.numbered:
                if lst.numbered in ['a', 'A']:
                    style = "enumerateLetter%s" % lst.numbered
                else:
                    style = "enumerate"
            else:
                style="itemize"
        self.listCounterID += 1
        counterID = self.listCounterID
        for (i,node) in enumerate(lst):
            if isinstance(node,parser.Item): 
                resetCounter = i==0 # we have to manually reset sequence counters. due to w/h calcs with wrap reportlab gets confused
                item = self.writeItem(node, style=style, counterID=counterID, resetCounter=resetCounter)
                items.extend(item)
            else:
                log.warning('got %s node in itemlist - skipped' % node.__class__.__name__)
        self.listIndentation -= 1
        return items
           

    def writeCell(self, cell):          
        #colspan = cell.colspan
        #rowspan = cell.rowspan
        colspan = cell.attributes.get('colspan', 1)
        rowspan = cell.attributes.get('rowspan', 1)
        
        elements = self.renderMixed(cell, text_style(in_table=self.nestingLevel, text_align=cell.attributes.get('align')))
        
        return {'content':elements,
                'rowspan':rowspan,
                'colspan':colspan}

    def writeRow(self,row):
        r = []
        for cell in row:
            if cell.__class__ == advtree.Cell:
                r.append(self.writeCell(cell))
            else:
                log.warning('table row contains non-cell node, skipped:' % cell.__class__.__name__)
        return r


    def writeCaption(self,node): 
        txt = []
        for x in node.children:
            res = self.write(x)
            if isInline(res):
                txt.extend(res)
        return buildPara(txt, text_style(mode='center'))

    
    def writeTable(self, t):
        self.nestingLevel += 1
        elements = []
        data = []        
        maxCols = t.numcols
        t = rltables.reformatTable(t, maxCols)
        if t.__class__ == advtree.Table:
            maxCols = t.numcols

        self.currentColCount += maxCols
        
        # if a table contains only tables it is transformed to a list of the containing tables - that is handled below
        if t.__class__ != advtree.Table and all([c.__class__==advtree.Table for c in t]):
            tables = []
            self.nestingLevel -= 1
            self.currentColCount -= maxCols
            for c in t:
                tables.extend(self.writeTable(c))
            return tables        
        
        for r in t.children:
            if r.__class__ == advtree.Row:
                data.append(self.writeRow(r))
            elif r.__class__ == advtree.Caption:
                elements.extend(self.writeCaption(r))                
                t.removeChild(r) # this is slight a hack. we do this in order not to simplify cell-coloring code
                
        (data, span_styles) = rltables.checkSpans(data)
        self.currentColCount -= maxCols

        if not data:
            return []
        
        colwidthList = rltables.getColWidths(data, nestingLevel=self.nestingLevel)
        data = rltables.splitCellContent(data)

        has_data = False
        for row in data:
            if row:
                has_data = True
                break
        if not has_data:
            return []
        
        table = Table(data, colWidths=colwidthList, splitByRow=1)
        
        styles = rltables.style(t.attributes)
        table.setStyle(styles)
        table.setStyle(span_styles)
    
        table.setStyle([('LEFTPADDING', (0,0),(-1,-1), 3),
                        ('RIGHTPADDING', (0,0),(-1,-1), 3),
                        ])
        table.setStyle(rltables.tableBgStyle(t))
                       
        w,h = table.wrap(printWidth, printHeight)
        if maxCols == 1 and h > printHeight: # big tables with only 1 col are removed - the content is kept
            flatData = [cell for cell in flatten(data) if not isinstance(cell, str)]            
            self.nestingLevel -= 1
            return flatData 
       
        if table_style.get('spaceBefore', 0) > 0:
            elements.append(Spacer(0, table_style['spaceBefore']))
        elements.append(table)
        if table_style.get('spaceAfter', 0) > 0:
            elements.append(Spacer(0, table_style['spaceAfter']))

        (renderingOk, renderedTable) = self.renderTable(table, t)
        self.nestingLevel -= 1
        if not renderingOk:
            return []
        if renderingOk and renderedTable:
            return renderedTable
        return elements
    
    def renderTable(self, table, t_node):
        """
        method that checks if a table can be rendered by reportlab. this is done, b/c large tables cause problems.
        if a large table is detected, it is rendered on a larger canvas and - on success - embedded as an
        scaled down image.
        """
        if self.debug:
            log.info("testrendering:", os.path.join(self.tmpdir, 'table%d.pdf' % self.tablecount))
        fn = os.path.join(self.tmpdir, 'table%d.pdf' % self.tablecount)
        self.tablecount += 1

        doc = BaseDocTemplate(fn)
        doc.addPageTemplates(SimplePage(pageSize=A4))
        try:
            w,h=table.wrap(printWidth, printHeight)
            if self.debug:
                log.info("tablesize:(%f, %f) pagesize:(%f, %f) tableOverflowTolerance: %f" %(w, h, printWidth, printHeight, tableOverflowTolerance))
            if w > (printWidth + tableOverflowTolerance):
                log.warning('table test rendering: too wide - printwidth: %f (tolerance %f) tablewidth: %f' % (printWidth, tableOverflowTolerance, w))
                raise LayoutError
            if self.nestingLevel > 1 and h > printHeight:
                log.warning('nested table too high')
                raise LayoutError                
            doc.build([table])
            del doc
            if self.debug:
                log.info('table test rendering: ok')
            return (True, None)
        except LayoutError:
            log.warning('table test rendering: reportlab LayoutError')

        log.info('trying safe table rendering')
                   
        fail = True
        pw = printWidth
        ph = printHeight
        ar = ph/pw
        run = 1
        while fail:
            pw += 20
            ph += 20*ar
            if pw > printWidth * 2:
                break
            try:
                log.info('safe render run:', run)
                doc = BaseDocTemplate(fn)
                doc.addPageTemplates(SimplePage(pageSize=(pw,ph)))
                doc.build([table])
                fail = False
                del doc
            except:
                log.info('safe rendering fail for width:', pw)

        tableFailText = '<strong>WARNING: Table could not be rendered - ouputting plain text.</strong><br/>Potential causes of the problem are: (a) table contains a cell with content that does not fit on a single page (b) nested tables (c) table is too wide'

        if fail:
            log.warning('error rendering table - outputting plain text')
            elements = self.renderFailedNode(t_node, tableFailText)
            return (True, elements)

        imgname = fn +'.png'
        resolutions = [300, 200, 100, 50]
        convertFail = 1
        # conversion of large tables fails for high resolutions - try converting from high to low resolutions 
        while convertFail and resolutions:
            res = resolutions.pop(0)
            convertFail = os.system('convert  -density %d %s %s' % (res, fn, imgname))

        if convertFail:
            elements = self.renderFailedNode(t_node, tableFailText)
            log.warning('error rendering table - (pdf->png failed) outputting plain text')
            return (True, elements)

        images = []
        if os.path.exists(imgname):
            images = [Image(imgname, width=printWidth*0.90, height=printHeight*0.90)]
        else: # if the table spans multiple pages, convert generates multiple images
            import glob
            imageFns = glob.glob(fn + '-*.png')
            for imageFn in imageFns:
                images.append(Image(imageFn, width=printWidth*0.90, height=printHeight*0.90))
            
        return (True, images)
            
    def writeMath(self, node):
        source = re.compile(u'\n+').sub(u'\n', node.caption.strip()) # remove multiple newlines, as this could break the mathRenderer
        if not len(source):
            return []
        imgpath = None
        if self.math_cache_dir:            
            _md5 = md5()
            _md5.update(source)                
            math_id = _md5.hexdigest()
            imgpath = os.path.join(self.math_cache_dir, '%s.png' % math_id)
            if not os.path.exists(imgpath):
                imgpath = None

        if not imgpath:
            imgpath = writerbase.renderMath(source, output_path=self.tmpdir, output_mode='png', render_engine='texvc')
            if not imgpath:
                return []
            if self.math_cache_dir:
                new_path = os.path.join(self.math_cache_dir, '%s.png' % math_id)
                shutil.move(imgpath, new_path)
                imgpath = new_path
                
        img = PilImage.open(imgpath)
        if self.debug:
            log.info("math png at:", imgpath)
        w,h = img.size
        del img

        if self.nestingLevel: # scale down math-formulas in tables
            w = w * SMALLFONTSIZE/FONTSIZE
            h = h * SMALLFONTSIZE/FONTSIZE
            
        density = 120 # resolution in dpi in which math images are rendered by latex
        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 32px. UPDATE: is now 17 
        #imgAlign = '%fin' % (- (h - 32) / (2 * density))
        imgAlign = '%fin' % (- (h - 15) / (2 * density))
        #the non-breaking-space is needed to force whitespace after the formula
        return ' <img src="%(path)s" width="%(width)fin" height="%(height)fin" valign="%(valign)s" />&nbsp; ' % {
            'path': imgpath.encode(sys.getfilesystemencoding()),
            'width': w/density,
            'height': h/density,
            'valign': imgAlign, }
    
    writeTimeline = ignore
    writeControl = ignore

    writeVar = writeEmphasized


def writer(env, output, status_callback=None, coverimage=None, strict=False, debug=False, mathcache=None):
    r = RlWriter(env, strict=strict, debug=debug, mathcache=mathcache)
    if coverimage is None and env.configparser.has_section('pdf'):
        coverimage = env.configparser.get('pdf', 'coverimage', None)
    book = writerbase.build_book(env, status_callback=status_callback, progress_range=(10, 70))
    if status_callback is not None:
        status_callback(status='rendering')
    r.writeBook(book, output=output, coverimage=coverimage)

writer.description = 'PDF documents (using ReportLab)'
writer.content_type = 'application/pdf'
writer.file_extension = 'pdf'
writer.options = {
    'coverimage': {
        'param': 'FILENAME',
        'help': 'filename of an image for the cover page',       
    },
    'strict': {
        'help':'raise exception if errors occur', 
    },
    'debug': {
        'help':'debugging mode is more verbose',
    },
    'mathcache': {
        'param': 'DIRNAME',
        'help': 'directory of cached math images',
    }
}
