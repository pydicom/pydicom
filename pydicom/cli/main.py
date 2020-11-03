# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and does a  set_defaults(func=callback_function)

"""

import argparse
import sys
from pydicom.cli import codify, show
import pkg_resources


subparsers = None

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
    for entry_point in pkg_resources.iter_entry_points('pydicom_subcommands'):
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
            'help',
             help='display help for subcommands'
        )
    help_parser.add_argument(
            'subcommand',
             nargs='?',
             help='Subcommand to show help for'
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
