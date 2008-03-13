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

from xml.sax.saxutils import escape as xmlescape
from PIL import Image as PilImage

def _check_reportlab():
    import reportlab
    try:
        from reportlab.platypus.doctemplate import NotAtTopPageBreak
    except ImportError:
        raise ImportError("you need to have the svn version of reportlab installed")
_check_reportlab()

#from reportlab.rl_config import defaultPageSize
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import BaseDocTemplate, SimpleDocTemplate, NextPageTemplate, NotAtTopPageBreak
from reportlab.platypus.tables import Table
from reportlab.platypus.flowables import Spacer, HRFlowable, PageBreak, KeepTogether, Image
from reportlab.platypus.xpreformatted import XPreformatted
#from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
from reportlab.platypus.doctemplate import LayoutError
from reportlab.lib.pagesizes import A4, A3

from customflowables import Figure, FiguresAndParagraphs
from pdfstyles import p_style, li_style, p_indent_style, pre_style, pre_style_small, articleTitle_style
from pdfstyles import h1_style, h2_style, h3_style, h4_style, heading_styles, figure_caption_style, table_p_style, table_style
from pdfstyles import reference_style, chapter_style, bookTitle_style, bookSubTitle_style
from pdfstyles import leftIndent, pageMarginHor, pageMarginVert, filterText, standardSansSerif, standardMonoFont
from pdfstyles import license_title_style, license_heading_style, license_text_style, license_li_style, gfdlfile
from pdfstyles import printWidth, printHeight, dl_style, SMALLFONTSIZE, BIGFONTSIZE, p_center_style
#from pdfstyles import pageWidth, pageHeight, bookAuthor_style

import rltables
from pagetemplates import WikiPage, TitlePage, SimplePage

from mwlib import parser, log
from mwlib import rendermath


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

def buildPara(txtList, style=p_style):
    _txt = ''.join(txtList)
    _txt = _txt.strip()
    if len(_txt) > 0:
        return [Paragraph(_txt, style)]
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

    def __init__(self, images=None):        
        self.level = 0  # level of article sections --> similar to html heading tag levels
        self.references = []
        self.imgDB = images
        self.listIndentation = 0  # nesting level of lists
        self.listCounterID = 1
        self.baseUrl = ''
        self.tmpImages = set()
        self.namedLinkCount = 1   
        self.nestingLevel = -1       
        self.renderer = rendermath.Renderer()
        self.sectionTitle = False
        self.tablecount = 0
        
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
        headingStyles = [h1_style, h2_style, h3_style, h4_style, articleTitle_style]
        def isHeading(e):
            return isinstance(e, HRFlowable) or (hasattr(e, 'style') and  e.style in headingStyles)
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

    def cleanElements(self, elements):
        for e in elements:
            if isinstance(e, Paragraph) and (e.text == '<br />' or e.text == '<br/>'):
                elements.remove(e)

    def writeGFDL(self,gfdlfile=gfdlfile):
        elements = []
        elements.append(NotAtTopPageBreak())
        for line in open(gfdlfile).readlines():
            if line.startswith("="):
                elements.append( Paragraph(line[2:], license_title_style) )
            elif re.match('\d\. ', line):
                elements.append( Paragraph(line, license_heading_style) )
            elif len(line.strip()):
                if line.startswith("*"):
                    elements.append( Paragraph(re.sub('^\* (?P<num>[A-Z]\.) ', '<bullet><b>\g<num></b></bullet>', line), license_li_style) ) # "list items"
                else:
                    elements.append( Paragraph(line, license_text_style) )           
        return elements


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
        m=getattr(self, m)
        return m(obj)

    def writeBook(self, book, bookParseTree, output, removedArticlesFile=None,
                  coverimage=None):
        self.outputdir = output
        #debughelper.showParseTree(sys.stdout, bookParseTree)
        buildAdvancedTree(bookParseTree)
        debughelper.showParseTree(sys.stdout, bookParseTree)
        try:
            self.renderBook(book, bookParseTree, output, coverimage=coverimage)
            log.info('###### RENDERING OK')
            return 0       
        except:
            try:
                self.removeBadArticles(book, bookParseTree, output, removedArticlesFile)
                self.renderBook(book, bookParseTree, output, coverimage=coverimage)
                log.info('###### RENDERING OK - REMOVED ARTICLES:')#, repr(open(removedArticlesFile).read()))            
                return 0
            except Exception, err: # cant render book
                traceback.print_exc()
                log.error('###### RENDERING FAILED:')
                log.error(err)
                raise

    def renderBook(self, book, bookParseTree, output, coverimage=None):
        self.book = book
        self.baseUrl = book.source['url']
        elements = []
        version = 'mwlib version: %s , rlwriter version: %s' % (rlwriterversion, mwlibversion)
        self.doc = BaseDocTemplate(output, topMargin=pageMarginVert, leftMargin=pageMarginHor, rightMargin=pageMarginHor, bottomMargin=pageMarginVert,title=getattr(book, 'title', None), keywords=version)

        self.output = output
        self.tmpdir = tempfile.mkdtemp()

        elements.extend(self.writeTitlePage(coverimage=coverimage))
        try:
            for e in bookParseTree.children:
                r = self.write(e)
                elements.extend(r)
        except:
            traceback.print_exc()
            raise
        #self.cleanElements(elements)
        elements = self.groupElements(elements)
        #debughelper.dumpElements(elements)
        elements.extend(self.writeGFDL())
        log.info("start rendering: %r" % output)
        try:
            self.doc.build(elements)
            return 0
        except Exception, err:
            log.error('error:\n', err)
            traceback.print_exc()
            raise

    def removeBadArticles(self, book, bookParseTree, output, removedArticlesFile):
        from mwlib.parser import Article
        log.warning("unable to render book - removing problematic articles")
        removed_articles = []
        ok_articles = []
        for (i,node) in enumerate(bookParseTree):
            if isinstance(node, Article):
                elements = []
                elements.extend(self.writeArticle(node))
                try:
                    testdoc = BaseDocTemplate(output, topMargin=pageMarginVert, leftMargin=pageMarginHor, rightMargin=pageMarginHor, bottomMargin=pageMarginVert, title=getattr(book, 'title', None))
                    testdoc.addPageTemplates(WikiPage(title=node.caption))
                    testdoc.build(elements)
                    ok_articles.append(node.caption)
                except Exception, err:
                    log.error('article failed:' , node.caption)
                    tr = traceback.format_exc()
                    log.error(tr)
                    bookParseTree.children.remove(node)
                    removed_articles.append(node.caption)
        if not removedArticlesFile:
            log.warning('removed Articles:' + ' '.join(removed_articles))
            return
        f = open(removedArticlesFile,"w")
        for a in removed_articles:
            f.write("%s\n" % a.encode("utf-8"))
        f.close()
        if len(ok_articles) == 0:
            raise ReportlabError('all articles in book can\'t be rendered')
    
    def writeTitlePage(self, coverimage=None):       
        title = getattr(self.book, 'title', None)
        subtitle =  getattr(self.book, 'subtitle', None)
        if not title:
            return []
        self.doc.addPageTemplates(TitlePage(cover=coverimage))
        elements = [Paragraph(xmlescape(title), bookTitle_style)]
        if subtitle:
            elements.append(Paragraph(xmlescape(subtitle), bookSubTitle_style))
        for item in self.book.getItems():
            if item['type'] == 'article':
                firstArticle = item['title']
                break
        self.doc.addPageTemplates(WikiPage(firstArticle))
        elements.append(NextPageTemplate(firstArticle.encode('utf-8')))
        elements.append(PageBreak())
        return elements

    def writeChapter(self, chapter):
        hr = HRFlowable(width="80%", spaceBefore=6, spaceAfter=0, color=colors.black, thickness=0.5)
        return [NotAtTopPageBreak(),
                hr,
                Paragraph(xmlescape(chapter.caption), chapter_style),
                hr]

    def writeSection(self,obj):
        level = min(obj.getSectionLevel() + 1,3)
        #level = min(obj.level-1,3)
        headingStyle = heading_styles[level]
        self.sectionTitle = True
        headingTxt = ''.join(self.write(obj.children[0])).strip()
        self.sectionTitle = False
        elements = [Paragraph('<font name=%s><b>%s</b></font>' % (standardSansSerif,headingTxt), headingStyle)]
        self.level += 1
        for node in obj.children[1:]:
            res = self.write(node)
            if isInline(res): #FIXME: parser bug. we have to catch tagnodes 
                res = buildPara(res)
            elements.extend(res)
        self.level -= 1
        return elements

    def writeArticle(self,article):
        self.references = [] 
        title = xmlescape(article.caption)
        log.info('writing article: %r' % title)
        elements = []
        pt = WikiPage(title)
        self.doc.addPageTemplates(pt)
        elements.append(NextPageTemplate(title.encode('utf-8'))) # pagetemplate.id cant handle unicode
        elements.append(Paragraph("<b>%s</b>" % filterText(title, defaultFont=standardSansSerif), articleTitle_style))
        elements.append(HRFlowable(width='100%', hAlign='LEFT', thickness=1, spaceBefore=0, spaceAfter=10, color=colors.black))
        for e in article:
            r = self.write(e)
            if isInline(r): #FIXME:  parser bug. we have to catch tagnodes 
                r = buildPara(r)
            elements.extend(r)
        # check for non-flowables
        elements = [e for e in elements if not isinstance(e,basestring)]                
        elements = self.floatImages(elements)
        elements = self.tabularizeImages(elements)
        return elements
    
    def writeParagraph(self,obj):
        txt = []
        elements = []
        for node in obj:
            x = self.write(node)
            if isInline(x):
                txt.extend(x)
            else:
                _txt = ''.join(txt)
                if len(_txt.strip()) > 0:
                    elements.append(Paragraph(''.join(txt),p_style)) #filter
                txt = []
                elements.extend(x)

        t = ''.join(txt) # catch image only paragraphs. probably due to faulty/unwanted MW markup        
        if len(t.strip()):            
            imgRegex = re.compile('<img src="(?P<src>.*?)" width="(?P<width>.*?)in" height="(?P<height>.*?)in" valign=".*?"/>$')
            res=imgRegex.match(t)
            if res:
                try:                    
                    src = res.group('src')
                    log.info('got image only paragraph:', src, 'width', res.group('width'), 'height', res.group('height'))
                    if self.nestingLevel > -1:
                        width = float(res.group('width')) * inch
                        height = float(res.group('height')) * inch
                    else:
                        img = PilImage.open(src)
                        w,h = img.size
                        ar = w/h
                        arPage = printWidth/printHeight
                        if printWidth >= 1/4 *printHeight * ar:
                            height = min(1/4*printHeight, h * inch/100) # min res is 100dpi
                        else:
                            height = min(printWidth / ar, h * inch/100)
                        width = height * ar
                    return [Image(src, width=width, height=height, lazy=0)]
                except:
                    traceback.print_exc()
                    pass
            elements.append(Paragraph(t, p_style)) #filter
        return elements

    def floatImages(self, nodes):
        """Floating images are combined with paragraphs.
        This is achieved by sticking images and paragraphs
        into a FiguresAndParagraphs flowable

        @type nodes: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """

        def getMargins(align):
            if align=='right':
                #return (0.15*cm, 0, 0.35*cm, 0.2*cm)
                return (0, 0, 0.35*cm, 0.2*cm)
            elif align=='left':
                #return (0.15*cm, 0.2*cm, 0.35*cm, 0)
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
                hf += f.imgHeight + f.margin[0] + f.margin[2] + f.padding[0] + f.padding[2] + f.cs.leading
                #w, _hf = f.wrap(pageWidth, pageHeight) FIXME: this should be more accurate
                maxImgWidth=max(maxImgWidth, f.imgWidth)
            for p in paras:
                if isinstance(p,Paragraph):
                    w,h = p.wrap(printWidth - maxImgWidth,printHeight)
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
                    if ((hasattr(n, 'style') and (n.style.name in ['p_style','p_style_indent', 'dl_style', 'li_style', 'h4_style', 'h3_style', 'h2_style'])) or \
                       (hasattr(n, 'style') and (n.style.name.startswith('p_indent') or n.style.name.startswith('li_style'))  ) ) \
                       and not gotSufficientFloats(figures, floatingNodes): #newpara
                        floatingNodes.append(n)
                    else:
                        if len(floatingNodes) > 0:
                            if hasattr(floatingNodes[-1], 'style') and floatingNodes[-1].style.name in ['h4_style', 'h3_style', 'h2_style']: # prevent floating headings before nonFloatables
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
        txt = []
        txt.extend(self.renderInline(obj))
        t = ''.join(txt)
        t = re.sub( "<br */>", "\n", t.strip())
        if len(t):
            # fixme: if any line is too long, we decrease fontsize to try to fit preformatted text on the page
            # PreformattedBox flowable should do intelligent and visible splitting when necessary
            maxCharOnLine = max( [ len(line) for line in t.split("\n")])
            if maxCharOnLine > 76: #fixme: a more intelligent method should be used to find out if text is to wide for page
                pre = XPreformatted(t, pre_style_small)
            else:
                pre = XPreformatted(t, pre_style)
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
                items.extend(buildPara(txt, p_style)) #filter
                items.extend(res)
                txt = []
        if not len(items):
            return txt
        else:
            items.extend(buildPara(txt,p_style)) #filter
        return items
        
    def writeText(self,obj):
        txt = obj.caption
        if self.sectionTitle:
            return [filterText(xmlescape(txt), defaultFont=standardSansSerif)]
        return [filterText(xmlescape(txt))]

    def renderInline(self, node):
        txt = []
        for child in node.children:
            res = self.write(child)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning(node.__class__.__name__, ' contained block element: ', child.__class__.__name__)
        return txt


    def renderMixed(self,node, para_style=p_style):
        txt = []
        items = []
        for c in node:
            res = self.write(c)
            if isInline(res):
                txt.extend(res)
            else:
                items.extend(buildPara(txt, para_style)) #filter
                items.extend(res)
                txt = []
        if not len(items):
            return buildPara(txt, para_style)
        else:
            items.extend(buildPara(txt, para_style)) #filter
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
        return [Paragraph(''.join(txt), p_style)]

    def writeDefinitionDescription(self, n):
        return self.writeIndented(n)

    def writeIndented(self, n):
        txt = self.renderInline(n)
        return [Paragraph(''.join(txt), p_indent_style(leftIndent))]
        
    def writeBlockquote(self, n):
        txt = self.writeEmphasized(n)
        return [Paragraph(''.join(txt), p_indent_style(leftIndent))]

    def writeOverline(self, n):
        pass

    def writeUnderline(self, n):
        return self.renderInlineTag(n, 'u')

    def writeSub(self, n):
        return self.renderInlineTag(n, 'sub')

    def writeSup(self, n):
        return self.renderInlineTag(n, 'super')
        
    def writeSmall(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % SMALLFONTSIZE)

    def writeBig(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % BIGFONTSIZE)
        
    def writeCite(self, n):
        self.writeDefinitionDescription(n)

    def writeStyle(self, s):
        txt = []
        txt.extend(self.renderInline(s))
        log.warning('unknown tag node', repr(s))
        return txt

    def writeLink(self,obj):
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
            t = ''.join(txt).strip().encode('utf-8')
            t = unicode(urllib.unquote(t), 'utf-8')
            
        url = u"%s%s" % (self.baseUrl, urllib.quote(href.encode('utf-8')))
        return ['<link href="%s">%s</link>' % ( url, t)] #filter

    def writeSpecialLink(self,obj):
        return self.writeLink(obj)

    def writeURL(self, obj):
        txt = []       
        if obj.children:
            txt.extend(self.renderInline(obj))
        else:
            txt.append(filterText(xmlescape(obj.caption)))
            
        return ['<link href="%(href)s">%(text)s</link>' % {
            'href':urllib.quote(obj.caption.encode('utf-8'),safe=':/'),
            'text': ''.join(txt).strip()
            }]
    
    def writeNamedURL(self,obj):
        txt = []
        if obj.children:
            txt.extend(self.renderInline(obj))
        else:
            name = "[%s]" % self.namedLinkCount
            self.namedLinkCount += 1
            txt.append(name)            
        return ['<link href="%(href)s">%(text)s</link>' % {
            'href':urllib.quote(obj.caption.encode('utf-8'),safe=':/'),
            'text': ''.join(txt).strip()
            }]

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
        url = u"%s%s" % (self.baseUrl, urllib.quote(txt.encode('utf-8')))
        return ['<link href="%s">%s</link>' % ( url, ''.join(txt))]
    

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

        targetWidth = 400
        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(obj.target, size=targetWidth)
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
            max_img_width = 7 # max size in cm FIXME: make this configurable
            max_img_height = 11 # FIXME: make this configurable
            scale = 1/30 # 100 dpi = 30 dpcm <-- this is the minimum pic resolution FIXME: make this configurable
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
        #if not align:
        #    align = 'right' # FIXME: make this configurable
            
        txt = []
        for node in obj.children:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning('imageLink contained block element: %s' % type(res))
        if obj.isInline(): 
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
        return [Figure(imgPath, captionTxt=captionTxt,  captionStyle=figure_caption_style, imgWidth=width, imgHeight=height, margin=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), padding=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), align=align)]


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
                    res = Paragraph('',p_style)
            if len(row) == 0:
                row.append(res)
            else:
                row.append(res)
                data.append(row)
                row = []
        if len(row) == 1:
            row.append(Paragraph('',p_style))
            data.append(row)
        table = Table(data)
        return [table]

    def writeCode(self, n):
        return self.writePreFormatted(n)

    def writeTeletyped(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs='fontName=%s' % standardMonoFont)
        
    def writeBreakingReturn(self, n):
        return ['<br />']

    def writeHorizontalRule(self, n):
        return [HRFlowable(width="100%", spaceBefore=3, spaceAfter=6, color=colors.black, thickness=0.25)]

    def writeIndex(self, n):
        log.warning('unhandled Index Node - rendering child nodes')
        return self.renderChildren(n) #fixme: handle index nodes properly

    def writeReference(self, n):
        i = parser.Item()
        i.children = [c for c in n.children]
        self.references.append(i)
        return ['<super><font size="10">[%s]</font></super> ' % len(self.references)]
    
    def writeReferenceList(self, n):
        if self.references:                
            return self.writeItemList(self.references, numbered=True, style=reference_style)
        else:
            return []

    def writeCenter(self, n):
        return self.renderMixed(n, para_style=p_center_style)

    def writeDiv(self, n):
        return self.renderMixed(n, para_style=p_style) 

    def writeSpan(self, n):
        return self.renderInline(n)

    def writeStrike(self, n):
        return self.renderInlineTag(n, 'strike')


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

    def writeItem(self, item, numbered=False, counterID=None, style=li_style, resetCounter=False):
        # FIXME: refactor parameters: style shouldn't be passed, but some styletype-var. numbered Boolean could be merged with that
        txt = []
        items = []
        if resetCounter:
            seqReset = '<seqreset id="liCounter%d" base="0" />' % (counterID)
        else:
            seqReset = ''
        def finishPara(txt):           
            if not txt:
                return
            listIndent = max(0,(self.listIndentation))
            txt = ''.join(flatten(txt)).strip()
            if not numbered:
                li = Paragraph(u'<bullet>\u2022</bullet>%s' % txt, li_style(listIndent))
            elif style == reference_style:
                li = Paragraph('<bullet>%s[<seq id="liCounter%d" />]</bullet>%s' % (seqReset,counterID, txt), li_style(listIndent))
            else:
                li = Paragraph('<bullet>%s<seq id="liCounter%d" />.</bullet>%s' % (seqReset,counterID, txt), li_style(listIndent))
            items.append(li)
            txt = []
        
        for x in item:
            res = self.write(x)
            if not res:
                continue
            if isInline(res):
                txt.append(res)
            else:
                finishPara(txt)
                items.extend(res)
        finishPara(txt)
        return items

    def writeItemList(self, lst, numbered=False, style=li_style):
        self.listIndentation += 1
        items = []
        numbered = numbered or lst.numbered
        self.listCounterID += 1
        counterID = self.listCounterID           
        for (i,node) in enumerate(lst):
            if isinstance(node,parser.Item): 
                resetCounter = i==0 # we have to manually reset sequence counters. due to w/h calcs with wrap reportlab gets confused
                items.extend(self.writeItem(node,numbered=numbered, counterID=counterID, style=style, resetCounter=resetCounter))
            else:
                items.extend(self.write(node))
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
            
        txt = []
        elements = []
        for node in cell:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                elements.extend(buildPara(txt,table_p_style)) #filter
                txt = []
                elements.extend(res)
        if txt:
            elements.extend(buildPara(txt,table_p_style)) #filter

        return {'content':elements,
                'rowspan':rowspan,
                'colspan':colspan}

    def writeRow(self,row):
        r = []
        for cell in row:
            if cell.__class__ == advtree.Cell:
                r.append(self.writeCell(cell))
            else:
                log.warning('table row contains: %s - node skipped' % x.__class__.__name__)
        return r


    def writeCaption(self,node): 
        txt = []
        for x in node.children:
            res = self.write(x)
            if isInline(res):
                txt.extend(res)
        return buildPara(txt, p_style)              

    
    def writeTable(self, t):
        self.nestingLevel += 1
        elements = []
        data = []        

        t = rltables.reformatTable(t)
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
        (gotData, onlyListItems, maxCellContent, maxCols) = rltables.checkData(data)
        if not gotData:
            log.info('got empty table')
            self.nestingLevel -= 1
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

        self.nestingLevel -= 1

        (renderingOk, renderedTable) = self.renderTable(table)
        if not renderingOk:
            return []
        if renderingOk and renderedTable:
            return [renderedTable]
        return elements

    def renderTable(self, table):
        """
        method that checks if a table can be rendered by reportlab. this is done, b/c large tables cause problems.
        if a large table is detected, it is rendered on a doublesize canvas and - on success - embedded as an
        scaled down image.
        """

        fn = os.path.join(self.tmpdir, 'table%d.pdf' % self.tablecount)
        self.tablecount += 1

        doc = BaseDocTemplate(fn)
        doc.addPageTemplates(SimplePage(pageSize=A4))
        try:
            w,h=table.wrap(printWidth, printHeight)
            if w > printWidth:
                raise LayoutError
            doc.build([table])
            return (True, None)
        except LayoutError:
            log.warning('table rendering failed for: ', fn)

        log.info('try safe table rendering')
        doc = BaseDocTemplate(fn)
        doc.addPageTemplates(SimplePage(pageSize=A3))
        try:
            doc.build([table])
            log.info('safe rendering ok')
        except LayoutError:
            log.warning('table rendering failed for: ', fn)
            return (False, None)

        imgname = fn +'.png'
        os.system('convert -density 150 %s %s' % (fn, imgname))        
        img = Image(imgname, width=printWidth*0.95, height=printHeight*0.95)

        return (True, img)
            
    def writeMath(self, node):
        source = node.caption.strip()
        source = re.compile("\n+").sub("\n", source)
        source = source.replace("'","'\\''").encode('utf-8') # escape single quotes 

        #fixme: we should use the texvc that's bundled with the mediawiki installation
        texvc = os.path.join(os.path.dirname(__file__), '../math/') + 'texvc' 
        cmd = "%s %s %s '%s' utf-8" % (texvc, self.tmpdir, self.tmpdir, source)
        f = os.popen(cmd)
        renderoutput = f.read()
        imgpath = os.path.join(self.tmpdir, renderoutput[1:33] + '.png')

        img = PilImage.open(imgpath)
        log.info("math png at:", imgpath)
        w,h = img.size
        #density = 300 # resolution in dpi in which math images are rendered by latex
        density = 120
        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 32px. UPDATE: is now 17 
        #imgAlign = '%fin' % (- (h - 32) / (2 * density))
        imgAlign = '%fin' % (- (h - 15) / (2 * density))
        return ' <img src="%(path)s" width="%(width)fin" height="%(height)fin" valign="%(valign)s" /> ' % {
            'path': imgpath.encode(sys.getfilesystemencoding()), # FIXME: imgPath needs to be configurable
            'width': w/density,
            'height': h/density,
            'valign': imgAlign, }
    

    writeLangLink = ignore
    writeTimeline = ignore
    writeControl = ignore

