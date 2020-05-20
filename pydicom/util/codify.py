# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""
Produce runnable python code which can recreate DICOM objects or files.

Can run as a script to produce code for an entire file,
or import and use specific functions to provide code for pydicom DICOM classes

"""

# Run this from the same directory as a "base" dicom file and
# this code will output to screen the dicom parameters like:
#    ds.PatientName = 'TEST'
# etc for all parameters in the file.
# This can then be pasted into a python file and parameters edited as necessary
# to create a DICOM file from scratch

import sys
import os.path
import pydicom
from pydicom.datadict import dictionary_keyword

import re

line_term = "\n"

# Helper functions first

# Precompiled search patterns for camel_to_underscore()
first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')

byte_VRs = [
    'OB', 'OW', 'OW/OB', 'OW or OB', 'OB or OW', 'US or SS or OW', 'US or SS',
    'OD', 'OL'
]


def camel_to_underscore(name):
    """Convert name from CamelCase to lower_case_with_underscores"""
    # From http://stackoverflow.com/questions/1175208
    s1 = first_cap_re.sub(r'\1_\2', name)
    return all_cap_re.sub(r'\1_\2', s1).lower()


def tag_repr(tag):
    """String of tag value as (0xgggg, 0xeeee)"""
    return "(0x{group:04x}, 0x{elem:04x})".format(
        group=tag.group, elem=tag.element)


def default_name_filter(name):
    """Callable to reduce some names in code to more readable short form

    :arg name: a sequence variable name or sequence item name
    :return: a shorter version of name if a known conversion,
             else return original name

    """
    name = camel_to_underscore(name)
    name = name.replace("control_point", "cp")
    name = name.replace("reference", "ref")
    name = name.replace("fraction_group", "frxn_gp")
    return name


# Functions to produce python code
def code_imports():
    """Code the import statements needed by other codify results

    :return: a string of import statement lines

    """
    line1 = "import pydicom"
    line2 = "from pydicom.dataset import Dataset, FileMetaDataset"
    line3 = "from pydicom.sequence import Sequence"
    return line_term.join((line1, line2, line3))


def code_dataelem(dataelem,
                  dataset_name="ds",
                  exclude_size=None,
                  include_private=False):
    """Code lines for a single DICOM data element

    :arg dataelem: the DataElement instance to turn into code
    :arg dataset_name: variable name of the Dataset containing dataelem
    :arg exclude_size: if specified, values longer than this (in bytes)
                       will only have a commented string for a value,
                       causing a syntax error when the code is run,
                       and thus prompting the user to remove or fix that line.
    :return: a string containing code to recreate the data element
             If the data element is a sequence, calls code_sequence

    """

    if dataelem.VR == "SQ":
        return code_sequence(dataelem, dataset_name, exclude_size,
                             include_private)

    # If in DICOM dictionary, set using the keyword
    # If not (e.g. is private element), set using add_new method
    have_keyword = True
    try:
        keyword = dictionary_keyword(dataelem.tag)
    except KeyError:
        have_keyword = False

    valuerep = repr(dataelem.value)

    if exclude_size:
        if (dataelem.VR in byte_VRs and
                len(dataelem.value) > exclude_size):
            valuerep = (
                "# XXX Array of %d bytes excluded" % len(dataelem.value))

    if have_keyword:
        format_str = "{ds_name}.{keyword} = {valuerep}"
        line = format_str.format(
            ds_name=dataset_name, keyword=keyword, valuerep=valuerep)
    else:
        format_str = "{ds_name}.add_new({tag}, '{VR}', {valuerep})"
        line = format_str.format(
            ds_name=dataset_name,
            tag=tag_repr(dataelem.tag),
            VR=dataelem.VR,
            valuerep=valuerep)
    return line


def code_sequence(dataelem,
                  dataset_name="ds",
                  exclude_size=None,
                  include_private=False,
                  name_filter=default_name_filter):
    """Code lines for recreating a Sequence data element

    :arg dataelem: the DataElement instance of the Sequence
    :arg dataset_name: variable name of the dataset containing the Sequence
    :arg exclude_size: if specified, values longer than this (in bytes)
                       will only have a commented string for a value,
                       causing a syntax error when the code is run,
                       and thus prompting the user to remove or fix that line.
    :arg include_private: If True, private data elements will be coded.
                          If False, private elements are skipped
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
        # Determine index to use. If seq item has a data element with 'Index',
        #    use that; if one with 'Number', use that, else start at 1
        index_keyword = seq_keyword.replace("Sequence", "") + "Index"
        number_keyword = seq_keyword.replace("Sequence", "") + "Number"
        if index_keyword in ds:
            index_str = str(getattr(ds, index_keyword))
        elif number_keyword in ds:
            index_str = str(getattr(ds, number_keyword))
        else:
            index_str = str(i + 1)

        # Code comment line to mark start of sequence item
        lines.append('')
        lines.append("# " + seq_name + ": " + seq_item_name + " " + index_str)

        # Determine the variable name to use for the sequence item (dataset)
        ds_name = seq_var.replace("_sequence", "") + index_str

        # Code the sequence item
        code_item = code_dataset(ds, ds_name, exclude_size, include_private)
        lines.append(code_item)

        # Code the line to append the item to its parent sequence
        lines.append(seq_var + ".append(" + ds_name + ")")

    # Join the lines and return a single string
    return line_term.join(lines)


def code_dataset(ds,
                 dataset_name="ds",
                 exclude_size=None,
                 include_private=False,
                 is_file_meta=False):
    """Return python code lines for import statements needed by other code

    :arg exclude_size: if specified, values longer than this (in bytes)
                       will only have a commented string for a value,
                       causing a syntax error when the code is run,
                       and thus prompting the user to remove or fix that line.
    :arg include_private: If True, private data elements will be coded.
                          If False, private elements are skipped
    :return: a list of code lines containing import statements

    """
    lines = []
    ds_class = " = FileMetaDataset()" if is_file_meta else " = Dataset()"
    lines.append(dataset_name + ds_class)
    for dataelem in ds:
        # If a private data element and flag says so, skip it and go to next
        if not include_private and dataelem.tag.is_private:
            continue
        # Otherwise code the line and add it to the lines list
        code_line = code_dataelem(dataelem, dataset_name, exclude_size,
                                  include_private)
        lines.append(code_line)
        # Add blank line if just coded a sequence
        if dataelem.VR == "SQ":
            lines.append('')
    # If sequence was end of this dataset, remove the extra blank line
    if len(lines) and lines[-1] == '':
        lines.pop()
    # Join all the code lines and return them
    return line_term.join(lines)


def code_file(filename, exclude_size=None, include_private=False):
    """Write a complete source code file to recreate a DICOM file

    :arg filename: complete path and filename of a DICOM file to convert
    :arg exclude_size: if specified, values longer than this (in bytes)
                       will only have a commented string for a value,
                       causing a syntax error when the code is run,
                       and thus prompting the user to remove or fix that line.
    :arg include_private: If True, private data elements will be coded.
                          If False, private elements are skipped
    :return: a string containing code lines to recreate entire file

    """
    lines = []

    ds = pydicom.dcmread(filename, force=True)

    # Code a nice header for the python file
    lines.append("# Coded version of DICOM file '{0}'".format(filename))
    lines.append("# Produced by pydicom codify utility script")

    # Code the necessary imports
    lines.append(code_imports())
    lines.append('')

    # Code the file_meta information
    lines.append("# File meta info data elements")
    code_meta = code_dataset(ds.file_meta, "file_meta", exclude_size,
                             include_private, is_file_meta=True)
    lines.append(code_meta)
    lines.append('')

    # Code the main dataset
    lines.append("# Main data elements")
    code_ds = code_dataset(
        ds, exclude_size=exclude_size, include_private=include_private)
    lines.append(code_ds)
    lines.append('')

    # Add the file meta to the dataset, and set transfer syntax
    lines.append("ds.file_meta = file_meta")
    lines.append("ds.is_implicit_VR = " + str(ds.is_implicit_VR))
    lines.append("ds.is_little_endian = " + str(ds.is_little_endian))

    # Return the complete code string
    return line_term.join(lines)


def main(default_exclude_size, args=None):
    """Create python code according to user options

    Parameters:
    -----------
    default_exclude_size:  int
        Values longer than this will be coded as a commented syntax error

    args: list
        Command-line arguments to parse.  If None, then sys.argv is used
    """

    try:
        import argparse
    except ImportError:
        print("The argparse module is required to run this script")
        print("argparse is standard in python >= 2.7,")
        print("   or can be installed with 'pip install argparse'")
        sys.exit(-1)

    parser = argparse.ArgumentParser(
        description="Produce python/pydicom code from a DICOM file",
        epilog="Binary data (e.g. pixels) larger than --exclude-size "
        "(default %d bytes) is not included. A dummy line "
        "with a syntax error is produced. "
        "Private data elements are not included "
        "by default." % default_exclude_size)
    parser.add_argument(
        'infile', help="DICOM file from which to produce code lines")
    parser.add_argument(
        'outfile',
        nargs='?',
        type=argparse.FileType('w'),
        help=("Filename to write python code to. "
              "If not specified, code is written to stdout"),
        default=sys.stdout)
    help_exclude_size = 'Exclude binary data larger than specified (bytes). '
    help_exclude_size += 'Default is %d bytes' % default_exclude_size
    parser.add_argument(
        '-e',
        '--exclude-size',
        type=int,
        default=default_exclude_size,
        help=help_exclude_size)
    parser.add_argument(
        '-p',
        '--include-private',
        action="store_true",
        help='Include private data elements '
        '(default is to exclude them)')
    parser.add_argument(
        '-s',
        '--save-as',
        help=("Specify the filename for ds.save_as(save_filename); "
              "otherwise the input name + '_from_codify' will be used"))

    args = parser.parse_args(args)

    # Read the requested file and convert to python/pydicom code lines
    filename = args.infile  # name
    code_lines = code_file(filename, args.exclude_size, args.include_private)

    # If requested, write a code line to save the dataset
    if args.save_as:
        save_as_filename = args.save_as
    else:
        base, ext = os.path.splitext(filename)
        save_as_filename = base + "_from_codify" + ".dcm"
    line = "\nds.save_as(r'{filename}', write_like_original=False)"
    save_line = line.format(filename=save_as_filename)
    code_lines += save_line

    # Write the code lines to specified file or to standard output
    # For test_util, captured output .name throws error, ignore it:
    try:
        if args.outfile.name != "<stdout>":
            print("Writing code to file '%s'" % args.outfile.name)
    except AttributeError:
        pass
    args.outfile.write(code_lines)


if __name__ == "__main__":
    main(default_exclude_size=100)
