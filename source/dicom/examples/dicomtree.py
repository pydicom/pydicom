# dicomtree.py
"""Show a dicom file using a hierarchical tree in a graphical window"""
# Copyright (c) 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

# Modeled after Tree.py at http://mail.python.org/pipermail/python-checkins/2001-March/016462.html

usage = "Usage: python dicomtree.py dicom_filename"

import Tix

def RunTree(w, filename):
    top = Tix.Frame(w, relief=Tix.RAISED, bd=1)
    tree = Tix.Tree(top, options="hlist.columns 2")
    tree.pack(expand=1, fill=Tix.BOTH, padx=10, pady=10, side=Tix.LEFT)
    # print tree.hlist.keys()   # use to see the available configure() options
    tree.hlist.configure(bg='white', font='Courier 10', indent=30)
    tree.hlist.configure(selectbackground='light yellow', gap=150)
    
    box = Tix.ButtonBox(w, orientation=Tix.HORIZONTAL)
    box.add('ok', text='Ok', underline=0, command=w.destroy, width=6)
    box.add('exit', text='Exit', underline=0, command=w.destroy, width=6)
    box.pack(side=Tix.BOTTOM, fill=Tix.X)
    top.pack(side=Tix.TOP, fill=Tix.BOTH, expand=1)

    show_file(filename, tree)

def show_file(filename, tree):
    tree.hlist.add("root", text=filename)
    ds = dicom.ReadFile(sys.argv[1])
    ds.decode()
    recurse_tree(tree, ds, "root", False)
    tree.autosetmode()

def recurse_tree(tree, ds, parent, hide=False):
    # order the dicom tags
    keylist = ds.keys()
    keylist.sort()

    for k in keylist:
        attr = ds[k]
        node_id = parent + "." + hex(id(attr))
        if type(attr.value) is PersonNameUnicode:
            tree.hlist.add(node_id, text=attr.value)
        else:
            tree.hlist.add(node_id, text=str(attr))
        if hide:
            tree.hlist.hide_entry(node_id)
        if attr.VR == "SQ":   # a sequence
            for i, dataset in enumerate(attr.value):
                item_id = node_id + "." + str(i+1)
                sq_item_description = attr.description().replace(" Sequence", "") # XXX not i18n
                item_text = "%s %d" % (sq_item_description, i+1)
                tree.hlist.add(item_id, text=item_text)
                tree.hlist.hide_entry(item_id)
                recurse_tree(tree, dataset, item_id, hide=True)

if __name__ == '__main__':
    import sys
    import dicom
    if len(sys.argv) != 2:
        print "Please supply a dicom file name:\n"
        print usage
        sys.exit(-1)
    root = Tix.Tk()
    root.geometry("%dx%d%+d%+d" % (800, 600, 0, 0))
    
    RunTree(root, sys.argv[1])
    root.mainloop()
