#!/usr/bin/env python
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup
import os
import os.path

import sys

setup(name="pydicom",
      include_package_data = True,
      zip_safe = False, # could do it but want users to be able to directly see examples,tests included with package
      packages = ['dicom'],
      version="0.9.2",
      description="Pure python package for DICOM file reading and writing",
      author="Darcy Mason",
      author_email="darcymason@gmail.com",
      url="http://pydicom.googlecode.com",
      license = "Gnu General Public License",
      keywords = "dicom python medical imaging",
      classifiers = [
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps."
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
        ]

     )
