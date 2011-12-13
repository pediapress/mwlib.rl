#! /usr/bin/env python

# Copyright (c) PediaPress GmbH
# See README.txt for additional licensing information.

import os

try:
    from setuptools import setup, Extension
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, Extension

install_requires = ["mwlib>=0.12.14, <0.14", "pygments>=1.0", "mwlib.ext>=0.9.3, <0.14"]


def get_version():
    d = {}
    execfile("mwlib/rl/_version.py", d, d)
    return str(d["version"])


def main():
    if os.path.exists('Makefile'):
        # this is a git checkout
        print 'Running make'
        os.system('make')

    setup(
        name="mwlib.rl",
        version=get_version(),
        entry_points={
            'mwlib.writers': ['rl = mwlib.rl.rlwriter:writer'],
        },
        install_requires=install_requires,
        packages=["mwlib", "mwlib.rl", "mwlib.fonts"],
        namespace_packages=['mwlib'],
        zip_safe=False,
        include_package_data=True,
        url="http://code.pediapress.com/",
        description="generate pdfs from mediawiki markup",
        long_description=open("README.rst").read(),
        license="BSD License",
        maintainer="pediapress.com",
        maintainer_email="info@pediapress.com")


if __name__ == '__main__':
    main()
