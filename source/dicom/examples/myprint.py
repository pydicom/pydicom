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
        data_element = dataset[k]
        if data_element.VR == "SQ":   # a sequence
            print indentStr, data_element.description()
            for ds in data_element.value:
                myprint(ds, indent+1)
                print nextIndentStr + "---------"
        else:
            if data_element.description() in dont_print:
                print "   ---- not printed ----   "
            else:            
                print indentStr, data_element.description(), "=", repr(data_element.value) # use str(data_element.value) here to skip quotes around items, etc.

if __name__ == "__main__":
    import dicom
    ds = dicom.ReadFile("rtplan.dcm")
    myprint(ds)