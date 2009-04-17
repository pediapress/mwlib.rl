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
You need to have setuptools/easy_install installed. Installation
should be as easy as typing::
  
  $ easy_install mwlib.rl

If you don't have setuptools installed, download the source package, 
unpack it and run::

  $ python setup.py install

(this will also install setuptools)

*texvc*
 You have to make sure that *texvc* is in your system PATH. *texvc* 
 is supplied by the mediawiki installation. It should be located in
 the following directory: mediawiki_install_path/math

 texvc also requires:
 * LaTeX
 * dvipng
 * AMS* packages for LaTeX (maybe included in LaTex distribution)

You will also need:

*mwlib*
  mwlib parses mediawiki articles

*pygments*
  for source code formatting
  http://pygments.org/ (debian packet:  python-pygments)

*fribidi*
  package for handling bidirectional (right-to-left / left-to-right) text. gnu freebidi and the python bindings are needed
  http://fribidi.freedesktop.org/wiki/  (debian packages: libfribidi0 and libfribidi-dev)
  http://pyfribidi.sourceforge.net/index.html (debian packages: python-pyfribidi)
  
*ploticus*
  package which is used to render timelines 
  http://ploticus.sourceforge.net/doc/welcome.html (debian package: ploticus)

PDF Customization
======================================================================

Customizing the resulting PDFs is possible by adding a custom configuration file. 
The file needs to named customconfig.py and should reside next to the pdfstyles.py file. 
Basically you can override anything in the pdfstyles.py file with your custom configuration. 
Any changes need to be done with care in order not to break things!
Check the pdfstyles.py file for more information.

    
Contact/Further Information
======================================================================
For further information please visit our trac instance running at
http://code.pediapress.com
The current development version can also be found there.

ChangeLog
======================================================================

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
