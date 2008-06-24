"""make py.test skip the build directory"""

import py

class Exclude(py.test.collect.Directory):
    def recfilter(self, path):
        if path.check(dir=1, dotfile=0):
            if path.basename=='build':
                return False
        return super(Exclude, self).recfilter(path)
    
Directory = Exclude
