# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program"""

import argparse
import sys


def add_codify_subparser(subparsers):
    codify = subparsers.add_parser("codify", help="codify help")
    codify.add_argument(
        "infile", help="DICOM file from which to produce code lines"
    )
    codify.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType("w"),
        help=(
            "Filename to write python code to. "
            "If not specified, code is written to stdout"
        ),
        default=sys.stdout,
    )
    # help_exclude_size = 'Exclude binary data larger than specified (bytes). '
    # help_exclude_size += 'Default is %d bytes' % default_exclude_size
    # parser.add_argument(
    #     '-e',
    #     '--exclude-size',
    #     type=int_type,
    #     default=default_exclude_size,
    #     help=help_exclude_size)
    # parser.add_argument(
    #     '-p',
    #     '--include-private',
    #     action="store_true",
    #     help='Include private data elements '
    #     '(default is to exclude them)')
    # parser.add_argument(
    #     '-s',
    #     '--save-as',
    #     help=("Specify the filename for ds.save_as(save_filename); "
    #           "otherwise the input name + '_from_codify' will be used"))


def add_show_subparser(subparsers):
    show = subparsers.add_parser("show", help="show help")


def main(args=None):
    """Entry point for 'pydicom' command line interface

    args: list
        Command-line arguments to parse.  If None, then sys.argv is used
    """
    parser = argparse.ArgumentParser(
        prog="pydicom", description="pydicom command line utilities"
    )
    subparsers = parser.add_subparsers(help="sub-command help")

    add_codify_subparser(subparsers)
    add_show_subparser(subparsers)

    args = parser.parse_args(args)
    print(repr(args))


def show():
    pass


def tree():
    pass
