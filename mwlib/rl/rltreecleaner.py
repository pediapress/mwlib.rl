#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib import advtree
from mwlib.advtree import Paragraph
from mwlib.advtree import Text, Cell, Link, Math, URL, BreakingReturn, HorizontalRule, CategoryLink
from mwlib.advtree import SpecialLink, ImageLink, ReferenceList, Chapter, NamedURL, LangLink, Table
               
def fixLists(node): 
    """
    all ItemList Nodes that are the only children of a paragraph are moved out of the paragraph.
    the - now empty - paragraph node is removed afterwards
    """
    if node.__class__ == advtree.ItemList and node.parent and node.parent.__class__ == Paragraph:
        if not node.siblings and node.parent.parent:
            node.parent.parent.replaceChild(node.parent,[node])        
    for c in node.children[:]:
        fixLists(c)


childlessOK = [Text, Cell, Link, Math, URL, BreakingReturn, HorizontalRule, CategoryLink, LangLink,
               SpecialLink, ImageLink, ReferenceList, Chapter, NamedURL]

def removeChildlessNodes(node):
    """
    remove nodes that have no children except for nodes in childlessOk list
    """   

    if not node.children and node.__class__ not in childlessOK:
        removeNode = node
        while removeNode.parent and not removeNode.siblings:
            removeNode = removeNode.parent
        if removeNode.parent:
            removeNode.parent.removeChild(removeNode)

    for c in node.children[:]:
        removeChildlessNodes(c)

def removeLangLinks(node):
    """
    removes the language links that are listed below an article. language links
    inside the article should not be touched
    """

    txt = []
    langlinkCount = 0

    for c in node.children:
        if c.__class__ == LangLink:
            langlinkCount +=1
        else:
            txt.append(c.getAllDisplayText())
    txt = ''.join(txt).strip()
    if langlinkCount and not txt and node.parent:
        node.parent.removeChild(node)

    for c in node.children[:]:
        removeLangLinks(c)
        

def _tableIsCrititcal(table):
    classAttr = getattr(table, 'vlist', {}).get('class','')
    if classAttr.find('navbox')>-1:    
        return True

    return False

def removeCriticalTables(node):
    """
    table rendering is limited: a single cell can never be larger than a single page,
    otherwise rendering fails. in this method problematic tables are removed.
    the content is preserved if possible and only the outmost 'container' table is removed
    """

    if node.__class__ == Table and _tableIsCrititcal(node):
        children = []
        for row in node.children:
            for cell in row:
                for n in cell:
                    children.append(n)
        if node.parent:
            node.parent.replaceChild(node, children)
        return

    for c in node.children:
        removeCriticalTables(c)


def buildAdvancedTree(root):
    advtree.extendClasses(root) 
    advtree.fixTagNodes(root)
    advtree.removeNodes(root)
    advtree.removeNewlines(root)
    advtree.fixStyles(root) 
    removeChildlessNodes(root)
    removeLangLinks(root)
    fixLists(root)
    removeCriticalTables(root)
