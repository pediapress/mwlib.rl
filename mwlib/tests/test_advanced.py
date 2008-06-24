#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.


from renderhelper import renderMW

# node combinations: Table, Paragraph, PreFormatted, Emphasized, Definitionlist, Indented, Blockquote, Link,  URL, NamedURL,
# CategoryLink, LangLink, Image, Gallery, Source, Code, Teletyped, BR, References, Div, Span, ItemList, Math
# styles: Emphasized, Strong, overline, underline, sub, sup, small, big, cite, Center, Strike


nastyChars = u'%(stylestart)sUmlauts: äöüÖÄÜß chinese: 应急机制构筑救灾长城 arabic: عيون المواقع : صحافة و إعلام %(styleend)s'
links = u"Link: [[MWArticleTitle]] plus anchor text: [[MWArticleTitle|%(nasty)s]] NamedURL: [http://example.com]  plus anchor text: [http://example.com %(nasty)s] URL: http://example.com" % {'nasty':nastyChars}


def get_styled_text(txt):
    txt_list = []
    for style in ["", "''", "'''", '<u>']:
        if style.find('<') == -1:
            styleend = style
        else:
            styleend = style[0] + '/' + style[1:]
        t = txt % { 'stylestart' : style,
                      'styleend': styleend}    
        txt_list.append(t)
    return txt_list

def test_list_and_tables_3():
    # oversized table -> nested table is rendered in plain-text
    txt = '''
{| class="prettytable"
|-
|
* lvl 1 %(links)s
* lvl 1
** lvl 2 %(links)s
** lvl 2
*** <math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>
*** %(links)s
** lvl 2
** lvl 2
* lvl 1
|
{| class="prettytable"
|-
|
# lvl 1 
# lvl 1
## lvl 2
## lvl 2 
### <tt>teletyped text</tt>
### lvl 3
## lvl 2
## lvl 2
# lvl 1
| text
|-
| text || <math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>
|}
|-
|text after nesting || %(links)s
|}
''' % { 'links':links }
    renderMW('\n\n'.join(get_styled_text(txt)), 'lists_and_tables_3')

def test_list_and_tables_2():
    # oversized table -> nested table is rendered in plain-text
    txt = '''
{| class="prettytable"
|-
|
* lvl 1 %(links)s
* lvl 1
** lvl 2 %(links)s
** lvl 2
*** <math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>
*** %(links)s
** lvl 2
** lvl 2
* lvl 1
|
{| class="prettytable"
|-
|
# lvl 1 %(links)s
# lvl 1
## lvl 2
## lvl 2 %(links)s
### <tt>teletyped text</tt>
### %(links)s
## lvl 2
## lvl 2
# lvl 1
| text
|-
| text || <math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>
|}
|-
|text after nesting || %(links)s
|}
''' % { 'links':links }
    renderMW('\n\n'.join(get_styled_text(txt)), 'lists_and_tables_2')

def test_list_and_tables_1():
    txt = '''
some text outside a table
   
{| class="prettytable"
|-
|
* lvl 1 %(nasty)s
* lvl 1
** lvl 2 %(nasty)s
** lvl 2
*** lvl 3
*** %(nasty)s
** lvl 2
** lvl 2
* lvl 1
|
# lvl 1 %(nasty)s
# lvl 1
## lvl 2
## lvl 2 %(nasty)s
### lvl 3
### %(nasty)s
## lvl 2
## lvl 2
# lvl 1
|}
''' % { 'nasty':nastyChars }
    renderMW('\n\n'.join(get_styled_text(txt)), 'lists_and_tables_1')


def test_link_and_lists():
    txt = '''
== Lists ==

# %(links)s
# plain text
## lvl2: %(links)s
## lvl 2: plain text

* %(links)s
* plain text
** lvl2: %(links)s
** lvl 2: plain text
''' % {'links': links}

    renderMW('\n\n'.join(get_styled_text(txt)), 'links_and_lists')

def test_link_in_table():
    txt = '''
== Table ==

{| class="prettytable"
|-
| 1.1 || %(links)s
|-
| %(links)s || 2.2
|}

{| class="prettytable"
|-
| colspan="2" | colspanned cell
|-
| 2.1 || 2.2
|-
| colspan="2" |
{| class="prettytable"
|-
| %(links)s || nested
|-
| bla || blub
|}

|}
''' % {'links': links}

    renderMW('\n\n'.join(get_styled_text(txt)), 'links_and_tables')


def test_math_advanced():

    txt = '''
inline math follows <math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math> and now text.

;indented math in definition list
:<math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>

math in table (test down-scaling of formula):

{| class="prettytable"
|-
|<math>-2=\sqrt[3]{-8}\ne\sqrt[6]{(-8)^2}=\sqrt[6]{64}=+2.</math>
|text
|-
| text
| text
|}
'''
    renderMW(txt, 'math_advanced')

def test_entity_links():
    txt = '[http://toolserver.org/~magnus/geo/geohack.php?pagename=HMS_Cardiff_(D108)&params=-51.783600_N_-58.467786_E_]'

    renderMW(txt, 'links_entities')

def test_category_links():
    """test for http://code.pediapress.com/wiki/ticket/177"""
    txt = '[[:Category:foo bar]]'
    renderMW(txt, 'links_entities')
