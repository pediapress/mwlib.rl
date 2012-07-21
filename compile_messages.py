#! /usr/bin/env python

import pkg_resources  # needed for 'pip install -e'
from l10n import compile_messages

if __name__ == '__main__':
    compile_messages(localedir='mwlib/rl/locale')
