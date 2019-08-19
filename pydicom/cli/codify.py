# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for codify"""

import pydicom.util.codify

default_exclude_size = 100


def add_subparser(subparsers):
    codify_parser = subparsers.add_parser(
        "codify",
        description="Produce python/pydicom code from a DICOM file",
        epilog="Binary data (e.g. pixels) larger than --exclude-size "
        "(default %d bytes) is not included. A dummy line "
        "with a syntax error is produced. "
        "Private data elements are not included "
        "by default." % default_exclude_size,
    )

    # Codify existed before as a stand-alone before, re-use it here
    pydicom.util.codify.set_parser_arguments(
        codify_parser, default_exclude_size
    )
    codify_parser.set_defaults(func=pydicom.util.codify.do_codify)
