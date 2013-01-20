#!/usr/bin/env python
from distribute_setup import use_setuptools
use_setuptools(version="0.6.17")

from setuptools import setup, find_packages
import os
import os.path

import sys

extra = {}

# Uncomment the following two lines to test in python 3
# if sys.version_info >= (3,):
#    extra['use_2to3'] = True

setup(
    name="pydicom",
    packages=find_packages(),
    include_package_data=True,
    version="0.9.8",
    package_data={'dicom': ['testfiles/*.dcm']},
    zip_safe=False,  # want users to be able to see included examples,tests
    description="Pure python package for DICOM medical file reading and writing",
    author="Darcy Mason",
    author_email="darcymason@gmail.com",
    url="http://pydicom.googlecode.com",
    license="MIT license",
    keywords="dicom python medical imaging",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        #"Programming Language :: Python :: 3.0",
        #"Programming Language :: Python :: 3.1",
        #"Programming Language :: Python :: 3.2",
        #"Programming Language :: Python :: 3.3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
    ],
    long_description="""
    pydicom is a pure python package for parsing DICOM files.
    DICOM is a standard (http://medical.nema.org) for communicating
    medical images and related information such as reports
    and radiotherapy objects.

    pydicom makes it easy to read these complex files into natural
    pythonic structures for easy manipulation.
    Modified datasets can be written again to DICOM format files.
    See the `Getting Started <http://code.google.com/p/pydicom/wiki/GettingStarted>`_
    wiki page for installation and basic information, and the
    `Pydicom User Guide <http://code.google.com/p/pydicom/wiki/PydicomUserGuide>`_ page
    for an overview of how to use the pydicom library.
    """,
    test_loader="dicom.test.run_tests:MyTestLoader",
    test_suite="dummy_string",
    **extra
)
