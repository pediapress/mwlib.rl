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
from mwlib import parser, uparser, utils

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
    optparser = optparse.OptionParser(usage="""%prog [OPTIONS] [ARTICLE ...]""")
    optparser.add_option("-c", "--config", help="config file (required unless --baseurl is given)")
    optparser.add_option("-b", "--baseurl", help="base URL for mwapidb backend")
    optparser.add_option("-s", "--shared-baseurl", help="base URL for shared images for mwapidb backend")
    optparser.add_option("-o", "--output", help="write output to OUTPUT")
    optparser.add_option("-l", "--logfile", help="write logfile")
    optparser.add_option("-m", "--metabookfile", help="json encoded text file with book structure")
    optparser.add_option("-r", "--removedarticles", help="list of articles that were removed b/c rendering was impossible")
    optparser.add_option("-d", "--daemonize", action="store_true", dest="daemonize", default=False,
                      help="return immediately and generate PDF in background")
    optparser.add_option("-e", "--errorfile", dest="errorfile", help="write errors to this file")
    optparser.add_option("--license", help="Title of article containing full license text")
    optparser.add_option("--template-blacklist", help="Title of article containing blacklisted templates")
    options, args = optparser.parse_args()
    
    try:
        if not args and not (options.metabookfile and options.output):
            optparser.error("missing ARTICLE argument")

        config = options.config
        baseurl = options.baseurl
        output = options.output
        metabookfile = options.metabookfile
        removedarticles = options.removedarticles
        logfile = options.logfile

        if logfile:
            utils.start_logging(logfile)
        
        if not baseurl and not config:
            try:
                config = os.environ['MWPDFCONFIG']
            except KeyError:
                sys.exit('Neither --conf nor --baseurl specified\nPlease specify config file location with --config, base URL with --baseurl or set environment variable MWPDFCONFIG')
    
        if options.daemonize:
            utils.daemonize()
    
        from mwlib import wiki
        from mwlib.rl import rlwriter
    
        metabook = MetaBook()
    
        if config:
            w = wiki.makewiki(config)
        
            cp=ConfigParser()
            cp.read(config)
            license = {
                'name': cp.get('wiki', 'defaultarticlelicense')
            }
            license['wikitext'] = w['wiki'].getRawArticle(license['name'])
            metabook.source = {
                'name': cp.get('wiki', 'name'),
                'url': cp.get('wiki', 'url'),
                'defaultarticlelicense': license,
            }
        else:
            w = {
                'wiki': wiki.wiki_mwapi(baseurl, options.license, options.template_blacklist),
                'images': wiki.image_mwapi(baseurl, options.shared_baseurl)
            }
            metadata = w['wiki'].getMetaData()
            metabook.source = {
                'name': metadata['name'],
                'url': metadata['url'],
                'defaultarticlelicense': metadata['license'],
            }
    
        r=rlwriter.RlWriter(images=w['images'])    
    
        coverimage = None
        if not metabookfile:
            article = unicode(args[0],'utf-8').strip()
            bookParseTree = parser.Book()
            bookParseTree.children.append(uparser.parseString(title=article, wikidb=w['wiki']))
            metabook.addArticles([article])
        else:
            metabook.readJsonFile(metabookfile)
            if config and cp.has_section('pdf'):
                coverimage = cp.get('pdf','coverimage',None)
            bookParseTree = buildBook(metabook, w['wiki'])
    
        if not output: #fixme: this only exists for debugging purposes
            output = 'test.pdf'
        if not removedarticles and output: # FIXME
            removedarticles = output + ".removed"

        r.writeBook(metabook, bookParseTree, output=output + '.tmp', removedArticlesFile=removedarticles, coverimage=coverimage)

        os.rename(output + '.tmp', output)
    except:
        if options.errorfile:
            open(options.errorfile, 'wb').write()
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
