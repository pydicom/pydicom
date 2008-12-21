# myprint.py
"""Example of printing a dataset in your own format"""
# Copyright (c) 2008 Darcy Mason
# released under GPL license

def myprint(dataset, indent=0):
    """Go through all item in the dataset and print.
    Modelled after Dataset._PrettyStr()
    """
    dont_print = ['Pixel Data', 'File Meta Information Version']

    keylist = dataset.keys()
    keylist.sort()
    indentStr = "   " * indent
    nextIndentStr = "   " *(indent+1)
    for k in keylist:
        attr = dataset[k]
        if attr.VR == "SQ":   # a sequence
            print indentStr, attr.description()
            for ds in attr.value:
                myprint(ds, indent+1)
                print nextIndentStr + "---------"
        else:
            if attr.description() in dont_print:
                print "   ---- not printed ----   "
            else:            
                print indentStr, attr.description(), "=", repr(attr.value) # use str(attr.value) here to skip quotes around items, etc.

if __name__ == "__main__":
    import dicom
    ds = dicom.ReadFile("rtplan.dcm")
    myprint(ds)