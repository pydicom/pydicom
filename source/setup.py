#!/usr/bin/env python
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup
import os
import os.path

import sys

setup(name="pydicom",
      include_package_data = True,
      zip_safe = False, # want users to be able to see included examples,tests
      packages = ['dicom'],
      version="0.9.3",
      description="Pure python package for DICOM medical file reading and writing",
      author="Darcy Mason",
      author_email="darcymason@gmail.com",
      url="http://pydicom.googlecode.com",
      license = "MIT license",
      keywords = "dicom python medical imaging",
      classifiers = [
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps."
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
        ],
      long_description = """
      pydicom is a pure python package for working with DICOM files. 
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
      """
     )
