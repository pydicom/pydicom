# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and does a  set_defaults(func=callback_function)

"""

import argparse
import sys
from pydicom.cli import _codify, show

modules = [_codify, show]


def main(args=None):
    """Entry point for 'pydicom' command line interface

    args: list
        Command-line arguments to parse.  If None, then sys.argv is used
    """
    parser = argparse.ArgumentParser(
        prog="pydicom", description="pydicom command line utilities"
    )
    subparsers = parser.add_subparsers(help="sub-command help")

    for module in modules:
        module.add_subparser(subparsers)

    args = parser.parse_args(args)
    args.func(args)
