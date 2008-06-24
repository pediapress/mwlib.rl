#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import sys
import optparse
from ConfigParser import ConfigParser, Error as CPError

import mwlib.log
from mwlib.metabook import MetaBook
from mwlib import parser, uparser, utils

log = mwlib.log.Log('mw-app-rl')

def buildBook(metabook, wikidb, progress=None, progress_range=(10, 70)):
    bookParseTree = parser.Book()
    items = list(metabook.getItems())
    if progress is not None and items:
        p = progress_range[0]
        inc = (progress_range[1] - p) / len(items)
    for item in items:
        progress(p)
        if item['type'] == 'chapter':
            bookParseTree.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            a=uparser.parseString(title=item['title'], revision=item.get('revision', None), wikidb=wikidb)
            if item.has_key('displaytitle'):
                a.caption = item['displaytitle']
            bookParseTree.children.append(a)
        p += inc
    progress(progress_range[1])
    return bookParseTree


def pdf():
    from mwlib.options import OptionParser
    
    optparser = OptionParser()
    optparser.add_option("-o", "--output", help="write output to OUTPUT")
    optparser.add_option("-d", "--daemonize", action="store_true", dest="daemonize", default=False,
                      help="return immediately and generate PDF in background")
    optparser.add_option("-e", "--errorfile", dest="errorfile", help="write errors to this file")
    optparser.add_option("-p", "--progress", help="write progress to PROGRESS")
    options, args = optparser.parse_args()

    if not options.output: # FIXME: this only exists for debugging purposes
        options.output = 'test.pdf'
    
    if not options.conf:
        try:
            options.conf = os.environ['MWPDFCONFIG']
        except KeyError:
            sys.exit('Please specify config file location with --conf or set environment variable MWPDFCONFIG')
        
    def progress(p):
        if options.progress is None:
            return
        f = open(options.progress, 'wb')
        f.write('%d\n' % p)
        f.close()
    
    try:
        from mwlib.rl import rlwriter
        
        env = optparser.env
        
        progress(0)
        if options.daemonize:
            utils.daemonize()
        
        progress(10)
        
        r = rlwriter.RlWriter(env)    
        
        coverimage = None
        if env.configparser.has_section('pdf'):
            coverimage = env.configparser.get('pdf', 'coverimage', None)
        
        bookParseTree = buildBook(env.metabook, env.wiki, progress=progress, progress_range=(10, 70))
        
        r.writeBook(bookParseTree, output=options.output + '.tmp', coverimage=coverimage)
        
        os.rename(options.output + '.tmp', options.output)
        progress(100)
    except:
        if options.errorfile:
            import traceback
            traceback.print_exc(file=open(options.errorfile, 'wb'))
        raise

def zip2pdf():
    parser = optparse.OptionParser(usage="%prog ZIPFILE OUTPUT")
    options, args = parser.parse_args()
    
    if len(args) < 2:
        parser.error("specify ZIPFILE and OUTPUT")
    
    from mwlib import parser, wiki
    from mwlib.rl import rlwriter
    
    zipfile = args[0]
    output = args[1]
    
    env = wiki.makewiki(zipfile)
    
    bookParseTree = parser.Book()
    for item in env.metabook.getItems():
        if item['type'] == 'chapter':
            bookParseTree.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            a = env.wiki.getParsedArticle(title=item['title'], revision=item.get('revision'))
            bookParseTree.children.append(a)
    
    rlwriter.RlWriter(env).writeBook(bookParseTree, output=output)
    env.images.clean()
