# codify.py
"""Produce runnable python code which can recreate DICOM objects or files.

Can run as a script to produce code for an entire file,
or import and use specific functions to provide code for pydicom DICOM classes

"""
# Copyright (c) 2013 Darcy Mason
# This file is part of pydicom, released under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# Run this from the same directory as a "base" dicom file and
# this code will output to screen the dicom parameters like:
#    ds.PatientName = 'TEST'
# etc for all parameters in the file.
# This can then be pasted into a python file and parameters edited as necessary
# to create a DICOM file from scratch

import sys
import dicom
from dicom.datadict import dictionary_keyword

usage = """
python codify.py dicomfilename

Output the python statements which can recreate a DICOM file
"""

line_term = "\n"


def code_imports():
    """Code the import statements needed by other codify results

    :return: a string of import statement lines

    """
    line1 = "import dicom"
    line2 = "from dicom.dataset import Dataset"
    line3 = "from dicom.sequence import Sequence"
    return line_term.join((line1, line2, line3))


def tag_repr(tag):
    """String of tag value as (0xgggg, 0xeeee)"""
    return "(0x{group:04x}, 0x{elem:04x})".format(group=tag.group,
                                                  elem=tag.element)


def code_dataelem(dataelem, dataset_name="ds"):
    """Code lines for a single DICOM data element

    :arg dataelem: the DataElement instance to turn into code
    :arg dataset_name: variable name of the Dataset containing dataelem
    :return: a string containing code to recreate the data element
             If the data element is a sequence, calls code_sequence

    """
    if dataelem.VR == "SQ":
        return code_sequence(dataelem, dataset_name)

    # If in DICOM dictionary, set using the keyword
    # If not (e.g. is private element), set using add_new method
    have_keyword = True
    try:
        keyword = dictionary_keyword(dataelem.tag)
    except KeyError:
        have_keyword = False

    valuerep = repr(dataelem.value)
    if have_keyword:
        format_str = "{ds_name}.{keyword} = {valuerep}"
        line = format_str.format(ds_name=dataset_name,
                                 keyword=keyword,
                                 valuerep=valuerep)
    else:
        format_str = "{ds_name}.add_new({tag}, '{VR}', {valuerep})"
        line = format_str.format(ds_name=dataset_name,
                                 tag=tag_repr(dataelem.tag),
                                 VR=dataelem.VR,
                                 valuerep=valuerep)
    return line


def default_name_filter(name):
    """Callable to reduce some names in code to more readable short form

    :arg name: a sequence variable name or sequence item name
    :return: a shorter version of name if a known conversion,
             else return original name

    """
    name = name.replace("Sequence", "_seq")
    name = name.replace("ControlPoint", "cp")
    name = name.replace("ReferencedDoseReference", "refd_dose_ref")
    return name


def code_sequence(dataelem, dataset_name="ds",
                  name_filter=default_name_filter):
    """Code lines for recreating a Sequence data element

    :arg dataelem: the DataElement instance of the Sequence
    :arg dataset_name: variable name of the dataset containing the Sequence
    :arg name_filter: a callable taking a sequence name or sequence item name,
                      and returning a shorter name for easier code reading
    :return: a string containing code lines to recreate a DICOM sequence

    """
    lines = []
    seq = dataelem.value
    seq_name = dataelem.name
    seq_item_name = seq_name.replace(' Sequence', '')
    seq_keyword = dictionary_keyword(dataelem.tag)

    # Create comment line to document the start of Sequence
    lines.append('')
    lines.append("# " + seq_name)

    # Code line to create a new Sequence object
    if name_filter:
        seq_var = name_filter(seq_keyword)
    lines.append(seq_var + " = Sequence()")

    # Code line to add the sequence to its parent
    lines.append(dataset_name + "." + seq_keyword + " = " + seq_var)

    # Code lines to add sequence items to the Sequence
    for i, ds in enumerate(seq):

        # Code comment line to mark start of sequence item
        lines.append('')
        lines.append("# " + seq_name + ": " + seq_item_name + " " + str(i + 1))

        # Determine the variable name to use for the sequence item (dataset)
        ds_name = seq_var + "_item" + str(i)
        if name_filter:
            ds_name = name_filter(ds_name)

        # Code the sequence item
        lines.append(code_dataset(ds, ds_name))

        # Code the line to append the item to its parent sequence
        lines.append(seq_var + ".append(" + ds_name + ")")
    # Join the lines and return a single string
    return line_term.join(lines)


def code_dataset(ds, dataset_name="ds"):
    """Return python code lines for import statements needed by other code

    :return: a list of code lines containing import statements

    """
    lines = []
    lines.append(dataset_name + " = Dataset()")
    for dataelem in ds:
        lines.append(code_dataelem(dataelem, dataset_name))
    return line_term.join(lines)


def code_file(filename):
    """Write a complete source code file to recreate a DICOM file

    :arg filename: complete path and filename of a DICOM file to convert

    :return: a string containing code lines to recreate entire file

    """
    lines = []

    ds = dicom.read_file(filename, force=True)

    lines.append("# Coded version of DICOM file '{0}'".format(filename))
    lines.append("# Produced by pydicom codify util script")
    lines.append(code_imports())
    lines.append('')
    lines.append("# File meta info data elements")
    lines.append(code_dataset(ds.file_meta, "file_meta"))
    lines.append('')

    lines.append("# Main data elements")
    lines.append(code_dataset(ds))
    lines.append('')
    lines.append("ds.file_meta = file_meta")
    lines.append("ds.is_implicit_VR = " + str(ds.is_implicit_VR))
    lines.append("ds.is_little_endian = " + str(ds.is_little_endian))

    return line_term.join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print usage
        sys.exit(-1)

    filename = sys.argv[1]
    print code_file(filename)
