#! /usr/bin/env python

import os

def get_mo_files():
    mo_files = []
    for dirpath, dirnames, filenames in os.walk('mwlib/rl/locale/'):
        for f in filenames:
            file_base, file_ext = os.path.splitext(f)
            if file_ext == '.mo':
                mo_files.append(os.path.join(dirpath, f))
    return mo_files

def main():
    files = [x.strip() for x in os.popen("hg manifest")]
    files.append("README.html")
    def remove(n):
        try:
            files.remove(n)
        except ValueError:
            pass
    
    remove("make_manifest.py")
    remove(".hgtags")
    remove("Makefile")
    
    files.extend(get_mo_files())
    
    files.sort()

    f = open("MANIFEST.in", "w")
    for x in files:
        f.write("include %s\n" % x)
    f.close()


if __name__=='__main__':
    main()
