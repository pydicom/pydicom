# dicomtree.py
"""Show a dicom file using a hierarchical tree in a graphical window"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

usage = "Usage: python dicomtree.py dicom_filename"

import Tix


def RunTree(w, filename):
    top = Tix.Frame(w, relief=Tix.RAISED, bd=1)
    tree = Tix.Tree(top, options="hlist.columns 2")
    tree.pack(expand=1, fill=Tix.BOTH, padx=10, pady=10, side=Tix.LEFT)
    # print(tree.hlist.keys())   # use to see the available configure() options
    tree.hlist.configure(bg='white', font='Courier 10', indent=30)
    tree.hlist.configure(selectbackground='light yellow', gap=150)

    box = Tix.ButtonBox(w, orientation=Tix.HORIZONTAL)
    # box.add('ok', text='Ok', underline=0, command=w.destroy, width=6)
    box.add('exit', text='Exit', underline=0, command=w.destroy, width=6)
    box.pack(side=Tix.BOTTOM, fill=Tix.X)
    top.pack(side=Tix.TOP, fill=Tix.BOTH, expand=1)

    show_file(filename, tree)


def show_file(filename, tree):
    tree.hlist.add("root", text=filename)
    ds = dicom.read_file(sys.argv[1])
    ds.decode()  # change strings to unicode
    recurse_tree(tree, ds, "root", False)
    tree.autosetmode()


def recurse_tree(tree, dataset, parent, hide=False):
    # order the dicom tags
    for data_element in dataset:
        node_id = parent + "." + hex(id(data_element))
        if isinstance(data_element.value, unicode):
            tree.hlist.add(node_id, text=unicode(data_element))
        else:
            tree.hlist.add(node_id, text=str(data_element))
        if hide:
            tree.hlist.hide_entry(node_id)
        if data_element.VR == "SQ":   # a sequence
            for i, dataset in enumerate(data_element.value):
                item_id = node_id + "." + str(i + 1)
                sq_item_description = data_element.name.replace(" Sequence", "")  # XXX not i18n
                item_text = "{0:s} {1:d}".format(sq_item_description, i + 1)
                tree.hlist.add(item_id, text=item_text)
                tree.hlist.hide_entry(item_id)
                recurse_tree(tree, dataset, item_id, hide=True)

if __name__ == '__main__':
    import sys
    import dicom
    if len(sys.argv) != 2:
        print("Please supply a dicom file name:\n")
        print(usage)
        sys.exit(-1)
    root = Tix.Tk()
    root.geometry("{0:d}x{1:d}+{2:d}+{3:d}".format(800, 600, 0, 0))

    RunTree(root, sys.argv[1])
    root.mainloop()
