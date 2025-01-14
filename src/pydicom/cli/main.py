# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and calls set_defaults(func=callback_function)

"""

import argparse
from importlib.metadata import entry_points
import re
import sys
from typing import cast, Any
from collections.abc import Callable

from pydicom import dcmread
from pydicom.data.data_manager import get_charset_files, get_testdata_file
from pydicom.datadict import tag_for_keyword
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import UID
from pydicom.valuerep import PersonName


subparsers: argparse._SubParsersAction | None = None


# Restrict the allowed syntax tightly, since use Python `eval`
# on the expression. Do not allow callables, or assignment, for example.
re_kywd_or_item = (
    r"("
    r"\w+"  # Keyword (\w allows underscore, needed for file_meta)
    r"|"  # or
    r"\([0-9A-Fa-f]{4},[0-9A-Fa-f]{4}\)"  # DICOM hex tag (gggg,eeee)
    r")"
    r"(?:\[(-?\d+)\])?"  # Optional [index] or [-index], keep inside brackets
)

re_file_spec_object = re.compile(re_kywd_or_item + r"(\." + re_kywd_or_item + r")*$")

re_match_tag = r"\(([0-9A-Fa-f]{4}),([0-9A-Fa-f]{4})\)"
re_tag_with_spaces = r"\([0-9A-Fa-f]{4}, +[0-9A-Fa-f]{4}\)"

EXTRA_ALLOWED_IDENTIFIERS = {
    # selected properties via {v[0] for v in inspect.getmembers(UID, inspect.isdatadescriptor)}
    FileDataset: ("file_meta",),
    Dataset: ("file_meta",),
    UID: (
        "keyword",
        "is_compressed",
        "info",
        "is_encapsulated",
        "is_retired",
        "is_valid",
        "is_little_endian",
        "is_private",
        "is_implicit_VR",
        "name",
        "is_transfer_syntax",
        "is_deflated",
    ),
    PersonName: (
        "family_name",
        "ideographic",
        "name_suffix",
        "given_name",
        "components",
        "phonetic",
        "middle_name",
        "alphabetic",
        "name_prefix",
    ),
}

filespec_help = (
    "File specification, in format [pydicom::]filename[::element]. "
    "If `pydicom::` prefix is present, then use the pydicom "
    "test file with that name. If `element` is given, "
    "use only that data element within the file. "
    "Examples: "
    "path/to/your_file.dcm, "
    "your_file.dcm::StudyDate, "
    "your_file.dcm::(0001,0001), "
    "pydicom::rtplan.dcm::BeamSequence[0], "
    "yourplan.dcm::BeamSequence[0].BeamNumber, "
    "pydicom::rtplan.dcm::(300A,00B0)[0].(300A,00B6)"
)


def eval_element(ds: Dataset, element: str) -> Any:
    # replace all ".(gggg,eeee)" hex tags with `eval`uable expression

    obj: Dataset|None = ds
    for sub_elem in element.split("."):
        # e.g. match "BeamSequence[1]" --> groups: ['BeamSequence', '1']
        m = re.match(re_kywd_or_item, sub_elem)
        identifier = m.groups()[0]  # type: ignore

        if tag_for_keyword(identifier) is not None:  # Standard DICOM keyword
            obj = getattr(obj, identifier, None)
            if obj is None:
                raise argparse.ArgumentTypeError(
                    f"'{identifier}' is not in the parent object"
                )
        # Try (gggg,eee) tag
        elif match := re.match(re_match_tag, identifier):
            try:
                obj = cast(Dataset, obj)["".join(match.groups()[0:2])].value
            except KeyError:
                raise argparse.ArgumentTypeError(
                    f"'{identifier}' is not in the parent object"
                )
        # Try other identifiers
        elif identifier in EXTRA_ALLOWED_IDENTIFIERS.get(type(obj), []):
            obj = getattr(obj, identifier, None)
            if obj is None:
                raise argparse.ArgumentTypeError(
                    f"'{identifier}' is not in the parent object"
                )
        else:
            raise argparse.ArgumentTypeError(
                f"'{identifier}' is not a known DICOM keyword, "
                "tag or allowed class property"
            )

        # If here, then have the new object, handle indexing if there
        if (index := m.groups()[1]) is not None:  # type: ignore
            try:
                obj = obj[int(index)]
            except (IndexError, TypeError) as e:
                raise argparse.ArgumentTypeError(
                    f"'{index}' gave an index error: {str(e)}"
                )

    return obj


def filespec_parts(filespec: str) -> tuple[str, str, str]:
    """Parse the filespec format into prefix, filename, element

    Format is [prefix::filename::element]

    Note that ':' can also exist in valid filename, e.g. r'c:\temp\test.dcm'
    """

    *prefix_file, last = filespec.split("::")

    if not prefix_file:  # then only the filename component
        return "", last, ""

    prefix = "pydicom" if prefix_file[0] == "pydicom" else ""
    if prefix:
        prefix_file.pop(0)

    # If list empty after pop above, then have pydicom::filename
    if not prefix_file:
        return prefix, last, ""

    return prefix, "".join(prefix_file), last


def filespec_parser(filespec: str) -> list[tuple[Dataset, Any]]:
    """Utility to return a dataset and an optional data element value within it

    Note: this is used as an argparse 'type' for adding parsing arguments.

    Parameters
    ----------
    filespec: str
        A filename with optional `pydicom::` prefix and optional data element,
        in format:
            [pydicom::]<filename>[::<element>]
        If an element is specified, it must be a path to a data element,
        sequence item (dataset), or a sequence, specified with
        DICOM keywords, or DICOM tags in the format (gggg,eeee).

        Examples:
            your_file.dcm
            your_file.dcm::StudyDate
            pydicom::ct_small.dcm::(0019,0010)
            pydicom::rtplan.dcm::BeamSequence[0]
            pydicom::rtplan.dcm::BeamSequence[0].BeamLimitingDeviceSequence
            pydicom::rtplan.dcm::(300A,00B0)[0]
            pydicom::rtplan.dcm::(300A,00B0)[0].BeamLimitingDeviceSequence
            pydicom::rtplan.dcm::(300A,00B0)[0].(300A,00B6)

    Returns
    -------
    List[Tuple[Dataset, Any]]
        Matching pairs of (dataset, data element value)
        This usually is a single pair, but a list is returned for future
        ability to work across multiple files.

    Note
    ----
        This function is meant to be used in a call to an `argparse` library's
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
    prefix, filename, element = filespec_parts(filespec)

    # Get the pydicom test filename even without prefix, in case user forgot it
    try:
        pydicom_filename = cast(str, get_testdata_file(filename))
    except ValueError:  # will get this if absolute path passed
        pydicom_filename = ""

    # Check if filename is in charset files
    if not pydicom_filename:
        try:
            char_filenames = get_charset_files(filename)
            if char_filenames:
                pydicom_filename = char_filenames[0]
        except NotImplementedError:  # will get this if absolute path passed
            pass

    if prefix == "pydicom":
        filename = pydicom_filename

    # Check element syntax first to avoid unnecessary load of file
    if element and not re_file_spec_object.match(element):
        # Special message if a tag with spaces
        if m := re.search(re_tag_with_spaces, element):
            msg = (
                f"Tag '{m.group()}' is not valid syntax for a " "tag: no spaces allowed"
            )
        else:
            msg = (
                f"Component '{element}' is not valid syntax for a "
                "data element, sequence, or sequence item"
            )
        raise argparse.ArgumentTypeError(msg)

    # Read DICOM file
    try:
        ds = dcmread(filename, force=True)
    except FileNotFoundError:
        extra = (
            (f", \nbut 'pydicom::{filename}' test data file is available")
            if pydicom_filename
            else ""
        )
        raise argparse.ArgumentTypeError(f"File '{filename}' not found{extra}")
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading '{filename}': {e}")

    if not element:
        return [(ds, None)]

    data_elem_val = eval_element(ds, element)

    return [(ds, data_elem_val)]


def help_command(args: argparse.Namespace) -> None:
    if subparsers is None:
        print("No subcommands are available")
        return

    subcommands: list[str] = list(subparsers.choices.keys())
    if args.subcommand and args.subcommand in subcommands:
        subparsers.choices[args.subcommand].print_help()
    else:
        print("Use pydicom help [subcommand] to show help for a subcommand")
        subcommands.remove("help")
        print(f"Available subcommands: {', '.join(subcommands)}")


SubCommandType = dict[str, Callable[[argparse._SubParsersAction], None]]


def get_subcommand_entry_points() -> SubCommandType:
    subcommands = {}
    for entry_point in entry_points(group="pydicom_subcommands"):
        subcommands[entry_point.name] = entry_point.load()

    return subcommands


def main(args: list[str] | None = None) -> None:
    """Entry point for 'pydicom' command line interface

    Parameters
    ----------
    args : List[str], optional
        Command-line arguments to parse.  If ``None``, then :attr:`sys.argv`
        is used.
    """
    global subparsers

    py_version = sys.version.split()[0]

    parser = argparse.ArgumentParser(
        prog="pydicom",
        description=f"pydicom command line utilities (Python {py_version})",
    )
    subparsers = parser.add_subparsers(help="subcommand help")

    help_parser = subparsers.add_parser("help", help="display help for subcommands")
    help_parser.add_argument(
        "subcommand", nargs="?", help="Subcommand to show help for"
    )
    help_parser.set_defaults(func=help_command)

    # Get subcommands to register themselves as a subparser
    subcommands = get_subcommand_entry_points()
    for subcommand in subcommands.values():
        subcommand(subparsers)

    ns = parser.parse_args(args)
    if not vars(ns):
        parser.print_help()
    else:
        ns.func(ns)
