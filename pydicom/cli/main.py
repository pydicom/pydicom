# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and does a  set_defaults(func=callback_function)

"""

import argparse
import sys
import pkg_resources
import re

from pydicom import dcmread
from pydicom.data.data_manager import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement

subparsers = None


# Restrict the allowed syntax tightly, since use Python `eval`
# on the expression. Do not allow callables, or assignment, for example.
re_kywd_or_item = (
    r"\w+"  # Keyword (\w allows underscore, needed for file_meta) 
    r"(\[(-)?\d+\])?"  # Optional [index] or [-index]
)

re_file_spec_object = re.compile(
    re_kywd_or_item + r"(\." + re_kywd_or_item + r")*$"
)

filespec_help = (
    "[pydicom:]filename[:subobject]\n"
    "DICOM file and optional data element within it.\n"
    "If optional 'pydicom:' prefix is used, then show the pydicom\n"
    "test file with the given filename\n"
    "Examples:\n"
    "   path/to/your_file.dcm\n"
    "   pydicom:rtplan.dcm:BeamSequence[0].BeamNumber\n"
)


def eval_element(ds: Dataset, element: str) -> DataElement:
    try:
        data_elem_val = eval("ds." + element, {"ds": ds})
    except AttributeError:
        raise argparse.ArgumentTypeError(
            f"Data element '{element}' is not in the dataset"
        )
    except IndexError as e:
        raise argparse.ArgumentTypeError(
            f"'{element}' has an index error: {str(e)}"
        )

    return data_elem_val


def filespec_parser(filespec: str):
    """Utility to return a dataset and an optional data element value within it

    Note: this is used as an argparse 'type' for adding parsing arguments.

    Parameters
    ----------
    filespec: str
        A filename with optional `pydicom:` prefix and optional data element,
        in format:
            [pydicom:]<filename>[:<element>]
        If an element is specified, it must be a path to a data element,
        sequence item (dataset), or a sequence.
        Examples:
            your_file.dcm
            your_file.dcm:StudyDate
            pydicom:rtplan.dcm:BeamSequence[0]
            pydicom:rtplan.dcm:BeamSequence[0].BeamLimitingDeviceSequence

    Returns
    -------
    ds: Dataset
        The entire dataset read from the file.
    element: Union[Sequence, Dataset, Any]
        The specified data element's value: one of Sequence, Dataset
        (sequence item) or data element value like float, int, str

    Note
    ----
        This function is meant to be used in a call to an `argparse` libary's
        `add_argument` call for subparsers, with name="filespec" and 
        `type=filespec_parser`. When used that way, the resulting args.filespec
        will contain the return values of this function
        (e.g. use `ds, element_val = args.filespec` after parsing arguments)
        See the `pydicom.cli.show` module for an example.
    
    Raises
    ------
    argparse.ArgumentTypeError
        If the filename does not exist in local path or in pydicom test files,
        or if the optional element is not a valid expression,
        or if the optional element is a valid expression but does not exist
        within the dataset
    """
    pydicom_testfile = False
    if filespec.startswith("pydicom:"):
        pydicom_testfile = True
        filespec = filespec[8:]
    
    
    splitup = filespec.split(":", 1)
    filename = splitup[0]
    if pydicom_testfile:
        filename = get_testdata_file(filename)
    
    # If optional :element there, get it, else blank
    element = splitup[1] if len(splitup) == 2 else ""

    # Check element syntax first to avoid unnecessary load of file
    if element and not re_file_spec_object.match(element):
        raise argparse.ArgumentTypeError(
            f"Component '{element}' is not valid syntax for a "
            "data element, sequence, or sequence item"
        )

    # Read DICOM file
    try:
        ds = dcmread(filename, force=True)
    except FileNotFoundError:
        raise argparse.ArgumentTypeError(f"File '{filename}' not found")
    except Exception as e:
        raise argparse.ArgumentTypeError(
            f"Error reading '{filename}': {str(e)}"
        )

    if not element:
        return ds, None

    data_elem_val = eval_element(ds, element)

    return ds, data_elem_val


def help_command(args):
    subcommands = list(subparsers.choices.keys())
    if args.subcommand and args.subcommand in subcommands:
        subparsers.choices[args.subcommand].print_help()
    else:
        print("Use pydicom help [subcommand] to show help for a subcommand")
        subcommands.remove("help")
        print(f"Available subcommands: {', '.join(subcommands)}")


def get_subcommand_entry_points():
    subcommands = {}
    for entry_point in pkg_resources.iter_entry_points("pydicom_subcommands"):
        subcommands[entry_point.name] = entry_point.load()
    return subcommands


def main(args=None):
    """Entry point for 'pydicom' command line interface

    args: list
        Command-line arguments to parse.  If None, then sys.argv is used
    """
    global subparsers

    parser = argparse.ArgumentParser(
        prog="pydicom", description="pydicom command line utilities"
    )
    subparsers = parser.add_subparsers(help="subcommand help")

    help_parser = subparsers.add_parser(
        "help", help="display help for subcommands"
    )
    help_parser.add_argument(
        "subcommand", nargs="?", help="Subcommand to show help for"
    )
    help_parser.set_defaults(func=help_command)

    # Get subcommands to register themselves as a subparser
    subcommands = get_subcommand_entry_points()
    for subcommand in subcommands.values():
        subcommand(subparsers)

    args = parser.parse_args(args)
    if not len(args.__dict__):
        parser.print_help()
    else:
        args.func(args)
