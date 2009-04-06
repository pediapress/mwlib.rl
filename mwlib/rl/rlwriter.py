#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

import gettext
import sys
import os
import re
import urllib
import urlparse
import traceback
import tempfile
import htmlentitydefs
import shutil
import inspect
import subprocess

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

from reportlab.platypus.doctemplate import NextPageTemplate, NotAtTopPageBreak
from reportlab.platypus.tables import Table
from reportlab.platypus.flowables import Spacer, HRFlowable, PageBreak, KeepTogether, Image, CondPageBreak
from reportlab.platypus.xpreformatted import XPreformatted
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus.doctemplate import LayoutError
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

from mwlib.rl.customflowables import Figure, FiguresAndParagraphs, SmartKeepTogether

from pdfstyles import text_style, heading_style, table_style

from pdfstyles import pageMarginHor, pageMarginVert, serif_font, mono_font
from pdfstyles import printWidth, printHeight, smallfontsize, bigfontsize, fontsize
from pdfstyles import tableOverflowTolerance
from pdfstyles import max_img_width, max_img_height, min_img_dpi, inline_img_dpi
from pdfstyles import maxCharsInSourceLine
import pdfstyles 

from mwlib.writer.imageutils import ImageUtils
from mwlib.writer import miscutils, styleutils

import rltables
from pagetemplates import WikiPage, TitlePage, SimplePage

from mwlib import parser, log, uparser, metabook, timeline

from mwlib.rl import fontconfig

log = log.Log('rlwriter')

try:
    import pyfribidi
    useFriBidi = True
except ImportError:
    #log.warning('pyfribidi not installed - rigth-to-left text not typeset correctly')
    useFriBidi = False

from mwlib.rl import debughelper
from mwlib.rl.toc import TocRenderer
from mwlib.rl._version import version as rlwriterversion
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


def buildPara(txtList, style=text_style(), txt_style=None):
    _txt = ''.join(txtList)
    _txt = _txt.strip()
    if txt_style:
        _txt = '%(start)s%(txt)s%(end)s' % {
            'start': ''.join(txt_style['start']),
            'end': ''.join(txt_style['end']),
            'txt': _txt,
            }
    if len(_txt) > 0:
        try:
            return [Paragraph(_txt, style)]
        except:
            traceback.print_exc()
            log.warning('reportlab paragraph error:', repr(_txt))
            return []
    else:
        return []

class ReportlabError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    


class RlWriter(object):

    def __init__(self, env=None, strict=False, debug=False, mathcache=None, lang=None, enable_toc=False):
        localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
        translation = gettext.NullTranslations()
        if lang:
            try:
                translation = gettext.translation('mwlib.rl', localedir, [lang])
            except IOError, exc:
                log.warn(str(exc))
        translation.install(unicode=True)
        
        self.env = env
        if self.env is not None:
            self.book = self.env.metabook
            self.imgDB = env.images
        else:
            self.imgDB = None

        self.font_switcher = fontconfig.RLFontSwitcher()
        self.font_switcher.font_paths = fontconfig.font_paths
        self.font_switcher.registerDefaultFont(pdfstyles.default_font)        
        self.font_switcher.registerFontDefinitionList(fontconfig.fonts)
        self.font_switcher.registerReportlabFonts(fontconfig.fonts)


        self.image_utils = ImageUtils(pdfstyles.printWidth,
                                      pdfstyles.printHeight,
                                      pdfstyles.img_default_thumb_width,
                                      pdfstyles.img_min_res,
                                      pdfstyles.img_max_thumb_width,
                                      pdfstyles.img_max_thumb_height,
                                      pdfstyles.img_inline_scale_factor,
                                      pdfstyles.print_width_px,
                                      )
        
        self.strict = strict
        self.debug = debug
        self.level = 0  # level of article sections --> similar to html heading tag levels
        self.references = []
        self.ref_name_map = {}
        self.listIndentation = 0  # nesting level of lists
        self.listCounterID = 1
        self.tmpImages = set()
        self.namedLinkCount = 1
        self.tableNestingLevel = 0       
        self.sectionTitle = False
        self.tablecount = 0
        self.paraIndentLevel = 0

        self.gallery_mode = False
        self.pre_mode = False
        self.ref_mode = False
        self.license_mode = False
        self.source_mode = False
        self.inline_mode = 0

        self.linkList = []
        self.disable_group_elements = False
        self.failSaveRendering = False

        self.sourceCount = 0        
        self.currentColCount = 0
        self.currentArticle = None
        self.math_cache_dir = mathcache or os.environ.get('MWLIBRL_MATHCACHE')
        self.tmpdir = tempfile.mkdtemp()
        self.bookmarks = []
        self.colwidth = 0

        self.articleids = []        
        self.layout_status = None
        self.enable_toc = enable_toc
        self.toc_entries = []
        self.toc_renderer = TocRenderer()
        self.reference_list_rendered = False
        self.article_meta_info = []
        
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
                        groupedElements.append(SmartKeepTogether(group))
                        group = []
                        groupHeight = 0
                    else:
                        group.append(elements.pop(0))
                else:
                    group.append(elements.pop(0))
        if group:
            groupedElements.append(SmartKeepTogether(group))

        return groupedElements           

                                
    def write(self, obj):
        if not obj.visible:
            return []
        m = "write" + obj.__class__.__name__
        if not hasattr(self, m):
            log.error('unknown node:', repr(obj.__class__.__name__))
            if self.strict:
                raise writerbase.WriterError('Unkown Node: %s ' % obj.__class__.__name__)
            return []
        m=getattr(self, m)
        return m(obj)

    def writeBook(self, bookParseTree, output, removedArticlesFile=None,
                  coverimage=None, status_callback=None):
        
        if status_callback:
            status_callback(status=_('layouting'), progress=0)
        if self.debug:
            parser.show(sys.stdout, bookParseTree, verbose=True)
            pass

        advtree.buildAdvancedTree(bookParseTree)
        tc = TreeCleaner(bookParseTree, save_reports=self.debug)
        tc.cleanAll(skipMethods=['fixPreFormatted',
                                 'removeEmptyReferenceLists',
                                 ]) # FIXME: check if the fixPreFormatted method makes sense for mwlib.rl

        self.getArticleIDs(bookParseTree)

        self.numarticles = len(bookParseTree.getChildNodesByClass(advtree.Article))
        self.articlecount = 0
        
        if self.debug:
            #parser.show(sys.stdout, bookParseTree, verbose=True)
            print "TREECLEANER REPORTS:"
            print "\n".join([repr(r) for r in tc.getReports()])
            
        try:
            self.renderBook(bookParseTree, output, coverimage=coverimage, status_callback=status_callback)
            log.info('###### RENDERING OK')
            if hasattr(self, 'tmpdir'):
                shutil.rmtree(self.tmpdir, ignore_errors=True)
            return
        except Exception, err:
            traceback.print_exc()
            log.error('###### renderBookFailed: %s' % err)               
            try:
                self.failSaveRendering = True
                (ok_count, fail_count, fail_articles) = self.flagFailedArticles(bookParseTree, output)

                if self.strict:
                    raise writerbase.WriterError('Error rendering articles: %s' % repr(' | '.join(fail_articles)))
                
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
                raise writerbase.WriterError('Collection/article could not be rendered')

    def getArticleIDs(self, parseTree):
        for article in parseTree.getChildNodesByClass(advtree.Article):
            article_id = self.buildArticleID(article.wikiurl, article.caption)
            self.articleids.append(article_id)

    def tocCallback(self, info):
        self.toc_entries.append(info)
        
    def renderBook(self, bookParseTree, output, coverimage=None, status_callback=None):
        elements = []
        try:
            extversion = _('mwlib.ext version: %(version)s') % {
                'version': str(_extversion.version),
            }
        except NameError:
            extversion = 'mwlib.ext not used'
            
        version = _('mwlib version: %(mwlibversion)s, mwlib.rl version: %(mwlibrlversion)s, %(mwlibextversion)s') % {
            'mwlibrlversion': rlwriterversion,
            'mwlibversion': mwlibversion,
            'mwlibextversion': extversion,
        }

        if status_callback:
            self.layout_status = status_callback.getSubRange(0, 50)
            render_status = status_callback.getSubRange(51, 100)
        else:
            self.layout_status = None
            render_status = None
        if self.enable_toc:
            tocCallback = self.tocCallback
        else:
            tocCallback = None
        self.doc = PPDocTemplate(output,
                                 topMargin=pageMarginVert,
                                 leftMargin=pageMarginHor,
                                 rightMargin=pageMarginHor,
                                 bottomMargin=pageMarginVert,
                                 title=self.book.get('title'),
                                 keywords=version,
                                 status_callback=render_status,
                                 tocCallback=tocCallback,
        )

        self.output = output
        if pdfstyles.showTitlePage:
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

        if pdfstyles.showArticleAttribution:
            elements.append(NotAtTopPageBreak())
            elements.extend(self.writeArticleMetainfo())
                   
        self.license_mode = True
        for license in self.env.wiki.getLicenses():
            license_node = uparser.parseString(title=license['title'], raw=license['wikitext'], wikidb=self.env.wiki)
            advtree.buildAdvancedTree(license_node)
            tc = TreeCleaner(license_node, save_reports=self.debug)
            tc.cleanAll(skipMethods=['fixPreFormatted',
                                     'removeEmptyReferenceLists',
                                     ])
            elements.extend(self.writeArticle(license_node))
        self.license_mode = False

        if not self.failSaveRendering:
            self.doc.bookmarks = self.bookmarks

        #debughelper.dumpElements(elements)

        if not bookParseTree.getChildNodesByClass(parser.Article):
            pt = WikiPage('')
            self.doc.addPageTemplates(pt)
            elements.append(Paragraph(' ', text_style()))

        log.info("start rendering: %r" % output)
        if render_status:
            render_status(status=_('rendering'), article='', progress=0)
        try:
            self.doc.build(elements)
            if self.enable_toc:
                self.toc_renderer.build(output, self.toc_entries) # uncomment this to enable experimental TOC rendering
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
        elements = [Paragraph(self.font_switcher.fontifyText(xmlescape(title)), text_style(mode='booktitle'))]
        if subtitle:
            elements.append(Paragraph(self.font_switcher.fontifyText(xmlescape(subtitle)), text_style(mode='booksubtitle')))
        if not firstArticle:
            return elements
        self.doc.addPageTemplates(WikiPage(firstArticleTitle, **kwargs))
        elements.append(NextPageTemplate(firstArticleTitle.encode('utf-8')))
        elements.append(PageBreak())
        return elements

    def writeChapter(self, chapter):
        hr = HRFlowable(width="80%", spaceBefore=6, spaceAfter=0, color=colors.black, thickness=0.5)

        title = self.renderText(chapter.caption)
        if self.inline_mode == 0 and self.tableNestingLevel==0:
            chapter_anchor = '<a name="%s" />' % len(self.bookmarks)
            self.bookmarks.append((title, 'chapter'))
        else:
            chapter_anchor = ''
        chapter_para = Paragraph('%s%s' % (title, chapter_anchor), heading_style('chapter'))
        elements = []

        if chapter.getChildNodesByClass(advtree.Article):
            next_article_title = self.renderText(chapter.getChildNodesByClass(advtree.Article)[0].caption)
            pt = WikiPage(next_article_title)
            self.doc.addPageTemplates(pt)
            elements.append(NextPageTemplate(next_article_title.encode('utf-8')))
        elements.extend([NotAtTopPageBreak(), hr, chapter_para, hr])
        elements.extend(self.renderChildren(chapter))       
        return elements

    def writeSection(self, obj):
        lvl = getattr(obj, "level", 4)
        if self.license_mode:
            headingStyle = heading_style("license")
        else:
            headingStyle = heading_style('section', lvl=lvl+1)
        if not obj.children:
            return ''
        self.sectionTitle = True       

        headingTxt = ''.join(self.renderInline(obj.children[0])).strip()
        self.sectionTitle = False
        if lvl <= 4 and self.inline_mode == 0 and self.tableNestingLevel==0:
            anchor = '<a name="%d"/>' % len(self.bookmarks)
            self.bookmarks.append((obj.children[0].getAllDisplayText(), 'heading'))
        else:
            anchor = ''
        elements = [Paragraph('<font name="%s"><b>%s</b></font>%s' % (serif_font, headingTxt, anchor), headingStyle)]
        
        self.level += 1
        obj.removeChild(obj.children[0])
        elements.extend(self.renderMixed(obj))
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

    def buildArticleID(self, wikiurl, article_name):
        tmplink = advtree.Link()
        tmplink.target = article_name
        tmplink.capitalizeTarget = True # this is a hack, this info should pulled out of the environment if available
        #tmplink._normalizeTarget() # FIXME: this is currently removed from mwlib. we need to check URL handling in mwlib
        idstr = '%s%s' % (wikiurl, tmplink.target)
        m = md5(idstr.encode('utf-8'))
        return m.hexdigest()

    def writeArticleMetainfo(self):
        elements = []
        elements.append(Paragraph('Article Sources and Contributors', heading_style(mode='article')))
        for title, url, authors in self.article_meta_info:
            if authors:
                authors_text = ', '.join([a for a in authors if a != 'ANONIPEDITS:0'])
                authors_text = re.sub(u'ANONIPEDITS:(?P<num>\d+)', u'\g<num> %s' % _(u'anonymous edits'), authors_text) 
                authors_text = self.font_switcher.fontifyText(xmlescape(authors_text))
            else:
                authors_text = '-'
            txt = '<b>%(title)s</b> <i>%(source_label)s</i>: %(source)s <i>%(contribs_label)s</i>: %(contribs)s ' % {
                'title': title,
                'source_label': _('Source'),
                'source': self.font_switcher.fontifyText(xmlescape(url)),
                'contribs_label': _('Contributors'),
                'contribs': authors_text,
                }
            elements.append(Paragraph(txt, text_style('attribution')))
        return elements
    
    def writeArticle(self, article):
        self.references = [] 
        title = self.renderText(article.caption)
        if self.layout_status:
            self.layout_status(article=title)
            self.articlecount += 1
        elements = []
        pt = WikiPage(title)
        if hasattr(self, 'doc'): # doc is not present if tests are run
            self.doc.addPageTemplates(pt)
            elements.append(NextPageTemplate(title.encode('utf-8'))) # pagetemplate.id cant handle unicode
            if isinstance(article.getPrevious(), advtree.Article) or self.license_mode:
                if pdfstyles.pageBreakAfterArticle: # if configured and preceded by an article
                    elements.append(NotAtTopPageBreak())
                elif miscutils.articleStartsWithInfobox(article, max_text_until_infobox=100):
                    elements.append(CondPageBreak(pdfstyles.article_start_min_space_infobox))
                else:
                    elements.append(CondPageBreak(pdfstyles.article_start_min_space))

        title = self.font_switcher.fontifyText(title, defaultFont=serif_font, breakLong=True)
        self.currentArticle = repr(title)

        if self.inline_mode == 0 and self.tableNestingLevel==0:
            heading_anchor = '<a name="%d"/>' % len(self.bookmarks)
            self.bookmarks.append((article.caption, 'article'))
        else:
            heading_anchor = ''

        #add anchor for internal links
        url = getattr(article, 'url', None)
        if url:
            article_id = self.buildArticleID(article.wikiurl, article.caption)
            heading_anchor = "%s%s" % (heading_anchor, '<a name="%s" />' % article_id)
        else:
            article_id = None
            
        if self.license_mode:            
            elements.append(NotAtTopPageBreak())
            heading_para = Paragraph('<b>%s</b>%s' % (title, heading_anchor), heading_style("licensearticle"))
        else:
            heading_para = Paragraph('<b>%s</b>%s' % (title, heading_anchor), heading_style("article"))
            
        elements.append(heading_para)

        elements.append(HRFlowable(width='100%', hAlign='LEFT', thickness=1, spaceBefore=0, spaceAfter=10, color=colors.black))
        
        if not hasattr(article, 'renderFailed'): # if rendering of the whole book failed, failed articles are flagged
            elements.extend(self.renderMixed(article))
        else:
            articleFailText = _('<strong>WARNING: Article could not be rendered - ouputting plain text.</strong><br/>Potential causes of the problem are: (a) a bug in the pdf-writer software (b) problematic Mediawiki markup (c) table is too wide')
            elements.extend(self.renderFailedNode(article, articleFailText))

        # check for non-flowables
        elements = [e for e in elements if not isinstance(e,basestring)]                
        elements = self.floatImages(elements) 
        elements = self.tabularizeImages(elements)

        if self.references:
            elements.append(Paragraph('<b>' + _('References') + '</b>', heading_style('section', lvl=3)))
            elements.extend(self.writeReferenceList())
            
        #if not article.getParentNodesByClass(advtree.License):
        if not self.license_mode:
            self.article_meta_info.append((title, url, getattr(article, 'authors', '')))

        if self.layout_status:
            if not self.numarticles:
                self.layout_status(progress=100)
            else:
                self.layout_status(progress=100*self.articlecount/self.numarticles)
           
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

        def scaleImages(images):
            scaled_images = []
            for img in images:
                ar = img.imgWidth/img.imgHeight
                w = printWidth / 2 - (img.margin[1] + img.margin[3] + img.padding[1] + img.padding[3])
                h = w/ar
                if w > img.imgWidth:
                    scaled = img
                else:
                    scaled = Figure(img.imgPath, img.captionTxt, img.cs, imgWidth=w, imgHeight=h, margin=img.margin, padding=img.padding, borderColor=img.borderColor, url=img.url)
                scaled_images.append(scaled)
            return scaled_images
        
        for n in nodes:
            if isinstance(n,Figure):
                figures.append(n)
            else:
                if len(figures)>1:
                    figures = scaleImages(figures)
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
            figures = scaleImages(figures)
            data = [  [figures[i],figures[i+1]]  for i in range(int(len(figures)/2))]
            if len(figures) % 2 != 0:
                data.append( [figures[-1],''] )                   
            table = Table(data)
            finalNodes.append(table)                    
        else:
            finalNodes.extend(figures)
        return finalNodes

    def writePreFormatted(self, obj):
        self.pre_mode = True
        txt = self.renderInline(obj)
        t = ''.join(txt)
        t = re.sub( u'<br */>', u'\n', t)
        t = t.replace('\t', ' '*pdfstyles.tabsize)
        self.pre_mode = False
        if not len(t):
            return []
        
        maxCharOnLine = max( [ len(line) for line in t.split("\n")])
        char_limit = max(1, int(maxCharsInSourceLine / (max(1, 0.75*self.currentColCount))))
        if maxCharOnLine > char_limit:
            t = self.breakLongLines(t, char_limit)
        pre = XPreformatted(t, text_style(mode='preformatted', in_table=self.tableNestingLevel))
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
        if self.source_mode:
            return [txt]
        if not self.pre_mode:
            txt = self.transformEntities(txt)
        txt = xmlescape(txt)
        if self.sectionTitle:
            return [self.font_switcher.fontifyText(txt, defaultFont=serif_font, breakLong=True)]
        if self.pre_mode:
            return [txt]
        if self.gallery_mode:
            return [self.font_switcher.fontifyText(txt, breakLong=True)]
        return [self.font_switcher.fontifyText(txt)]

    def renderInline(self, node):
        txt = []
        self.inline_mode += 1
        for child in node.children:
            res = self.write(child)
            if isInline(res): 
                txt.extend(res)
            else:
                log.warning(node.__class__.__name__, ' contained block element: ', child.__class__.__name__)
        self.inline_mode -= 1
        return txt


    def renderMixed(self, node, para_style=None, textPrefix=None):        
        if not para_style:
            if self.license_mode:
                para_style = text_style("license")
            else:
                para_style = text_style(indent_lvl=self.paraIndentLevel,in_table=self.tableNestingLevel)
        elif self.license_mode:
            para_style.fontSize = max(text_style('license').fontSize, para_style.fontSize - 4)
            para_style.leading = 1

        math_nodes = node.getChildNodesByClass(advtree.Math)
        if math_nodes:
            max_source_len = max([len(math.caption) for math in math_nodes])
            if max_source_len > pdfstyles.no_float_math_len:
                para_style.flowable = False

        txt = []
        if textPrefix:
            txt.append(textPrefix)
        items = []
        
        if isinstance(node, advtree.Node): #set node styles like text/bg colors, alignment
            text_color = styleutils.rgbColorFromNode(node)
            background_color = styleutils.rgbBgColorFromNode(node)           
            if text_color:
                para_style.textColor = text_color
            if background_color:
                para_style.backColor = background_color
            align = styleutils.getTextAlign(node)
            if align in ['right', 'center', 'justify']:
                align_map = {'right': TA_RIGHT,
                             'center': TA_CENTER,
                             'justify': TA_JUSTIFY,}
                para_style.alignment = align_map[align]

        txt_style = None
        if node.__class__ == advtree.Cell and getattr(node, 'is_header', False):
            txt_style = { # check nesting: start: <a>,<b> --> end: </b></a>
                'start': ['<b>'],
                'end': ['</b>'],
                }

 
        for c in node:             
            res = self.write(c)
            if isInline(res):
                txt.extend(res)                
            else:
                items.extend(buildPara(txt, para_style, txt_style=txt_style)) 
                items.extend(res)
                txt = []
        if not len(items):
            return buildPara(txt, para_style, txt_style=txt_style)
        else:
            items.extend(buildPara(txt, para_style, txt_style=txt_style)) 
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
        return [Paragraph(''.join(txt), text_style(in_table=self.tableNestingLevel))]

    def writeDefinitionDescription(self, n):
        return self.writeIndented(n)

    def writeIndented(self, n):
        self.paraIndentLevel += getattr(n, 'indentlevel', 1)
        items = self.renderMixed(n, para_style=text_style(indent_lvl=self.paraIndentLevel, in_table=self.tableNestingLevel))
        self.paraIndentLevel -= getattr(n, 'indentlevel', 1)
        return items
        
    def writeBlockquote(self, n):
        self.paraIndentLevel += 1
        items = self.renderMixed(n, text_style(mode='blockquote', in_table=self.tableNestingLevel))
        self.paraIndentLevel -= 1
        return items     
        
    def writeOverline(self, n):
        # FIXME: there is no way to do overline in reportlab paragraphs. 
        return self.renderInline(n)

    def writeUnderline(self, n):
        return self.renderInlineTag(n, 'u')

    writeInserted = writeUnderline

    def writeSub(self, n):
        return self.renderInlineTag(n, 'sub')

    def writeSup(self, n):
        return self.renderInlineTag(n, 'super')
        
    def writeSmall(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % smallfontsize)

    def writeBig(self, n):
        return self.renderInlineTag(n, 'font', tag_attrs=' size=%d' % bigfontsize)
        
    def writeCite(self, n):
        return self.writeEmphasized(n)

    def writeStyle(self, s):
        txt = []
        txt.extend(self.renderInline(s))
        log.warning('unknown tag node', repr(s))
        return txt

    def writeLink(self,obj):
        """ Link nodes are intra wiki links
        """

        href = obj.url 

        #looking for internal links
        internallink = False
        if isinstance(obj, advtree.ArticleLink) and obj.url:            
            a = obj.getParentNodesByClass(advtree.Article)
            wikiurl = ''
            if a:
                wikiurl = getattr(a[0], 'wikiurl', '')
            article_id = self.buildArticleID(wikiurl, obj.target)
            if article_id in self.articleids:
                internallink = True
        
        if not href:
            log.warning('no link target specified')
            if not obj.children:
                return []         
        else:
            quote_idx = href.find('"')
            if quote_idx > -1:
                href = href[:quote_idx]        
        if obj.children:
            txt = self.renderInline(obj)
            t = ''.join(txt).strip()
            if not href:
                return [t]
        else:
            txt = [href]
            txt = [getattr(obj, 'full_target', None) or obj.target]
            t = self.font_switcher.fontifyText(xmlescape(''.join(txt).strip())).encode('utf-8')
            t = unicode(urllib.unquote(t), 'utf-8')

        if not internallink:
            if obj.target.startswith('#'): # intrapage links are filtered
                t = t.strip()
            else:
                t = '<link href="%s">%s</link>' % (xmlescape(href), t.strip())
        else:
            t = u'<link href="#%s">\u2192 %s</link>' % (article_id, t.strip())

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
            quote_idx = href.find('"')
            if quote_idx > -1:
                href = href[:quote_idx]
        display_text = self.renderURL(href)
        href = xmlescape(href)
        if (self.tableNestingLevel and len(href) > 30) and not self.ref_mode:
            return self.writeNamedURL(obj)
        
        txt = '<link href="%s">%s</link>' % (href, display_text)
        return [txt]
    
    def writeNamedURL(self,obj):
        href = obj.caption.strip()
        if not self.ref_mode and not self.reference_list_rendered:
            i = parser.Item()
            i.children = [advtree.URL(href)]
            self.references.append(i)
        else: # we are writing a reference section. we therefore directly print URLs
            txt = self.renderInline(obj)
            txt.append(' <link href="%s">(%s)</link>' % (xmlescape(href), self.renderURL(urllib.unquote(href))))
            return [''.join(txt)]           
            
        if not obj.children:
            linktext = '<link href="%s">[%s]</link>' % (xmlescape(href), len(self.references))
        else:
            linktext = self.renderInline(obj)
            linktext.append(' <super><link href="%s"><font size="10">[%s]</font></link></super> ' % (xmlescape(href), len(self.references)))
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
    

    def svg2png(self, img_path ):
        cmd = 'convert %s -flatten -coalesce -strip  %s.png' % (img_path, img_path)
        try:
            p = subprocess.Popen(cmd, shell=True)
            pid, status = os.waitpid(p.pid, 0)
            if status != 0 :
                log.warning('img could not be converted. convert exited with non-zero return code:', repr(cmd))
                return ''
            else:
                return '%s.png' % img_path
        except OSError:
            log.warning('img could not be converted. cmd failed:', repr(cmd))
            return ''

    def getImgPath(self, target):
        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(target, size=800) # FIXME: width should be obsolete now
            if imgPath and imgPath.lower().endswith('svg'):
                imgPath = self.svg2png(imgPath)
            if imgPath:
                imgPath = imgPath.encode('utf-8')
                self.tmpImages.add(imgPath)
        else:
            imgPath = ''
        return imgPath

    def _fixBrokenImages(self, img_node, img_path):
        img = PilImage.open(img_path)
        cmds = []
        base_cmd = [
            'convert',
            '-limit',' memory', '32mb',
            '-limit',' map', '64mb',
            '-limit', 'disk', '64mb',
            '-limit', 'area', '64mb',
            ]
        if img.info.get('interlace', 0) == 1:
            cmds.append(base_cmd + [img_path, '-interlace', 'none', img_path])
        if img.mode == 'P': # ticket 324
            cmds.append(base_cmd + [img_path, img_path]) # we esentially do nothing...but this seems to fix the problems           
        if img.mode == 'LA': # ticket 429
            cleaned = PilImage.new('LA', img.size)
            new_data = []
            for pixel in img.getdata():
                if pixel[1] == 0:
                    new_data.append((255,0))
                else:
                    new_data.append(pixel)                        
            cleaned.putdata(new_data)
            cleaned.save(img_path)
            img = PilImage.open(img_path)    

        for cmd in cmds:
            try:
                ret = subprocess.call(cmd)
                if ret != 0:
                    log.warning("converting broken image failed (return code: %d): %r" % (ret, img_path))
                    return ret
            except OSError:
                log.warning("converting broken image failed (OSError): %r" % img_path)
                raise 
        try:
            del img
            img = PilImage.open(img_path)
            d = img.load()
        except:
            log.warning('image can not be opened by PIL: %r' % img_path)
            raise
        return 0
        
    def writeImageLink(self, img_node):        
        if img_node.colon == True:
            items = []
            for node in img_node.children:
                items.extend(self.write(node))
            return items

        img_path = self.getImgPath(img_node.target)
        
        if not img_path:
            if img_node.target == None:
                img_node.target = ''
            log.warning('invalid image url (obj.target: %r)' % img_node.target)
            return []

        try:
            ret = self._fixBrokenImages(img_node, img_path)
            if ret != 0:
                return []
        except: 
            import traceback
            traceback.print_exc()
            log.warning('image skipped')
            return []

        max_width = self.colwidth
        if self.tableNestingLevel > 0 and not max_width:
            cell = img_node.getParentNodesByClass(advtree.Cell)
            if cell:
                max_width = printWidth / len(cell[0].getAllSiblings()) - 10
        max_height = max_img_height * cm
        if self.tableNestingLevel > 0:
            max_height = printHeight/4 # fixme this needs to be read from config
        if self.gallery_mode:
            max_height = printHeight/3 # same as above
        w, h = self.image_utils.getImageSize(img_node, img_path, max_print_width=max_width, max_print_height=max_height)
        
        align = img_node.align
        if advtree.Center in [ p.__class__ for p in img_node.getParents()]:
            align = 'center'
            
        txt = []
        #if getattr(img_node, 'frame', '') != 'frameless' and not getattr(img_node, 'align', '') == 'none':
        if (getattr(img_node, 'thumb') or getattr(img_node, 'frame', '') == 'frame') and not getattr(img_node, 'align', '') == 'none':
            for node in img_node.children:            
                res = self.write(node)
                if isInline(res):
                    txt.extend(res)
                else:
                    log.warning('imageLink contained block element: %s' % type(res))

        is_inline = img_node.isInline()

        url = self.imgDB.getDescriptionURL(img_node.target) or self.imgDB.getURL(img_node.target)
        if url:
            linkstart = '<link href="%s"> ' % (xmlescape(url)) # spaces are needed, otherwise link is not present. probably b/c of a inline image bug of reportlab
            linkend = ' </link>'
        else:
            linkstart = ''
            linkend = ''

        if is_inline:
            txt = '%(linkstart)s<img src="%(src)s" width="%(width)fpt" height="%(height)fpt" valign="%(align)s"/>%(linkend)s' % {
                'src': unicode(img_path, 'utf-8'),
                'width': w,
                'height': h,
                'align': 'bottom',
                'linkstart': linkstart,
                'linkend': linkend,
                }
            return txt
        captionTxt = ''.join(txt)
        figure = Figure(img_path,
                        captionTxt=captionTxt,
                        captionStyle=text_style('figure', in_table=self.tableNestingLevel),
                        imgWidth=w,
                        imgHeight=h,
                        margin=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm),
                        padding=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm),
                        align=align,
                        url=url)
        return [figure]
       

    def writeGallery(self,obj):
        self.gallery_mode = True
        perrow = obj.attributes.get('perrow', None)
        num_images = len(obj.getChildNodesByClass(advtree.ImageLink))
        if num_images == 0:
            return []
        if not perrow:            
            perrow = min(4, num_images) # 4 is the default for the number of images per gallery row
        else:
            perrow = min(6, int(perrow), num_images)
        perrow = max(1, perrow)
        data = []
        row = []
        if obj.children:
            self.colwidth = printWidth/perrow - 12
        colwidths = [self.colwidth+12]*perrow

        for node in obj.children:
            if isinstance(node, advtree.ImageLink):
                node.align='center' # this is a hack. otherwise writeImage thinks this is an inline image
                res = self.write(node)
            else:
                res = self.write(node)
                try:
                    res = buildPara(res)
                except:
                    res = Paragraph('',text_style(in_table=self.tableNestingLevel))
            if len(row) < perrow:
                row.append(res)
            else:
                data.append(row)
                row = []
                row.append(res)                
        if len(row):
            while len(row) < perrow:
                row.append('')
            data.append(row)
        table = Table(data, colWidths=colwidths)
        table.setStyle([('VALIGN',(0,0),(-1,-1),'TOP')])
        self.gallery_mode = False
        caption = obj.attributes.get('caption', None)
        self.colwidth = None
        if caption:
            txt = self.font_switcher.fontifyText(caption)
            elements = buildPara(txt, heading_style(mode='tablecaption'))
            elements.append(table)
            return elements
        else:
            return [table]


    def _len(self, txt):
        in_tag = False
        length = 0
        for c in txt:
            if c == '<':
                in_tag = True
            elif c == '>':
                in_tag = False
            elif not in_tag:
                length += 1
        return length
    
    def breakLongLines(self, txt, char_limit):
       broken_source = []
       for line in txt.split('\n'):
           if len(line) < char_limit:
               broken_source.append(line)
           else:
               words = re.findall('([ \t]+|[^ \t]+)', line)
               while words:
                   new_line = [words.pop(0)]
                   while words and (self._len(''.join(new_line)) + self._len(words[0])) < char_limit:
                       new_line.append(words.pop(0))
                   broken_source.append(''.join(new_line))
       return '\n'.join(broken_source)
        

    def _writeSourceInSourceMode(self, n, src_lang, lexer):        
        sourceFormatter = ReportlabFormatter(font_size=fontsize, font_name='DejaVuSansMono', background_color='#eeeeee', line_numbers=False)
        sourceFormatter.encoding = 'utf-8'
        source = ''.join(self.renderInline(n))        
        source = source.replace('\t', ' '*pdfstyles.tabsize)
        maxCharOnLine = max( [ len(line) for line in source.split("\n")])
        char_limit = max(1, int(maxCharsInSourceLine / (max(1, self.currentColCount))))

        if maxCharOnLine > char_limit:
            source = self.breakLongLines(source, char_limit)
        txt = ''
        try:
            txt = highlight(source, lexer, sourceFormatter)           
            return [XPreformatted(txt, text_style(mode='source', in_table=self.tableNestingLevel))]            
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
            self.source_mode = True
            res = self._writeSourceInSourceMode(n, src_lang, lexer)
            self.source_mode = False
            if res:
                return res
        return self.writePreFormatted(n)


    def writeCode(self, n):
        return self.writeTeletyped(n)

    def writeTeletyped(self, n):
        self.font_switcher.force_font = 'DejaVuSansMono'
        txt = self.renderInlineTag(n, 'font', tag_attrs='fontName="%s"' % mono_font)
        self.font_switcher.force_font = None
        return txt
    
    def writeBreakingReturn(self, n):
        return ['<br />']

    def writeHorizontalRule(self, n):
        return [HRFlowable(width="100%", spaceBefore=3, spaceAfter=6, color=colors.black, thickness=0.25)]

    def writeIndex(self, n):
        log.warning('unhandled Index Node - rendering child nodes')
        return self.renderChildren(n) #fixme: handle index nodes properly

    def writeReference(self, n, isLink=False):
        ref_name = n.attributes.get('name')
        if ref_name and not n.children:
            ref_num = self.ref_name_map.get(ref_name, '')
        else:
            i = parser.Item()
            for c in n.children:
                i.appendChild(c)            
            self.references.append(i)
            ref_num = len(self.references)
            self.ref_name_map[ref_name] = ref_num
        if getattr(n, 'no_display', False):
            return []
        if isLink:
            return ['[%s]' % len(self.references)]
        else:
            return ['<super><font size="10">[%s]</font></super> ' % ref_num]
    
    def writeReferenceList(self, n=None):
        if self.references:                
            self.ref_mode = True
            refList = self.writeItemList(self.references, style="referencelist")
            self.references = []
            self.ref_mode = False
            self.reference_list_rendered = True
            return refList
        else:
            return []

    def writeCenter(self, n):
        return self.renderMixed(n, text_style(mode='center', in_table=self.tableNestingLevel))

    def writeDiv(self, n):
        if getattr(n, 'border', False) and not n.getParentNodesByClass(Table) and not n.getChildNodesByClass(advtree.PreFormatted):
            return self.renderMixed(n, text_style(mode='box', indent_lvl=self.paraIndentLevel, in_table=self.tableNestingLevel)) 
        else:
            return self.renderMixed(n, text_style(indent_lvl=self.paraIndentLevel, in_table=self.tableNestingLevel)) 

    def writeSpan(self, n):
        return self.renderInline(n)

    def writeFont(self, n): # FIXME we should evaluate the info in the fonttag
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

        if style=='itemize':
            itemPrefix = u'<bullet>\u2022</bullet>' 
        elif style == 'referencelist':
            itemPrefix = '<bullet>%s[<seq id="liCounter%d" />]</bullet>' % (seqReset,counterID)
        elif style== 'enumerate':
            itemPrefix = '<bullet>%s<seq id="liCounter%d" />.</bullet>' % (seqReset,counterID)
        elif style.startswith('enumerateLetter'):
            itemPrefix = '<bullet>%s<seqformat id="liCounter%d" value="%s"/><seq id="liCounter%d" />.</bullet>' % (seqReset,counterID, style[-1], counterID)
        else:
            log.warn('invalid list style:', repr(style))
            itemPrefix = ''

        listIndent = max(0,(self.listIndentation + self.paraIndentLevel))
        if self.license_mode:
            para_style = text_style(mode="licenselist",indent_lvl=listIndent)
        elif self.ref_mode:
            para_style = text_style(mode="references",indent_lvl=listIndent)
        else:
            para_style = text_style(mode='list', indent_lvl=listIndent, in_table=self.tableNestingLevel)
        if resetCounter: # first list item gets extra spaceBefore
            para_style.spaceBefore = text_style().spaceBefore

        leaf = item.getFirstLeaf() # strip leading spaces from list items
        if leaf and hasattr(leaf, 'caption'):
            leaf.caption = leaf.caption.lstrip()
            
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
           

    def writeCell(self, cell, row):
        colspan = cell.attributes.get('colspan', 1)
        rowspan = cell.attributes.get('rowspan', 1)
        align = cell.attributes.get('align') or row.attributes.get('align')
        if not align and getattr(cell, 'is_header', False):
            align = 'center'
        elements = []
        if cell.getChildNodesByClass(advtree.NamedURL) or cell.getChildNodesByClass(advtree.Reference) or cell.getChildNodesByClass(advtree.Sup):
            elements.append(Spacer(0, 1))            
        elements.extend(self.renderMixed(cell, text_style(in_table=self.tableNestingLevel, text_align=align)))
        return {'content':elements,
                'rowspan':rowspan,
                'colspan':colspan}

    def writeRow(self,row):
        r = []
        
        for cell in row:
            if cell.__class__ == advtree.Cell:
                r.append(self.writeCell(cell, row))
            else:
                log.warning('table row contains non-cell node, skipped: %r' % cell.__class__.__name__)
        return r


    def writeCaption(self,node): 
        txt = []
        for x in node.children:
            res = self.write(x)
            if isInline(res):
                txt.extend(res)
        txt.insert(0, '<b>')
        txt.append('</b>')
        return buildPara(txt, heading_style(mode='tablecaption'))

    
    def writeTable(self, t):
        self.tableNestingLevel += 1
        elements = []
        data = []        

        maxCols = getattr(t, 'numcols', 0)
        t = rltables.reformatTable(t, maxCols)
        if t.__class__ == advtree.Table:
            maxCols = t.numcols

        self.currentColCount += maxCols
        
        # if a table contains only tables it is transformed to a list of the containing tables - that is handled below
        if t.__class__ != advtree.Table and all([c.__class__==advtree.Table for c in t]):
            tables = []
            self.tableNestingLevel -= 1
            self.currentColCount -= maxCols
            for c in t:
                tables.extend(self.writeTable(c))
            return tables        
        
        for r in t.children[:]:
            if r.__class__ == advtree.Row:
                data.append(self.writeRow(r))
            elif r.__class__ == advtree.Caption:
                elements.extend(self.writeCaption(r))                
                t.removeChild(r) # this is slight a hack. we do this in order not to simplify cell-coloring code

        (data, span_styles) = rltables.checkSpans(data, t)
        self.currentColCount -= maxCols

        if not data:
            self.tableNestingLevel -= 1
            return []
        colwidthList = rltables.getColWidths(data, t, nestingLevel=self.tableNestingLevel)
        data = rltables.splitCellContent(data)

        has_data = False
        for row in data:
            if row:
                has_data = True
                break
        if not has_data:
            self.tableNestingLevel -= 1
            return []
        table = Table(data, colWidths=colwidthList, splitByRow=1)        
        styles = rltables.style(t)
        table.setStyle(styles)
        table.setStyle(span_styles)
    
        table.setStyle([('LEFTPADDING', (0,0),(-1,-1), 3),
                        ('RIGHTPADDING', (0,0),(-1,-1), 3),
                        ])
        table.setStyle(rltables.tableBgStyle(t))
                       
        w,h = table.wrap(printWidth, printHeight)
        if maxCols == 1 and h > printHeight: # big tables with only 1 col are removed - the content is kept
            flatData = [cell for cell in flatten(data) if not isinstance(cell, str)]            
            self.tableNestingLevel -= 1
            return flatData 
       
        if table_style.get('spaceBefore', 0) > 0:
            elements.append(Spacer(0, table_style['spaceBefore']))
        elements.append(table)
        if table_style.get('spaceAfter', 0) > 0:
            elements.append(Spacer(0, table_style['spaceAfter']))

        (renderingOk, renderedTable) = self.renderTable(table, t)
        self.tableNestingLevel -= 1
        if not renderingOk:
            return []
        if renderingOk and renderedTable:
            return renderedTable
        #debughelper.dumpTable(table)
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
            if self.tableNestingLevel > 1 and h > printHeight:
                log.warning('nested table too high')
                raise LayoutError
            self.addAnchors(table)
            doc.build([table])
            self.delAnchors(table)
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
        while fail:
            pw += 20
            ph += 20*ar
            if pw > printWidth * 2:
                break
            try:
                doc = BaseDocTemplate(fn)
                doc.addPageTemplates(SimplePage(pageSize=(pw,ph)))
                doc.build([table])
                fail = False
                del doc
            except:
                log.info('safe rendering fail for width:', pw)
                break

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

    def addAnchors(self, table):
        anchors = ""
        for article_id in self.articleids:
            newAnchor = '<a name="%s" />' % article_id
            anchors = "%s%s" % (anchors, newAnchor)
        p = Paragraph(anchors, text_style())

        c = table._cellvalues[0][0]
        if not c:
            c = [p]
        else:
            c.append(p)

    def delAnchors(self, table):
        c = table._cellvalues[0][0]
        if c:
            c.pop()
    
    def writeMath(self, node):
        source = re.compile(u'\n+').sub(u'\n', node.caption.strip()) # remove multiple newlines, as this could break the mathRenderer
        if not len(source):
            return []
        imgpath = None
        if self.math_cache_dir:            
            _md5 = md5()
            _md5.update(source.encode('utf-8'))
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

        if self.tableNestingLevel: # scale down math-formulas in tables
            w = w * smallfontsize/fontsize
            h = h * smallfontsize/fontsize
            
        density = 120 # resolution in dpi in which math images are rendered by latex
        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 32px. UPDATE: is now 17 
        #imgAlign = '%fin' % (- (h - 32) / (2 * density))
        imgAlign = '%fin' % (- (h - 15) / (2 * density))
        #the non-breaking-space is needed to force whitespace after the formula
        return '<img src="%(path)s" width="%(width)fin" height="%(height)fin" valign="%(valign)s" />' % {
            'path': imgpath.encode(sys.getfilesystemencoding()),
            'width': w/density,
            'height': h/density,
            'valign': imgAlign, }

    
    def writeTimeline(self, node):
        img_path = timeline.drawTimeline(node.timeline, self.tmpdir)
        if img_path:
            # width and height should be parsed by the....parser and not guessed by the writer
            node.width = 180
            node.thumb = True
            node.isInline = lambda : False
            w, h = self.image_utils.getImageSize(node, img_path)
            return [Figure(img_path, '', text_style(), imgWidth=w, imgHeight=h)]        
        return []


    writeControl = ignore
    writeVar = writeEmphasized


def writer(env, output,
    status_callback=None,
    coverimage=None,
    strict=False,
    debug=False,
    mathcache=None,
    lang=None,
    enable_toc=False,       
):
    r = RlWriter(env, strict=strict, debug=debug, mathcache=mathcache, lang=lang, enable_toc=enable_toc)
    if coverimage is None and env.configparser.has_section('pdf'):
        coverimage = env.configparser.get('pdf', 'coverimage', None)
    if status_callback:
        buildbook_status = status_callback.getSubRange(0,20)
        writer_status = status_callback.getSubRange(21, 100)
    else:
        buildbook_status = writer_status = None
    book = writerbase.build_book(env, status_callback=buildbook_status)
    r.writeBook(book, output=output, coverimage=coverimage, status_callback=writer_status)

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
    },
    'lang': {
        'param': 'LANGUAGE',
        'help': 'use translated strings in given language (defaults to "en" for English)',
    },
    'enable_toc': {
        'help':'render Table of Contents - this is still highly EXPERIMENTAL',
    },
    
}
