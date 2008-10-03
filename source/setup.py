#!/usr/bin/env python

from distutils.core import setup
import os
import os.path

import sys

setup(name="pydicom",
      version="0.9.1",
      description="Read, display, modify, write Dicom files",
      author="Darcy Mason",
      author_email="darcymason@gmail.com",
      url="http://pydicom.googlecode.com",
      packages=['dicom'],
	  package_data={'dicom': ['examples/*', 'test/*']},
      license = "Gnu General Public License"
     )

