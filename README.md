pydicom
=======

[![Build Status](https://travis-ci.org/pydicom/pydicom.svg?branch=master)](https://travis-ci.org/pydicom/pydicom)
[![AppVeyor](https://ci.appveyor.com/api/projects/status/1vjtkr82lumnd3i7?svg=true)](https://ci.appveyor.com/project/glemaitre/pydicom)
[![CircleCI](https://circleci.com/gh/pydicom/pydicom/tree/master.svg?style=shield)](https://circleci.com/gh/pydicom/pydicom/tree/master)
[![codecov](https://codecov.io/gh/pydicom/pydicom/branch/master/graph/badge.svg)](https://codecov.io/gh/pydicom/pydicom)
[![Python version](https://img.shields.io/pypi/pyversions/pydicom.svg)](https://img.shields.io/pypi/pyversions/pydicom.svg)
[![PyPI version](https://badge.fury.io/py/pydicom.svg)](https://badge.fury.io/py/pydicom)

pydicom is a pure python package for working with [DICOM](http://medical.nema.org/) files.
It was made for inspecting and modifying DICOM data in an easy "pythonic" way.
The modifications can be written again to a new file.

As a pure python package, pydicom can run anywhere python runs without any other requirements,
although [NumPy](http://www.numpy.org) is needed if manipulating pixel data.

pydicom is not a DICOM server, and is not primarily about viewing images. It is designed to let you
manipulate data elements in DICOM files with python code.

Limitations -- the main limitation of the current version is that _compressed_ pixel data (e.g. JPEG)
cannot be altered in an intelligent way as it can for uncompressed pixels.
Files can always be read and saved, but compressed pixel data cannot easily be modified.

Documentation
-------------

pydicom [documentation](https://pydicom.readthedocs.org/en/stable/) is available on Read The Docs.

See [Getting Started](https://pydicom.readthedocs.org/en/stable/getting_started.html) for installation and basic information, and the [User Guide](https://pydicom.readthedocs.org/en/stable/pydicom_user_guide.html) for an overview of how to use the pydicom library.
