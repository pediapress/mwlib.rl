#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.
import copy

from mwlib import xmltreecleaner
from mwlib import advtree
from mwlib.advtree import Paragraph, PreFormatted, ItemList, Div, Reference, Cite, Item, Article, Section
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

# keys are nodes, that are not allowed to be inside one of the nodes in the value-list
# ex: we pull image links out of preformatted nodes and delete the preformatted node
moveNodes = {ImageLink:[PreFormatted],
             ItemList:[Div]}

def moveBrokenChildren(node):

    if node.__class__ in moveNodes.keys():
        firstContainer = node.parent
        container = node.parent
        while container:
            if container.__class__ in moveNodes[node.__class__]:
                if container.parent:
                    node.moveto(container)
            container = container.parent
        
    for c in node.children:
        moveBrokenChildren(c)


def fixTableColspans(node):
    """colspanning information in table cells is often wrong.    
    try to correct the obvious mistakes
    """

    # SINGLE CELL COLSPAN ERRORS FIX
    # if a row contains a single cell, we limit the colspanning amount
    # to the maximum table width
    if node.__class__ == Table:
        maxwidth = 0
        for row in node.children:
            numCells = len(row.children)
            rowwidth = 0
            for cell in row.children:
                if hasattr(cell, 'vlist'):
                    colspan = cell.vlist.get('colspan', 1)
                    if numCells > 1:
                        rowwidth += colspan
                    else:
                        rowwidth += 1
                else:
                    rowwidth +=1
            maxwidth = max(maxwidth,  rowwidth)
        for row in node.children:
            numCells = len(row.children)
            if numCells == 1:
                cell = row.children[0]
                if hasattr(cell, 'vlist'):
                    colspan = cell.vlist.get('colspan',None)
                    if colspan and colspan > maxwidth:
                        cell.vlist['colspan'] = maxwidth
    # END SINGLE CELL COLSPAN ERROR FIX
    for c in node.children:
        fixTableColspans(c)



def _any(list):
    for x in list:
        if x:
            return True
    return False

# ex: we delete preformatted nodes which are inside reference nodes, we keep all children off the preformatted node 
removeNodes = {PreFormatted:[Reference], Cite:[Item, Reference]}
def removeBrokenChildren(node):
    if node.__class__ in removeNodes.keys():
        if _any([parent.__class__ in removeNodes[node.__class__] for parent in node.parents]):
            if node.children:
                children = node.children
                node.parent.replaceChild(node, newchildren=children)
            else:
                node.remove()
            return
        
    for c in node.children:
        removeBrokenChildren(c)


def removeSingleCellTables(node):
    if node.__class__ == Table:
        if len(node.children) == 1 and len(node.children[0].children) == 1:
            if node.parent:
                cell_content = node.children[0].children[0].children
                node.parent.replaceChild(node, cell_content)
            
    for c in node.children:
        removeSingleCellTables(c)


def moveReferenceListSection(node):
    """
    the section containing the reference lists inside an article node are moved to the end of the article
    """

    if node.__class__ == Article:
        sections = node.getChildNodesByClass(Section)
        for section in sections:
            reflists = section.getChildNodesByClass(ReferenceList)
            if reflists and section.parent:
                section.parent.removeChild(section)
                node.appendChild(section)
        return
    
    for c in node.children:
        moveReferenceListSection(c)
                
def inheritStyles(node, inheritStyle={}):
    """
    style information is handed down to child nodes.
    """
    
    def flattenStyle(styleHash):
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

    def cleanInheritStyles(styleHash):
        sh = copy.copy(styleHash)
        ignoreStyles = ['border', 'border-spacing', 'background-color', 'background', 'class', 'margin', 'padding', 'align', 'colspan', 'rowspan',
                        'empty-cells', 'rules', 'clear', 'float', 'cellspacing', 'display', 'visibility']
        for style in ignoreStyles:
            sh.pop(style, None)
        return sh
            
    style = getattr(node, 'vlist', {})
    nodeStyle = inheritStyle
    if style:
        nodeStyle.update(flattenStyle(style))
        node.vlist = nodeStyle        
    elif inheritStyle:
        node.vlist = nodeStyle
    else:
        nodeStyle = {}

    for c in node.children:
        _is = cleanInheritStyles(nodeStyle)
        inheritStyles(c, inheritStyle=_is)
        
def buildAdvancedTree(root):
    advtree.extendClasses(root) 
    advtree.fixTagNodes(root)
    advtree.removeNodes(root)
    advtree.removeNewlines(root)
    advtree.fixStyles(root) 

    xmltreecleaner.fixBlockElements(root)

    moveBrokenChildren(root)
    removeChildlessNodes(root)
    removeLangLinks(root)
    fixLists(root)
    removeSingleCellTables(root)
    removeCriticalTables(root)
    removeBrokenChildren(root)
    fixTableColspans(root)
    moveReferenceListSection(root)
    inheritStyles(root)
    
