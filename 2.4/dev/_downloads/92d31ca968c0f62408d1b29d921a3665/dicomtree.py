# Copyright pydicom authors 2019. See LICENSE file for details
"""
=========================================
Show a dicom file using hierarchical tree
=========================================
Show a dicom file using a hierarchical tree in a graphical window.

sudo apt install tix-dev
sudo pip install -U pydicom
python3 dicomtree.py file.dcm
Or in file browser, right click on file.dcm, open with custom command:
python3 dicomtree.py
"""


import tkinter.tix as tkinter_tix

print(__doc__)

usage = "Usage: python dicomtree.py dicom_filename"


def RunTree(w, filename):
    top = tkinter_tix.Frame(w, relief=tkinter_tix.RAISED, bd=1)
    tree = tkinter_tix.Tree(top, options="hlist.columns 2")
    tree.pack(expand=1, fill=tkinter_tix.BOTH, padx=10, pady=10,
              side=tkinter_tix.LEFT)
    # print(tree.hlist.keys())   # use to see the available configure() options
    tree.hlist.configure(bg='white', font='Courier 10', indent=30)
    tree.hlist.configure(selectbackground='light yellow', gap=150)

    box = tkinter_tix.ButtonBox(w, orientation=tkinter_tix.HORIZONTAL)
    # box.add('ok', text='Ok', underline=0, command=w.destroy, width=6)
    box.add('exit', text='Exit', underline=0, command=w.destroy, width=6)
    box.pack(side=tkinter_tix.BOTTOM, fill=tkinter_tix.X)
    top.pack(side=tkinter_tix.TOP, fill=tkinter_tix.BOTH, expand=1)
    # https://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
    tree.bind_all('<MouseWheel>', lambda event:  # Wheel in Windows
                  tree.hlist.yview_scroll(int(-1 * event.delta / 120.),
                                          "units"))
    tree.bind_all('<Button-4>', lambda event:  # Wheel up in Linux
                  tree.hlist.yview_scroll(int(-1), "units"))
    tree.bind_all('<Button-5>', lambda event:  # Wheel down in Linux
                  tree.hlist.yview_scroll(int(+1), "units"))

    show_file(filename, tree)


def show_file(filename, tree):
    tree.hlist.add("root", text=filename)
    ds = pydicom.dcmread(filename)
    ds.decode()  # change strings to unicode
    recurse_tree(tree, ds, "root", False)
    tree.autosetmode()


def recurse_tree(tree, dataset, parent, hide=False):
    # order the dicom tags
    for data_element in dataset:
        node_id = parent + "." + hex(id(data_element))
        if isinstance(data_element.value, str):
            tree.hlist.add(node_id, text=str(data_element))
        else:
            tree.hlist.add(node_id, text=str(data_element))
        if hide:
            tree.hlist.hide_entry(node_id)
        if data_element.VR == "SQ":  # a sequence
            for i, dataset in enumerate(data_element.value):
                item_id = node_id + "." + str(i + 1)
                sq_item_description = data_element.name.replace(
                    " Sequence", "")  # XXX not i18n
                item_text = "{0:s} {1:d}".format(sq_item_description, i + 1)
                tree.hlist.add(item_id, text=item_text)
                tree.hlist.hide_entry(item_id)
                recurse_tree(tree, dataset, item_id, hide=True)


if __name__ == '__main__':
    import sys
    import pydicom

    if len(sys.argv) != 2:
        print("Please supply a dicom file name:\n")
        print(usage)
        sys.exit(-1)
    root = tkinter_tix.Tk()
    root.geometry("{0:d}x{1:d}+{2:d}+{3:d}".format(1200, 900, 0, 0))
    root.title("DICOM tree viewer - " + sys.argv[1])

    RunTree(root, sys.argv[1])
    root.mainloop()
