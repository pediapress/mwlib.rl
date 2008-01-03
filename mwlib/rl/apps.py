#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import sys
import optparse
from ConfigParser import ConfigParser
import urllib
import tempfile
import shutil
from zipfile import ZipFile

import mwlib.log
from mwlib.metabook import MetaBook, mwcollection_to_metabook
from mwlib.utils import daemonize
from mwlib import parser, uparser

log = mwlib.log.Log('mw-app-rl')

def buildBook(metabook, wikidb):
    bookParseTree = parser.Book()
    for item in metabook.getItems():
        if item['type'] == 'chapter':
            bookParseTree.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            a=uparser.parseString(title=item['title'], revision=item.get('revision', None), wikidb=wikidb)
            if item.has_key('displaytitle'):
                a.caption = item['displaytitle']
            bookParseTree.children.append(a)                             
    metabook.parseTree = bookParseTree
 
def pdfall():
    """
    this method should only be used for debugging purposes!
    it takes an articlelist-file and renders all articles
    """
    optparser = optparse.OptionParser(usage="%prog [--conf CONF] -a ARTICLEFILE")
    optparser.add_option("-c", "--conf", help="config file")
    optparser.add_option("-a", "--articlefile", help="file with a list of articles which are rendered separately") 
    options, args = optparser.parse_args()
    config = options.conf
    articlefile = options.articlefile
    
    from mwlib import wiki  
    from mwlib.rl import rlwriter
    import sys
    import traceback
    
    if not config:
        try:
            config = os.environ['MWPDFCONFIG']
        except KeyError:
            sys.exit('Please specify config file location with --config or set environment variable MWPDFCONFIG')

    w = wiki.makewiki(config)
    #db = w['wiki']
    #articles = db.articles()
    import urllib
    r=rlwriter.RlWriter(images=None) # dont use images, would take to long
    errorFile = open('errors.txt','w')

    ok = 0
    err = 0
    for (count,line) in enumerate(open(articlefile).readlines()):
        # PARSE
        try:
            metabook = MetaBook()
            article = unicode(line,'utf-8').strip()
            bookParseTree = parser.Book()
            bookParseTree.children.append(uparser.parseString(title=article, wikidb=w['wiki']))
            metabook.parseTree = bookParseTree
            metabook.addArticles([article])
            metabook.source = {'url':'http://caramba.brainbot.com/'}
        except:
            print "ERROR", repr(article)
            traceback.print_exc()
            err += 1
            continue
        # RENDER
        try:
            removedarticles = "testpdf.removed"           
            r.writeBook(metabook, output='test.pdf', removedArticlesFile=removedarticles)
            print "(",count,") OK:", repr(article)
            ok += 1
        except:
            traceback.print_exc()
            tr = traceback.format_exc()
            title =  article
            errorFile.write('#######################################################\n')
            errorFile.write('#####     %s      ####\n' % title.encode('utf-8'))
            errorFile.write(tr)
            errorFile.write('\n\n\n')
            err += 1
    errorFile.close()
    print "OK", ok, "ERROR", err, "OK-RATIO:", ok/float(err+ok)*100


def pdf():
    optparser = optparse.OptionParser(usage="""%prog [-c CONFIG] [-d] [-o OUTPUT] [-r REMOVEDARTICLES] ARTICLE
OR
%prog [-c CONFIG] [-d] [-o OUTPUT] -m METABOOKFILE
""")
    optparser.add_option("-c", "--config", help="config file")
    optparser.add_option("-o", "--output", help="write output to OUTPUT")
    optparser.add_option("-l", "--logfile", help="write logfile")
    optparser.add_option("-m", "--metabookfile", help="json encoded text file with book structure")
    optparser.add_option("-r", "--removedarticles", help="list of articles that were removed b/c rendering was impossible")
    optparser.add_option("-d", "--daemonize", action="store_true", dest="daemonize", default=False,
                      help="return immediately and generate PDF in background")
    optparser.add_option("-e", "--errorfile", help="write caught errors to this file")
    options, args = optparser.parse_args()
    
    if not args and not (options.metabookfile and options.output):
        optparser.error("missing ARTICLE argument")

    config = options.config
    output = options.output
    metabookfile = options.metabookfile
    removedarticles = options.removedarticles
    logfile = options.logfile

    if logfile:
        mwlib.log.Log.logfile = (open(logfile,"w"))

    if not config:
        try:
            config = os.environ['MWPDFCONFIG']
        except KeyError:
            sys.exit('Please specify config file location with --config or set environment variable MWPDFCONFIG')
    
    if options.daemonize:
        daemonize()
    
    try:
        from mwlib import wiki
        from mwlib.rl import rlwriter
        w = wiki.makewiki(config)

        r=rlwriter.RlWriter(images=w['images'] )    
        metabook = MetaBook()
        cp=ConfigParser()
        cp.read(config)  
        metabook.source = {
            'name': cp.get('wiki', 'name'),
            'url': cp.get('wiki', 'url'),
        }    
        if not metabookfile:
            article = unicode(args[0],'utf-8').strip()
            bookParseTree = parser.Book()
            bookParseTree.children.append(uparser.parseString(title=article, wikidb=w['wiki']))
            metabook.parseTree = bookParseTree
            metabook.addArticles([article])
        else:
            metabook.readJsonFile(metabookfile)
            if cp.has_section('pdf'):
                metabook.coverimage = cp.get('pdf','coverimage',None)
            buildBook(metabook, w['wiki'])

        if not output: #fixme: this only exists for debugging purposes
            output = 'test.pdf'
        if not removedarticles and output: # FIXME
            removedarticles = output + ".removed"
            
        r.writeBook(metabook, output=output + '.tmp', removedArticlesFile=removedarticles)
            
        os.rename(output + '.tmp', output)
    except Exception, e:
        if options.errorfile:
            errorfile = open(options.errorfile, 'w')
            print 'writing errors to %r' % options.errorfile
            errorfile.write('Caught: %s %s' % (e, type(e)))
        else:
            raise
    
def pdfcollection():
    optparser = optparse.OptionParser(usage="%prog [-c CONFIG] [-d] [-o OUTPUT] COLLECTIONTITLE")
    optparser.add_option("-c", "--config", help="config file")
    optparser.add_option("-o", "--output", help="write output to OUTPUT")
    options, args = optparser.parse_args()

    config = options.config
    output = options.output

    if len(args):
        collectiontitle = args[0]
    else:
        optparser.error('missing COLLECTIONTITLE')       
    if not config:
        optparser.error("missing CONFIG FILE option")
    if not output: #fixme: this only exists for debugging purposes
        output = 'test.pdf'

    from mwlib import wiki
    from mwlib.rl import rlwriter
    w = wiki.makewiki(config)
    
    cp=ConfigParser()
    cp.read(config)  
    metabook = mwcollection_to_metabook(cp, w['wiki'].getRawArticle(collectiontitle))
    
    buildBook(metabook, w['wiki'])
    r=rlwriter.RlWriter(images=w['images'] )    
    r.writeBook(metabook, output=output)
 
def zip2pdf():
    parser = optparse.OptionParser(usage="%prog ZIPFILE OUTPUT")
    options, args = parser.parse_args()
    
    if len(args) < 2:
        parser.error("specify ZIPFILE and OUTPUT")
    
    zipfile = args[0]
    output = args[1]
    
    from mwlib import wiki, uparser, parser, zipwiki
    from mwlib.rl import rlwriter

    wikidb = zipwiki.Wiki(zipfile)
    imagedb = zipwiki.ImageDB(zipfile)
    
    def buildBook(wikidb):
        bookParseTree = parser.Book()
        for item in wikidb.metabook.getItems():
            if item['type'] == 'chapter':
                bookParseTree.children.append(parser.Chapter(item['title'].strip()))
            elif item['type'] == 'article':
                a=uparser.parseString(title=item['title'], revision=item.get('revision', None), wikidb=wikidb)
                bookParseTree.children.append(a)
        wikidb.metabook.parseTree = bookParseTree
    
    r=rlwriter.RlWriter(images=imagedb)    
    buildBook(wikidb)

    r.writeBook(wikidb.metabook, output=output)
