#! /usr/bin/env python

import os
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup

install_requires=["mwlib>=0.3.0"]

def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

setup(
    name="mwlib.rl",
    version="0.3.0",
    entry_points = dict(console_scripts=['mw-pdf = mwlib.rl.apps:pdf',
                                         'mw-pdfall = mwlib.rl.apps:pdfall',
                                         'mw-pdfcollection = mwlib.rl.apps:pdfcollection',
                                         #'mw-zip2pdf = mwlib.rl.apps:zip2pdf',
                                         ]),
    install_requires=install_requires,

    packages=["mwlib", "mwlib.rl", "mwlib.fonts"],
    namespace_packages=['mwlib'],
    zip_safe = False,
    include_package_data = True,
    url = "http://code.pediapress.com/",
    description="generate pdfs from mediawiki markup",
    long_description = read_long_description(),
    license="BSD License",
    maintainer="pediapress.com",
    maintainer_email="info@pediapress.com",

)

