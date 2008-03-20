#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import sys
import optparse
from ConfigParser import ConfigParser

import mwlib.log
from mwlib.metabook import MetaBook
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
    return bookParseTree


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

        licensearticle = cp.get('wiki', 'defaultarticlelicense')
        if licensearticle:
            license = uparser.parseString(title=licensearticle, wikidb=w['wiki'])
        metabook.source = {
            'name': cp.get('wiki', 'name'),
            'url': cp.get('wiki', 'url'),
            'defaultarticlelicense': license,
        }    
        coverimage = None
        if not metabookfile:
            article = unicode(args[0],'utf-8').strip()
            bookParseTree = parser.Book()
            bookParseTree.children.append(uparser.parseString(title=article, wikidb=w['wiki']))
            metabook.addArticles([article])
        else:
            metabook.readJsonFile(metabookfile)
            if cp.has_section('pdf'):
                coverimage = cp.get('pdf','coverimage',None)
            bookParseTree = buildBook(metabook, w['wiki'])

        if not output: #fixme: this only exists for debugging purposes
            output = 'test.pdf'
        if not removedarticles and output: # FIXME
            removedarticles = output + ".removed"
            
        r.writeBook(metabook, bookParseTree, output=output + '.tmp', removedArticlesFile=removedarticles, coverimage=coverimage)
            
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
    metabook = MetaBook()
    metabook.source = {
        'name': cp.get('wiki', 'name'),
        'url': cp.get('wiki', 'url'),
    }
    metabook.loadCollectionPage(w['wiki'].getRawArticle(collectiontitle))
    
    bookParseTree = buildBook(metabook, w['wiki'])
    r=rlwriter.RlWriter(images=w['images'] )    
    r.writeBook(metabook, bookParseTree, output=output)
 
def zip2pdf():
    parser = optparse.OptionParser(usage="%prog ZIPFILE OUTPUT")
    options, args = parser.parse_args()
    
    if len(args) < 2:
        parser.error("specify ZIPFILE and OUTPUT")
    
    zipfile = args[0]
    output = args[1]
    
    from mwlib import parser, zipwiki
    from mwlib.rl import rlwriter

    wikidb = zipwiki.Wiki(zipfile)
    imagedb = zipwiki.ImageDB(zipfile)
    
    def buildBook(wikidb):
        bookParseTree = parser.Book()
        for item in wikidb.metabook.getItems():
            if item['type'] == 'chapter':
                bookParseTree.children.append(parser.Chapter(item['title'].strip()))
            elif item['type'] == 'article':
                a = wikidb.getParsedArticle(title=item['title'], revision=item.get('revision'))
                bookParseTree.children.append(a)
        return bookParseTree
    
    r=rlwriter.RlWriter(images=imagedb)    
    bookParseTree = buildBook(wikidb)

    r.writeBook(wikidb.metabook, bookParseTree, output=output)
