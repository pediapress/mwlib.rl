#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib import advtree
from mwlib.advtree import Paragraph

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


def buildAdvancedTree(root):
    advtree.extendClasses(root) 
    advtree.fixTagNodes(root)
    advtree.removeNodes(root)
    advtree.removeNewlines(root)
    advtree.fixStyles(root) 
    fixLists(root)
