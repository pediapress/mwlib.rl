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

from xml.sax.saxutils import escape as xmlescape
from PIL import Image as PilImage

from pygments import highlight
#from pygments.lexers import JavaLexer, XmlLexer, CppLexer, PythonLexer, RubyLexer, TextLexer
from pygments  import lexers
from pygments.formatters import ImageFormatter

from mwlib.utils import all

def _check_reportlab():
    from reportlab.pdfbase.pdfdoc import PDFDictionary
    try:
        PDFDictionary.__getitem__
    except AttributeError:
        raise ImportError("you need to have the svn version of reportlab installed")
_check_reportlab()

#from reportlab.rl_config import defaultPageSize
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import BaseDocTemplate, NextPageTemplate, NotAtTopPageBreak
from reportlab.platypus.tables import Table
from reportlab.platypus.flowables import Spacer, HRFlowable, PageBreak, KeepTogether, Image
from reportlab.platypus.xpreformatted import XPreformatted
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
from reportlab.platypus.doctemplate import LayoutError
from reportlab.lib.pagesizes import A4

from customflowables import Figure, FiguresAndParagraphs

from pdfstyles import text_style, heading_style, table_style
from pdfstyles import bookTitle_style, bookSubTitle_style

from pdfstyles import pageMarginHor, pageMarginVert, standardSansSerif, standardMonoFont, standardFont
from pdfstyles import printWidth, printHeight, SMALLFONTSIZE, BIGFONTSIZE, FONTSIZE
from pdfstyles import tableOverflowTolerance
from pdfstyles import max_img_width, max_img_height, min_img_dpi, inline_img_dpi

import rltables
from pagetemplates import WikiPage, TitlePage, SimplePage

from mwlib import parser, log, uparser

log = log.Log('rlwriter')

from mwlib.rl import debughelper
from mwlib.rl.rltreecleaner import buildAdvancedTree
from mwlib.rl import version as rlwriterversion
from mwlib._version import version as  mwlibversion
from mwlib import advtree

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


########## FONT SWITCHER METHOD -- DONT CHANGE UNLESS YOU KNOW WHAT YOU ARE DOING
breakChars = ['/', '.', '+', '-']
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

########## / FONT SWITCHER METHOD

class ReportlabError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    

class RlWriter(object):

    def __init__(self, env=None):
        self.env = env
        if self.env is not None:
            self.book = self.env.metabook
            self.imgDB = env.images
        else:
            self.imgDB = None
        self.level = 0  # level of article sections --> similar to html heading tag levels
        self.references = []
        self.listIndentation = 0  # nesting level of lists
        self.listCounterID = 1
        self.baseUrl = ''
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
                    if groupHeight > printHeight / 10: # 10 % of pageHeight               
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
            
    def cleanUp(self):
        for fn in self.tmpImages:
            try:
                os.unlink(fn)
            except:
                log.warning('could not delete temporary image: %s' % fn)

    def displayNode(self, n):
        """
        check if a node has styling info, that prevents rendering of item
        """
        if not hasattr(n, 'vlist'):
            return True
        style = n.vlist.get('style',None)
        if style:
            display = style.get('display', '').lower()
            if display == 'none':
                return False
        return True
                    
    def write(self, obj, required=None):
        if not self.displayNode(obj):
            return []
        m = "write" + obj.__class__.__name__
        if not hasattr(self, m):
            log.error('unknown node:', repr(obj.__class__.__name__))
            return []
        m=getattr(self, m)
        return m(obj)

    def writeBook(self, bookParseTree, output, removedArticlesFile=None,
                  coverimage=None):
        
        #debughelper.showParseTree(sys.stdout, bookParseTree)
        buildAdvancedTree(bookParseTree)
        #debughelper.showParseTree(sys.stdout, bookParseTree)
               
        try:
            self.renderBook(bookParseTree, output, coverimage=coverimage)
            log.info('###### RENDERING OK')
            shutil.rmtree(self.tmpdir)
            return 0
        except Exception, err:
            traceback.print_exc()
            log.error('###### renderBookFailed: %s' % err)
            try:
                self.flagFailedArticles(bookParseTree, output)
                self.renderBook(bookParseTree, output, coverimage=coverimage)
                log.info('###### RENDERING OK - SOME ARTICLES WRITTEN IN PLAINTEXT')
                shutil.rmtree(self.tmpdir)
                return 0
            except Exception, err: # cant render book
                traceback.print_exc()
                log.error('###### RENDERING FAILED:')
                log.error(err)
                shutil.rmtree(self.tmpdir)
                raise

    def renderBook(self, bookParseTree, output, coverimage=None):
        source = self.env.get_source()
        self.baseUrl = source['url']
        self.wikiTitle = source['name']
        elements = []
        version = 'mwlib version: %s , rlwriter version: %s' % (rlwriterversion, mwlibversion)
        self.doc = BaseDocTemplate(output, topMargin=pageMarginVert, leftMargin=pageMarginHor, rightMargin=pageMarginHor, bottomMargin=pageMarginVert,title=getattr(self.book, 'title', None), keywords=version)

        self.output = output
        self.tmpdir = tempfile.mkdtemp()

        elements.extend(self.writeTitlePage(wikititle=self.wikiTitle, coverimage=coverimage))
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
        
        if not bookParseTree.getChildNodesByClass(parser.Article):
            pt = WikiPage('', wikiurl=self.baseUrl, wikititle=self.wikiTitle)
            self.doc.addPageTemplates(pt)
            elements.append(Paragraph(' ', text_style()))
                            
        log.info("start rendering: %r" % output)
        try:
            self.doc.build(elements)
            return 0
        except Exception, err:
            log.error('error:\n', err)
            if len(err.args):
                exception_txt = err.args[0]
                if exception_txt.find('Splitting') >-1:
                    self.disable_group_elements = True
            traceback.print_exc()
            raise
    

    def flagFailedArticles(self, bookParseTree, output):
        for (i,node) in enumerate(bookParseTree):
            if isinstance(node, advtree.Article):
                elements = []
                elements.extend(self.writeArticle(node))
                try:
                    testdoc = BaseDocTemplate(output, topMargin=pageMarginVert, leftMargin=pageMarginHor, rightMargin=pageMarginHor, bottomMargin=pageMarginVert, title=getattr(self.book, 'title', None))
                    testdoc.addPageTemplates(WikiPage(title=node.caption, wikiurl=self.baseUrl, wikititle=self.wikiTitle))
                    testdoc.build(elements)
                except Exception, err:
                    log.error('article failed:' , node.caption)
                    tr = traceback.format_exc()
                    log.error(tr)
                    node.renderFailed = True

    
    def writeTitlePage(self, wikititle=None, coverimage=None):       
        title = getattr(self.book, 'title', None)
        subtitle =  getattr(self.book, 'subtitle', None)

        if not title:
            return []
        self.doc.addPageTemplates(TitlePage(wikititle=wikititle, cover=coverimage))
        elements = [Paragraph(xmlescape(title), bookTitle_style)]
        if subtitle:
            elements.append(Paragraph(xmlescape(subtitle), bookSubTitle_style))
        firstArticle=None
        for item in self.book.getItems():
            if item['type'] == 'article':
                firstArticle = item['title']
                break
        if not firstArticle:
            return elements
        self.doc.addPageTemplates(WikiPage(firstArticle,wikiurl=self.baseUrl, wikititle=self.wikiTitle))
        elements.append(NextPageTemplate(firstArticle.encode('utf-8')))
        elements.append(PageBreak())
        return elements

    def writeChapter(self, chapter):
        hr = HRFlowable(width="80%", spaceBefore=6, spaceAfter=0, color=colors.black, thickness=0.5)
        return [NotAtTopPageBreak(),
                hr,
                Paragraph(xmlescape(chapter.caption), heading_style('chapter')),
                hr]

    def writeSection(self,obj):
        lvl = getattr(obj, "level", 4)
        headingStyle = heading_style('section', lvl=lvl+1)
        self.sectionTitle = True
        headingTxt = ''.join(self.write(obj.children[0])).strip()
        self.sectionTitle = False
        elements = [Paragraph('<font name="%s"><b>%s</b></font>' % (standardSansSerif, headingTxt), headingStyle)]
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


    def writeArticle(self,article):
        self.references = [] 
        
        title = xmlescape(article.caption)
        log.info('writing article: %r' % title)
        title = filterText(title, defaultFont=standardSansSerif, breakLong=True)
        elements = []
        pt = WikiPage(title, wikiurl=self.baseUrl, wikititle=self.wikiTitle)
        if hasattr(self, 'doc'): # doc is not present if tests are run
            self.doc.addPageTemplates(pt)
            elements.append(NextPageTemplate(title.encode('utf-8'))) # pagetemplate.id cant handle unicode
        elements.append(Paragraph("<b>%s</b>" % title, heading_style('article')))
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
                return (0, 0, 0.35*cm, 0.2*cm)
            elif align=='left':
                return (0, 0.2*cm, 0.35*cm, 0)
            return (0.2*cm,0.2*cm,0.2*cm,0.2*cm)

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
                figures.append(n)
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
        t = re.sub( "<br */>", "\n", t.strip())
        self.preMode = False
        if len(t):
            # fixme: if any line is too long, we decrease fontsize to try to fit preformatted text on the page
            # PreformattedBox flowable should do intelligent and visible splitting when necessary
            # also decrease text size if we are inside a table
            maxCharOnLine = max( [ len(line) for line in t.split("\n")])
            if maxCharOnLine > 76 or self.nestingLevel:
                pre = XPreformatted(t, text_style(mode='preformatted', relsize='small', in_table=self.nestingLevel))
            else:
                pre = XPreformatted(t, text_style(mode='preformatted', in_table=self.nestingLevel))
            return [pre]

        else:
            return []
        
    def writeNode(self,obj):
        txt = []
        items = []
        for node in obj:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                items.extend(buildPara(txt, text_style(in_table=self.nestingLevel)))
                items.extend(res)
                txt = []
        if not len(items):
            return txt
        else:
            items.extend(buildPara(txt,text_style(in_table=self.nestingLevel))) #filter
        return items


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
        
    def writeText(self,obj):
        txt = obj.caption

        if not txt:
            return []
        if not self.preMode or self.sourcemode:
            txt = self.transformEntities(txt)
        if not self.sourcemode:
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
        self.paraIndentLevel += n.indentlevel
        items = self.renderMixed(n, para_style=text_style(indent_lvl=self.paraIndentLevel, in_table=self.nestingLevel))
        self.paraIndentLevel -= n.indentlevel
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


    def _quoteURL(self,url, baseUrl=None):
        safeChars = ':/#'
        if url.startswith('mailto:'):
            safeChars = ':/@'
        url = urllib.quote(url.encode('utf-8'),safe=safeChars)
        if baseUrl:
            url = u'%s%s' % (baseUrl, url)
        return url

    def writeLink(self,obj):
        """ Link nodes are intra wiki links
        """
        href = obj.target
        if not href:
            log.warning('no link target specified')
            href = ''

        txt = []
        if obj.children:
            txt.extend(self.renderInline(obj))
            t = ''.join(txt).strip()
        else:
            txt = [href]
            t = filterText(''.join(txt).strip()).encode('utf-8')
            t = unicode(urllib.unquote(t), 'utf-8')
        href = self._quoteURL(href, self.baseUrl)
        return [t]


    def renderURL(self, url):
        url = xmlescape(url)        
        zws = '<font fontSize="1"> </font>'
        url = url.replace("/",u'/%s' % zws).replace('&amp;', u'&amp;%s' % zws).replace('.','.%s' % zws).replace('+', '+%s' % zws)
        return url
    
    def writeURL(self, obj):       
        href = obj.caption
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
        return [''.join(txt)]
    
    def writeLangLink(self, node):
        return self.writeLink(node)

    def writeSpecialLink(self,obj):
        return self.writeLink(obj)


    def _cleanImage(self, path):
        """
        workaround for transparent images in reportlab:
        fully transparent pixels are explicitly set to white
        """
        try:
            img = PilImage.open(path)
        except IOError:
            return
        if img.mode in ['RGB', 'P', 'I']:
            return
        data = list(img.getdata())
        if not isinstance(data[0], tuple) or ( not len(data[0]) in [2,4]): # no alpha channel present
            return 
        try:
            if len(data[0]) == 4: # RGBA
                for i in range(len(data)):
                    if data[i][3] == 0: # alpha channel
                        data[i] = (255,255,255,255)
            elif len(data[0]) == 2: # LA
                for i in range(len(data)):
                    if data[i][1] == 0:
                        data[i] = (255,255)
        except:
            return        
        img.putdata(data)
        img.save(path)
        log.info('corrected image alpha channel')

    
    def writeImageLink(self,obj):
        if obj.colon == True:
            items = []
            for node in obj.children:
                items.extend(self.write(node))
            return items

        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(obj.target, size=800) # FIXME: size configurable etc.
            if imgPath:
                #self._cleanImage(imgPath)
                imgPath = imgPath.encode('utf-8')
                self.tmpImages.add(imgPath)
        else:
            imgPath = ''
        if not imgPath:
            log.warning('invalid image url')
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
        (_w,_h) = img.size
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
        align = obj.align
            
        txt = []
        for node in obj.children:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning('imageLink contained block element: %s' % type(res))
        if obj.isInline() : # or self.nestingLevel: 
            #log.info('got inline image:',  imgPath,"w:",width,"h:",height)
            txt = '<img src="%(src)s" width="%(width)fin" height="%(height)fin" valign="%(align)s"/>' % {
                'src':unicode(imgPath, 'utf-8'),
                'width':width/100,
                'height':height/100,
                'align':'bottom',
                }
            return txt
        # FIXME: make margins and padding configurable
        captionTxt = '<i>%s</i>' % ''.join(txt)  #filter
        return [Figure(imgPath, captionTxt=captionTxt,  captionStyle=text_style('figure', in_table=self.nestingLevel), imgWidth=width, imgHeight=height, margin=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), padding=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), align=align)]


    def writeGallery(self,obj):
        data = []
        row = []
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

    def writeSource(self, n):
        self.sourcemode = True
        mw_lang = n.vlist.get('lang', '').lower()
        #langMap = {'objc':ObjectiveCLexer(),
        #           }

        try:            
            lexer = lexers.get_lexer_by_name(mw_lang)
        except :
            traceback.print_exc()
            log.error('unknown source code language: %s' % repr(mw_lang))
            return []       
                
        sourceFormatter = ImageFormatter(font_size=FONTSIZE, font_name='DejaVu Sans Mono', line_numbers=False)
        sourceFormatter.encoding = 'utf-8'

        source = ''.join(self.renderInline(n))
        try:
            img = highlight(source.encode('utf-8'), lexer, sourceFormatter)
        except:
            traceback.print_exc()
            log.error('unsuitable lexer for source code language: %s - Lexer: %s' % (repr(mw_lang), lexer.__class__.__name__))
            
        fn = os.path.join(self.tmpdir, 'source%d.png' % self.sourceCount)
        f = open(fn, 'w')
        f.write(img)
        f.close()
        self.sourceCount += 1

        p = PilImage.open(fn)
        w, h = p.size
        pw = w / 1.5 # magic constant that scales the source text to an appropriate size with current font-size
        ph = h / 1.5 # fixme: clearly this has to be done in a more intelligent manner, and should depend on FONTSIZE
        scale = min( [printWidth/pw, printHeight/ph])
        if scale < 1:
            pw = pw * scale
            ph = ph * scale

        self.sourcemode = False
        image = Image(fn, width=pw, height=ph)
        image.hAlign = 'LEFT'
        return [image]

        

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
        return []
    
    def writeTagNode(self,t):
        if t.caption =='rss':
            items = []
            for node in t.children:
                items.extend(self.write(node))
            return items        
        elif t.caption in ['h1','h2','h3','h4']:
            level = int(t.caption[1])
            t.level = level
            return self.writeSection(t)
        elif t.caption == "imagemap":
            if t.imagemap.imagelink:
                return self.write(t.imagemap.imagelink)

        log.warning("Unhandled TagNode:", t.caption)
        return []

    
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
                style="enumerate"
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
        styles = serializeStyleInfo(cell.vlist)
        try:
            rowspan = int(styles.get('rowspan',1))
        except ValueError:
            rowspan = 1
        try:
            colspan = int(styles.get('colspan',1))
        except ValueError:
            colspan = 1
            
        elements = self.renderMixed(cell, text_style(in_table=self.nestingLevel))
        
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
        maxCols = rltables.getMaxCols(t)
        t = rltables.reformatTable(t, maxCols)
        maxCols = rltables.getMaxCols(t)
        # if a table contains only tables it is transformed to a list of the containing tables - that is handled below
        if t.__class__ != advtree.Table and all([c.__class__==advtree.Table for c in t]):
            tables = []
            self.nestingLevel -= 1
            for c in t:
                tables.extend(self.writeTable(c))
            return tables        
        
        for r in t.children:
            if r.__class__ == advtree.Row:
                data.append(self.writeRow(r))
            elif r.__class__ == advtree.Caption:
                elements.extend(self.writeCaption(r))                

        (data, span_styles) = rltables.checkSpans(data)

        if not data:
            return []
        
        colwidthList = rltables.getColWidths(data, nestingLevel=self.nestingLevel)
        data = rltables.splitCellContent(data)
        
        table = Table(data, colWidths=colwidthList, splitByRow=1)

        styles = rltables.style(serializeStyleInfo(t.vlist))
        table.setStyle(styles)
        table.setStyle(span_styles)
        table.setStyle([('LEFTPADDING', (0,0),(-1,-1), 3),
                        ('RIGHTPADDING', (0,0),(-1,-1), 3),
                        ])

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

        log.info("testrendering:", os.path.join(self.tmpdir, 'table%d.pdf' % self.tablecount))
        fn = os.path.join(self.tmpdir, 'table%d.pdf' % self.tablecount)
        self.tablecount += 1

        doc = BaseDocTemplate(fn)
        doc.addPageTemplates(SimplePage(pageSize=A4))
        try:
            w,h=table.wrap(printWidth, printHeight)
            log.info("tablesize:(%f, %f) pagesize:(%f, %f) tableOverflowTolerance: %f" %(w, h, printWidth, printHeight, tableOverflowTolerance))
            if w > (printWidth + tableOverflowTolerance):
                log.warning('table test rendering: too wide - printwidth: %f (tolerance %f) tablewidth: %f' % (printWidth, tableOverflowTolerance, w))
                raise LayoutError
            if self.nestingLevel > 1 and h > printHeight:
                log.warning('nested table too high')
                raise LayoutError                
            doc.build([table])
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
        source = node.caption.strip()
        source = re.compile("\n+").sub("\n", source)
        source = source.replace("'","'\\''").encode('utf-8') # escape single quotes 
        source = ' ' + source + ' '
        
        cmd = "texvc %s %s '%s' utf-8" % (self.tmpdir, self.tmpdir, source)
        res= os.popen(cmd)
        renderoutput = res.read()
        if not renderoutput.strip() or len(renderoutput) < 32:
            log.error('math rendering failed with source:', repr(source))
            log.error('render output:', repr(renderoutput))
            return []

        imgpath = os.path.join(self.tmpdir, renderoutput[1:33] + '.png')
        if not os.path.exists(imgpath):
            log.error('math rendering failed with source:', repr(source))
            return []

        img = PilImage.open(imgpath)
        log.info("math png at:", imgpath)
        w,h = img.size
        if self.nestingLevel: # scale down math-formulas in tables
            w = w * SMALLFONTSIZE/FONTSIZE
            h = h * SMALLFONTSIZE/FONTSIZE
            
        density = 120 # resolution in dpi in which math images are rendered by latex
        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 32px. UPDATE: is now 17 
        #imgAlign = '%fin' % (- (h - 32) / (2 * density))
        imgAlign = '%fin' % (- (h - 15) / (2 * density))
        return ' <img src="%(path)s" width="%(width)fin" height="%(height)fin" valign="%(valign)s" /> ' % {
            'path': imgpath.encode(sys.getfilesystemencoding()),
            'width': w/density,
            'height': h/density,
            'valign': imgAlign, }
    
    writeTimeline = ignore
    writeControl = ignore

