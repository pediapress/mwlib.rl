.. -*- mode: rst; coding: utf-8 -*-

======================================================================
mwlib.rl - reportlab pdf writer 
======================================================================


Overview
======================================================================
mwlib.rl provides a library for writing pdf documents from mediawiki_ 
articles which were parsed by the mwlib library. 


Installation
======================================================================
Please read http://mwlib.readthedocs.org/en/latest/installation.html
for installation instructions.

PDF Customization
======================================================================

Customizing the resulting PDFs is possible by adding a custom configuration file. 
The file needs to be named customconfig.py and should be located in your PYTHONPATH.
Basically you can override anything in the pdfstyles.py file with your custom configuration. 
Any changes need to be done with care in order not to break things!
Check the pdfstyles.py file for more information.

Also check the customnodetransformer.py file for more options for customization.

Font configuration:
-------------------

The font configuration can be changed in fontconfig.py. For the default configuration to 
work properly it is necessary to install a couple of fonts. If these fonts are not installed 
built-in Adobe fonts are used where necessary.

The following fonts need to be installed:
AR PL UMing HK, Ezra SIL, Nazli, UnBatang, Arundina Serif, Lohit Telugu, Sarai, Lohit Punjabi, 
Lohit Oriya, AnjaliOldLipi, Kedage, LikhanNormal, Lohit Tamil, Linux Libertine

These fonts are contained in the following debian (meta-)packages:
ttf-indic-fonts, ttf-unfonts, ttf-farsiweb, ttf-arphic-uming, ttf-sil-ezra, ttf-thai-arundina, 
linux-libertine

After the font installation a directory "mwlibfonts" needs to be created in the home directory.
All fonts need to be symlinked to the appropriate directories (see fontconfig.py).
    
Contact/Further Information
======================================================================
For further information please visit our trac instance running at
http://code.pediapress.com
The current development version can also be found there.

ChangeLog
======================================================================
2012-05-08 release 0.12.11
--------------------------
- fix pypi url used by tox
- workaround for protocol-less-urls that causes PDFs to refuse printing
- Translation updates from translatewiki.net
- make compile_mesages work when using pip -e
- fix zero divison error
- tweak param
- improve rowspan-splitting by taking approx. table width into account
- be a bit more conservative in make clean
- fix: correctly skip multiple occurences of broken image
- add fake zero-width-spaces for cjk text inside non-cjk wikis

2011-12-13 release 0.12.10
--------------------------
- allow scaling of floating math formulas
- allow floating of longer math formulas
- remove space after reference
- correct article ID: fixes printing problems on adobe reader
- use image blacklisting for non-strict servers instead of "nofilter"

2011-11-16 release 0.12.9
----------------------------
- add rtl support
- fix for https://bugzilla.wikimedia.org/show_bug.cgi?id=30548
- fix for https://bugzilla.wikimedia.org/show_bug.cgi?id=30515
- fix fail_safe_rendering for complex article titles (https://bugzilla.wikimedia.org/show_bug.cgi?id=30515)

2011-03-16 release 0.12.8
---------------------------
- fix for multiple table captions
- use lvl 1 headings in PDF bookmarks
- fix: use correct pagesize for TOC
- make chapter rule color configurable
- fix: use correct page template
- fix page header (#704)
- scale oversized math formulas
- fix translations
- add config option to suppress URL->reference section in tables
- handle Abbreviation node
- make math formula size limits configurable

2010-10-29 release 0.12.7
-------------------------
- setup.py: require mwlib 0.12.14.
- add localisation needed to fix #905
- fix for 901 / transparent image bug in adobe reader
- manually fetch hu translations from translatewiki
- fix for #903
- correct fontswitchter import
- add url blacklist

2010-10-11 release 0.12.6
-------------------------
- fix for image positioning: align=none -> non-inline
- change hungarian localisation string
- customflowables: fix resizeInlineImage method.
- Localisation updates from translatewiki.net
- fix for table cell dims (#842)
- fix for #850
- dont inherit color for table/row/cell
- add spanish translations
- make figure border color customizable
- fix for reference handling
- fix for TOC
- fix typo
- formulas resulting in huge image are skipped. avoid problems with old latex installs
- use text color for inline nodes
- fix for #844: dont float source code and preformatted nodes.
- switch to ez_setup.py from setuptools-0.6c11
- fix for #861
- fix for table header cell content is now correctly aligned and bold
- scale Source nodes
- added more translations thanks to John West
- add arabic translation thanks to John West


2010-7-16  release 0.12.5
-------------------------
- Localisation updates from Translatewiki.net
- make horizontal rule below article title configurable
- add gettext requirement to README. thanks to Daniel Weuthen
- fix for 704
- allow custom list item symbol
- add translateable strings
- use correct font for sections
- fix for tables
- add translatable string "Index"
- scale down preformatted nodes if they exceed the page width
- added Greek l10n for "Appendix", corrected the one for "Skipping Articles!"
- add update target
- stretch tables with: width=100%
- fix img alignment
- updates for fontconfig
- fix for #809
- translate Contents in hu
- fix flipped page_margins. fix for custom pagesizes
- use vertical alignment of table cells
- add test for fake hypenation
- fix fake hyphenation (#781)
- fix wording
- more L10N fixes
- fix po file for language id
- use text color
- fix handling of colspan
- handle abbr tag
- fix for galleries: #270
- move tests into top-level directory. py.test 1.1 is otherwise confused
- improve image alignment
- use render_caption property. small refactoring of getTableSize
- ignore hiero tags
- use refactored style handling
- support html attrs for list styles
- support roman and alpha ordered list styles
- remove inter-pdf link arrows
- make compatible with old imagemagick versions.
- allow custom title page images

2009-10-20 release 0.12.4
-------------------------

- no escaping in titlepage footer
- no escaping for pagefooter
- define treecleaner skip methods in pdfstyles to allow customization.
- allow higher resolution math images by setting environment variable MATH_RESOLUTION
- localize license title
- fix for #696
- fix for #699
- the code tag is now correctly handled as an inline element
- fix unicode decode error when using fribidi
- fix problem with pyfribidi
- fix for invalid values of the gallery perrow attribute
- no pagebreaks in nested tables
- ensure pagebreaks before tables if space is sparse
- use FreeSerif for Cyrillic and Greek
- fix for sections inside tables. add cjk handling to zh languages
- switch from DejaVu to FreeFont
- fix span checking for tables

2009-08-25 release 0.12.3
-------------------------
* rewrite table rendering code
* make it compatible with latest mwlib.ext

2009-08-17 release 0.12.1
-------------------------
* fixes
* add Table of Contents
* improve support for CJK languages
* fix printing problems
* use formatter class to style text
* add CustomNodeTransformer

2009-05-06 release 0.11.3
-------------------------
* fix

2009-05-06 release 0.11.2
-------------------------
* fixes

2009-05-05 release 0.11.1
-------------------------
* add image license and contributors section to the end of the PDF
* fixes

2009-04-17 release 0.10.2
-------------------------
* show pdf creation date on title page
* fixes

2009-04-09 release 0.10.1
-------------------------
* move contributors and article source to the end of the pdf
* basic support for timelines
* use mwlib > 0.10
* other fixes


2009-03-05 release 0.9.10
-------------------------

* insert conditional pagebreaks before articles
* minor fixes


2009-03-02 release 0.9.9
------------------------

* minor fixes


2009-02-19 release 0.9.8
------------------------

* xmlescape title and subtitle

2009-02-18 release 0.9.7
------------------------

* add translations
* improve styling

2009-02-03 release 0.9.4
------------------------

* improve rendering of galleries
* improve page breaks
* use new image scaling method from mwlib


2009-02-03 release 0.9.3
------------------------

* use correct alignment and background color for table cells
* text alignment is now justified by default
* workaround for greyscale images with alphachannel (#429)

License
======================================================================
Copyright (c) 2007, 2008 PediaPress GmbH

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above
  copyright notice, this list of conditions and the following
  disclaimer in the documentation and/or other materials provided
  with the distribution. 

* Neither the name of PediaPress GmbH nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. _mediawiki: http://www.mediawiki.org
