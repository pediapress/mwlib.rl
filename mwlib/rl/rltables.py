#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

import re

from mwlib.utils import all
from mwlib import log
from mwlib.advtree import Text, ItemList, Table, Row, Cell
from mwlib.writer import styleutils

from reportlab.lib import colors
from customflowables import Figure
#import debughelper
from pdfstyles import printHeight, printWidth


log = log.Log('rlwriter')


def checkSpans(data, t):
    """
    use colspan and rowspan attributes to build rectangular table data array
    """
    styles = []
    rowspans = []
    maxCols = 0

    for (i,row) in enumerate(data):
        added_cells = 0
        for (j,cell) in enumerate(row):
            colspan = cell.get('colspan', 1)
            rowspan  = cell.get('rowspan', 1)
            if rowspan > (len(data) - i):  # check for broken rowspans
                rowspan = len(data) - i       
            if colspan > 1:
                styles.append( ('SPAN',(j,i), (j+colspan-1,i)) ) 
                for cols in range(colspan-1):
                    data[i].insert(j + 1,{'content':'','inserted':'colspan'})
            if rowspan > 1:
                styles.append( ('SPAN',(j,i),(j + colspan-1,i+rowspan-1)) )
                for row_offset in range(rowspan-1):
                    for c in range(colspan):
                        data[i+row_offset+1].insert(j,{'content':'', 'inserted':'rowspan'})
                        t.children[i+row_offset+1].children.insert(j, Cell())
        maxCols = max(maxCols, len(data[i]))

    d = []
    for row in data: # extract content from cells
        newRow = [cell['content'] for cell in row] 
        while len(newRow) < maxCols: # make sure table is rectangular
            newRow.append('')
        d.append(newRow)
    return (d, styles)


def style(table):
    """
    extract the style info and return a reportlab style list
    try to guess if a border and/or frame
    """
    
    styleList = []
    styleList.append( ('VALIGN',(0,0),(-1,-1),'TOP') )
    if styleutils.tableBorder(table):
        styleList.extend([('INNERGRID',(0,0),(-1,-1),0.25,colors.black),
                          ('BOX',(0,0),(-1,-1),0.25,colors.black),
                          ])
    return styleList

def scaleImages(data):
    for row in data:
        for cell in row:
            for (i,e) in enumerate(cell):
                if isinstance(e,Figure): # scale image to half size
                    cell[i] = Figure(imgFile = e.imgPath, captionTxt=e.captionTxt, captionStyle=e.cs, imgWidth=e.imgWidth/2.0,imgHeight=e.imgHeight/2.0, margin=e.margin, padding=e.padding,align=e.align)

            
def getColWidths(data, table=None, recursionDepth=0, nestingLevel=1):
    """
    the widths for the individual columns are calculated. if the horizontal size exceeds the pagewidth
    the fontsize is reduced 
    """

    if nestingLevel > 1:
        scaleImages(data)

    if not data:
        return None
       
    availWidth = printWidth - 12 # twice the total cell padding
    minwidths  = [ 0 for x in range(len(data[0]))]
    summedwidths = [ 0 for x in range(len(data[0]))]
    maxbreaks = [ 0 for x in range(len(data[0]))]
    for (i, row) in enumerate(data):        
        for (j,cell) in enumerate(row):
            cellwidth = 0
            try:
                colspan = getattr(table.children[i].children[j], 'colspan', 1)
            except IndexError: # caused by empty row b/c of rowspanning
                colspan = 1
            for e in cell:
                minw, minh = e.wrap(0,printHeight)
                maxw, maxh = e.wrap(availWidth, printHeight)
                minw += 6  # FIXME +6 is the cell padding we are using
                cellwidth += minw
                if maxh > 0:
                    rows = minh / maxh - 0.5 # approx. #linebreaks - smooted out - 
                else:
                    rows = 0
                if colspan > 1:                    
                    for offset in range(colspan):
                        minwidths[j+offset] = max(minw/colspan, minwidths[j+offset])
                        maxbreaks[j+offset] = max(rows/colspan, maxbreaks[j+offset])
                else:
                    minwidths[j] = max(minw, minwidths[j])
                    maxbreaks[j] = max(rows,maxbreaks[j])
            summedwidths[j] = max(cellwidth, summedwidths[j])

    parent_cells = table.getParentNodesByClass(Cell)
    parent_tables = table.getParentNodesByClass(Table)
    # nested tables in colspanned cell are expanded to full page width
    if nestingLevel == 2 and parent_cells and parent_tables and parent_cells[0].colspan == parent_tables[0].numcols:
        availWidth -= 8
    elif nestingLevel > 1:
        return minwidths

    remainingSpace = availWidth - sum(summedwidths)
    if remainingSpace < 0 : 
        remainingSpace = availWidth - sum(minwidths)
        if remainingSpace < 0:
            if recursionDepth == 0:
                scaleImages(data)
                return getColWidths(data, table=table, recursionDepth=1, nestingLevel=nestingLevel)
            else:
                return None
        else:
            _widths = minwidths
    else:
        _widths = summedwidths
        
    totalbreaks = sum(maxbreaks)
    if totalbreaks == 0:
        return minwidths
    else:
        widths = [ _widths[col] + remainingSpace*(breaks/totalbreaks) for (col,breaks) in enumerate(maxbreaks) ]
        return widths
    

def splitCellContent(data):
    # FIXME: this is a hotfix for tables which contain extremly large cells which cant be handeled by reportlab
    import math
    n_data = []
    splitCellCount = 14 # some arbitrary constant...: if more than 14 items are present in a cell, the cell is split into two cells in two rows
    for row in data:
        maxCellItems = 0
        for cell in row:
            maxCellItems = max(maxCellItems,len(cell))
        if maxCellItems > splitCellCount:
            for splitRun in range(int(math.ceil(maxCellItems / splitCellCount))):
                n_row = []
                for cell in row:
                    if len(cell) > splitRun*splitCellCount:
                        n_row.append(cell[splitRun*splitCellCount:(splitRun+1)*splitCellCount])
                    else:
                        n_row.append('')                   
                n_data.append(n_row)                    
        else:
            n_data.append(row)
    return n_data



def getContentType(t):
    nodeInfo = []
    for row in t.children:
        rowNodeInfo = []
        for cell in row:
            cellNodeTypes = []
            cellTextLen = 0
            for item in cell.children:
                if not item.isblocknode: # any inline node is treated as a regular TextNode for simplicity
                    cellNodeTypes.append(Text)
                else:
                    cellNodeTypes.append(item.__class__)            
                cellTextLen += len(item.getAllDisplayText())
            if cell.children:
                rowNodeInfo.append( (cellNodeTypes, cellTextLen) )
        if rowNodeInfo:
            nodeInfo.append(rowNodeInfo)
    return nodeInfo

def reformatTable(t, maxCols):
    nodeInfo = getContentType(t)
    numCols = maxCols
    numRows = len(t.rows)

    onlyTables = len(t.children) > 0 #if table is empty onlyTables and onlyLists are False
    onlyLists = len(t.children) > 0
    if not nodeInfo:
        onlyTables = False
        onlyLists = False
    for row in nodeInfo:
        for cell in row:
            cellNodeTypes, cellTextLen = cell
            if not all(nodetype==Table for nodetype in cellNodeTypes):
                onlyTables = False
            if not all(nodetype==ItemList for nodetype in cellNodeTypes):
                onlyLists = False
            
    if onlyTables and numCols > 1:
        log.info('got table only table - removing container')
        t = removeContainerTable(t)
    if onlyLists and numCols > 2 :
        log.info('got list only table - reducing columns to 2')
        t = reduceCols(t, colnum=2)
    if onlyLists:
        log.info('got list only table - splitting list items')
        t = splitListItems(t)
        pass
    return t

def splitListItems(t):
    nt = t.copy()
    nt.children = []
    for r in t.children:
        nr = Row()
        cols = []
        maxItems = 0
        for cell in r:           
            items = []
            for c in cell.children:
                if c.__class__ == ItemList:
                    items.extend(c.children)                   
            cols.append(items)
            maxItems = max(maxItems,len(items))
        for i in range(maxItems):            
            for (j,col) in enumerate(cols):
                try:
                    item = cols[j][i]
                    il = ItemList()
                    il.appendChild(item)
                    nc = Cell()                    
                    nc.appendChild(il)
                    nr.appendChild(nc)
                except IndexError:                    
                    nr.appendChild(Cell())
            nt.appendChild(nr)
            nr = Row()        
    return nt
    
def reduceCols(t, colnum=2):
    nt = t.copy()
    nt.children = []
    for r in t.children:
        nr = Row()
        for c in r:
            nc = c.copy()
            if len(nr.children) == colnum:
                nt.appendChild(nr)
                nr=Row()
            nr.appendChild(nc)
        if len(nr.children)>0:
            while len(nr.children) < colnum:
                nr.appendChild(Cell())
            nt.appendChild(nr)
    return nt

def removeContainerTable(containertable):
    newtables = []
    for row in containertable:
        for cell in row:
            for item in cell:
                if item.__class__ == Table:
                    newtables.append(item)
                else:
                    log.info("unmatched node:", item.__class__)
    return newtables


def tableBgStyle(table):
    bg_style = []    
    for (i, row) in enumerate(table.children):
        if not row.__class__ == Row:
            continue
        rgb = styleutils.rgbBgColorFromNode(row)
        if rgb:
            bg_style.append(('BACKGROUND', (0,i), (-1,i), colors.Color(rgb[0], rgb[1], rgb[2])))
        colspan_sum = 0
        for (j, cell) in enumerate(row.children):
            if not cell.__class__ == Cell:
                continue
            rgb = styleutils.rgbBgColorFromNode(cell)
            colspan = cell.colspan
            start_col = colspan_sum
            end_col = colspan_sum + colspan -1
            colspan_sum += colspan
            rowspan = cell.rowspan
            if rgb:
                bg_style.append(('BACKGROUND', (start_col,i), (end_col,i+rowspan-1), colors.Color(rgb[0], rgb[1], rgb[2])))
    return bg_style
