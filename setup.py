#!/usr/bin/env python
from setuptools import setup, find_packages
from pydicom import __version__


description = "Pure python package for DICOM medical file reading and writing"

long_description = """

pydicom
=======

pydicom is a pure python package for parsing DICOM files. DICOM is a standard
(http://medical.nema.org) for communicating medical images and related
information such as reports and radiotherapy objects.

pydicom makes it easy to read these complex files into natural pythonic
structures for easy manipulation.  Modified datasets can be written again to
DICOM format files. See the `Getting Started
<http://pydicom.readthedocs.org/en/latest/getting_started.html>`_ page for
installation and basic information, and the `Pydicom User Guide
<http://pydicom.readthedocs.org/en/latest/pydicom_user_guide.html>`_ page for
an overview of how to use the pydicom library.
"""

CLASSIFIERS = [
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Intended Audience :: Healthcare Industry",
    "Intended Audience :: Science/Research",
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Operating System :: OS Independent",
    "Topic :: Scientific/Engineering :: Medical Science Apps.",
    "Topic :: Scientific/Engineering :: Physics",
    "Topic :: Software Development :: Libraries"]

KEYWORDS = "dicom python medical imaging"

NAME = "pydicom"
AUTHOR = "Darcy Mason and contributors"
AUTHOR_EMAIL = "darcymason@gmail.com"
MAINTAINER = "Darcy Mason and contributors"
MAINTAINER_EMAIL = "darcymason@gmail.com"
DESCRIPTION = description
LONG_DESCRIPTION = long_description
URL = "https://github.com/pydicom/pydicom"
DOWNLOAD_URL = "https://github.com/pydicom/pydicom/archive/master.zip"
LICENSE = "MIT"
VERSION = __version__
PACKAGE_DATA = {'pydicom': ['tests/test_files/*', 'tests/charset_files/*']}
REQUIRES = []

opts = dict(name=NAME,
            version=__version__,
            maintainer=MAINTAINER,
            maintainer_email=MAINTAINER_EMAIL,
            author=AUTHOR,
            author_email=AUTHOR_EMAIL,
            description=description,
            long_description=long_description,
            url=URL,
            download_url=DOWNLOAD_URL,
            license=LICENSE,
            keywords=KEYWORDS,
            classifiers=CLASSIFIERS,
            packages=find_packages(),
            package_data=PACKAGE_DATA,
            include_package_data=True,
            install_requires=REQUIRES,
            zip_safe=False)


if __name__ == '__main__':
    setup(**opts)
