# Copyright pydicom authors 2019. See LICENSE file for details
"""
=========================================
Show a dicom file using hierarchical tree
=========================================
Show a dicom file using a hierarchical tree in a graphical window.

"""
from pathlib import Path
import sys

import tkinter as tk
from tkinter import ttk

import pydicom


print(__doc__)


def build_tree(
    tree: ttk.Treeview, ds: pydicom.Dataset, parent: str | None = None
) -> None:
    """Build out the tree.

    Parameters
    ----------
    tree : ttk.Treeview
        The treeview object.
    ds : pydicom.dataset.Dataset
        The dataset object to add to the `tree`.
    parent : str | None
        The item ID of the parent item in the tree (if any), default ``None``.
    """
    # For each DataElement in the current Dataset
    for idx, elem in enumerate(ds):
        tree_item = tree.insert("", tk.END, text=str(elem))
        if parent:
            tree.move(tree_item, parent, idx)

        if elem.VR == "SQ":
            # DataElement is a sequence, containing 0 or more Datasets
            for seq_idx, seq_item in enumerate(elem.value):
                tree_seq_item = tree.insert(
                    "", tk.END, text=f"{elem.name} Item {seq_idx + 1}"
                )
                tree.move(tree_seq_item, tree_item, seq_idx)

                # Recurse into the sequence item(s)
                build_tree(tree, seq_item, tree_seq_item)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please supply the path to a DICOM file: python dicomtree.py path")
        sys.exit(-1)

    # Read the supplied DICOM dataset
    path = Path(sys.argv[1]).resolve(strict=True)
    ds = pydicom.dcmread(path)

    # Create the root Tk widget
    root = tk.Tk()
    root.geometry("1200x900")
    root.title(f"DICOM tree viewer - {path.name}")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    # Use a monospaced font
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", font=("Courier", 12))

    # Create the tree and populate it
    tree = ttk.Treeview(root)
    build_tree(tree, ds, None)
    tree.grid(row=0, column=0, sticky=tk.NSEW)

    # Start the DICOM tree widget
    root.mainloop()
