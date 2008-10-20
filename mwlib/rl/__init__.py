try:
    import mwlib.ext #try to use bundled version of reportlab
except ImportError:
    pass

import gettext
import os

localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
gettext.install('mwlib.rl', localedir, unicode=True)
