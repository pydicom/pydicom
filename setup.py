#!/usr/bin/env python

import os
import os.path
import sys
from glob import glob
from setuptools import setup, find_packages

have_dicom = True
try:
    import dicom
except ImportError:
    have_dicom = False

# get __version__ from _version.py
base_dir = os.path.dirname(os.path.realpath(__file__))
ver_file = os.path.join(base_dir, 'pydicom', '_version.py')
with open(ver_file) as f:
    exec(f.read())

description = "Pure python package for DICOM medical file reading and writing"

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

TESTS_REQUIRE = ['pytest']
_py_modules = []
if not have_dicom:
    _py_modules = ['dicom']

CLASSIFIERS = [
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Intended Audience :: Healthcare Industry",
    "Intended Audience :: Science/Research",
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Operating System :: OS Independent",
    "Topic :: Scientific/Engineering :: Medical Science Apps.",
    "Topic :: Scientific/Engineering :: Physics",
    "Topic :: Software Development :: Libraries"
]

KEYWORDS = "dicom python medical imaging"

NAME = "pydicom"
AUTHOR = "Darcy Mason and contributors"
AUTHOR_EMAIL = "darcymason@gmail.com"
MAINTAINER = "Darcy Mason and contributors"
MAINTAINER_EMAIL = "darcymason@gmail.com"
DESCRIPTION = description
URL = "https://github.com/pydicom/pydicom"
DOWNLOAD_URL = "https://github.com/pydicom/pydicom/archive/master.zip"
LICENSE = "MIT"
VERSION = __version__  # noqa: F821
REQUIRES = []
SETUP_REQUIRES = pytest_runner

# get long description from README.md
BASE_PATH = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(BASE_PATH, 'README.md')) as f:
    LONG_DESCRIPTION = f.read()


def data_files_inventory():
    data_files = []
    data_roots = ['pydicom/data']
    for data_root in data_roots:
        for root, subfolder, files in os.walk(data_root):
            files = [
                x.replace('pydicom/', '') for x in glob(root + '/*')
                if not os.path.isdir(x)
            ]
            files = [f for f in files if not f.endswith('.pyc')]
            data_files += files
    return data_files


PACKAGE_DATA = {
    'pydicom': data_files_inventory() + ['py.typed']
}

ENTRY_POINTS = {
    "console_scripts": ["pydicom=pydicom.cli.main:main"],
    "pydicom_subcommands": [
        "codify = pydicom.cli.codify:add_subparser",
        "show = pydicom.cli.show:add_subparser"
    ]
}


opts = dict(
    name=NAME,
    python_requires='>=3.6.1',
    version=VERSION,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=description,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url=URL,
    download_url=DOWNLOAD_URL,
    license=LICENSE,
    keywords=KEYWORDS,
    classifiers=CLASSIFIERS,
    packages=find_packages(),
    py_modules=_py_modules,
    package_data=PACKAGE_DATA,
    include_package_data=True,
    install_requires=REQUIRES,
    setup_requires=SETUP_REQUIRES,
    tests_require=TESTS_REQUIRE,
    zip_safe=False,
    entry_points=ENTRY_POINTS,
)

if __name__ == '__main__':
    setup(**opts)
