# Copyright 2020 pydicom authors. See LICENSE file for details.
"""
Gather system information and version information for pydicom and auxiliary
modules.

The output is a GitHub-flavoured markdown table whose contents can help
diagnose any perceived bugs in pydicom. This can be pasted directly into a new
GitHub bug report.

This file is intended to be run as an executable module.
"""

import platform
import sys
import importlib


def main():
    version_rows = [("platform", platform.platform()), ("Python", sys.version)]

    for module in ("pydicom", "gdcm", "jpeg_ls", "numpy", "PIL"):
        try:
            m = importlib.import_module(module)
        except ImportError:
            version_rows.append((module, "_module not found_"))
        else:
            version_rows.append((module, extract_version(m)))

    print_table(version_rows)


def print_table(version_rows):
    row_format = "{:12} | {}"
    print(row_format.format("module", "version"))
    print(row_format.format("------", "-------"))
    for module, version in version_rows:
        print(row_format.format(module, version))


def extract_version(module):
    return getattr(module, "__version__", "**no __version__ attribute**")


if __name__ == "__main__":
    main()
