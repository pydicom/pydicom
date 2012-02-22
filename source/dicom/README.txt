README for pydicom distribution

pydicom is released under a modified MIT license. See the license.txt file included with the distribution, or available at http://pydicom.googlecode.com.

To install from a source distribution, at a command line in the source directory (where setup.py is located), type:
python setup.py install

To use the code from python, type:
import dicom

See the examples for more details, or the online information at http://pydicom.googlecode.com.

#PZ 6th Feb 2012

Unzip dicom source into your site-packages directory
Create file pydicom-yourversion-py3.2.egg-info


Metadata-Version: 1.0
Name: pydicom
Version: 0.9.6
Summary: Pure python package for DICOM medical file reading and writing
Home-page: http://pydicom.googlecode.com
Author: Darcy Mason
Author-email: darcymason@gmail.com
License: MIT license
Description: 
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
        
Keywords: dicom python medical imaging
Platform: UNKNOWN
Classifier: License :: OSI Approved :: MIT License
Classifier: Intended Audience :: Developers
Classifier: Intended Audience :: Healthcare Industry
Classifier: Intended Audience :: Science/Research
Classifier: Development Status :: 4 - Beta
Classifier: Programming Language :: Python
Classifier: Programming Language :: Python :: 3.2
Classifier: Operating System :: OS Independent
Classifier: Topic :: Scientific/Engineering :: Medical Science Apps.
Classifier: Topic :: Scientific/Engineering :: Physics
Classifier: Topic :: Software Development :: Libraries
