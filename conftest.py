import os
from mwlib import _version, _extversion
def pytest_report_header(config):
    return "mwlib %s in %s\nmwlib.ext %s in %s" % (
        _version.version,
        os.path.dirname(_version.__file__),
        _extversion.version,
        os.path.dirname(_version.__file__))
