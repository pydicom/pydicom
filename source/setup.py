#!/usr/bin/env python
try:
    from setuptools import setup, find_packages
except:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

import os
import os.path

import sys

extra = {}


if sys.version_info >= (3,):
    extra['use_2to3'] = True

setup(
    name="dicom",
    packages=find_packages(),
    include_package_data=True,
    version="0.9.9-1",
    package_data={'dicom': ['testfiles/*.dcm']},
    zip_safe=False,  # want users to be able to see included examples,tests
    description="Pure python package for DICOM medical file reading and writing",
    author="Darcy Mason and contributors",
    author_email="darcymason@gmail.com",
    url="https://github.com/darcymason/pydicom",
    license="MIT license",
    keywords="dicom python medical imaging",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.0",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
    ],
    long_description="""
    dicom is a historical version of the pydicom package, for versions < 1.0.
    New code should target the pydicom package rather than this one.
    """,
    test_loader="dicom.test.run_tests:MyTestLoader",
    test_suite="dummy_string",
    **extra
)
