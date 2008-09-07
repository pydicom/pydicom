#!/usr/bin/env python

from distutils.core import setup
import os
import os.path

import sys

mydir = os.path.dirname(sys.argv[0])  # inside the pydicom directory

# examples_path = os.path.join(mydir, "dicom", "examples")
# example_files = [os.path.join(examples_path, x) for x in os.listdir(examples_path)
#                 if x.endswith(".txt") or x.endswith(".py")]

# doc_path = os.path.join(mydir, "dicom", "doc")
# doc_files = [os.path.join(doc_path, x) for x in os.listdir(doc_path)
#             if x.endswith(".py") or x.endswith(".html") or x.endswith(".htm")
#             or x.endswith(".txt")]

setup(name="pydicom",
      version="0.9",
      description="Read, display, modify, write Dicom files",
      author="Darcy Mason",
      author_email="darcymason@gmail.com",
      url="http://pydicom.googlecode.com",
      packages=['dicom'],
	  package_data={'dicom': ['examples/*', 'test/*']},
      license = "Gnu General Public License"
     )

