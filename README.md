pydicom
=======

[![Build Status](https://travis-ci.org/pydicom/pydicom.svg?branch=master)](https://travis-ci.org/pydicom/pydicom)
[![AppVeyor](https://ci.appveyor.com/api/projects/status/1vjtkr82lumnd3i7?svg=true)](https://ci.appveyor.com/project/glemaitre/pydicom)
[![CircleCI](https://circleci.com/gh/pydicom/pydicom/tree/master.svg?style=shield)](https://circleci.com/gh/pydicom/pydicom/tree/master)
[![codecov](https://codecov.io/gh/pydicom/pydicom/branch/master/graph/badge.svg)](https://codecov.io/gh/pydicom/pydicom)
[![Python version](https://img.shields.io/pypi/pyversions/pydicom.svg)](https://img.shields.io/pypi/pyversions/pydicom.svg)
[![PyPI version](https://badge.fury.io/py/pydicom.svg)](https://badge.fury.io/py/pydicom)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3332998.svg)](https://doi.org/10.5281/zenodo.3332998)

pydicom is a pure python package for working with [DICOM](http://medical.nema.org/) files.
It was made for inspecting and modifying DICOM data in an easy "pythonic" way.
The modifications can be written again to a new file.

As a pure python package, pydicom can run anywhere python runs without any other requirements,
although [NumPy](http://www.numpy.org) is needed if manipulating pixel data.

pydicom is not a DICOM server, and is not primarily about viewing images.
It is designed to let you
manipulate data elements in DICOM files with python code.

Limitations -- for files with _compressed_ pixel data, pydicom can decompress
it (with additional libraries installed) and allow you to manipulate the data,
but can only store changed pixel data as uncompressed. Files can always be
read and saved (including compressed pixel data that has not been modified),
but once decompressed, modified pixel data cannot be compressed again.

Documentation
-------------

pydicom documentation is available on GitHub Pages both for the [development
 (master) version](https://pydicom.github.io/pydicom/dev) and for the
[released version](https://pydicom.github.io/pydicom/stable). The
documentation for [the previous 0.9.9 version](https://pydicom.github.io/pydicom/0.9/)
is still there for reference.

See [Getting Started](https://pydicom.github.io/pydicom/stable/getting_started.html)
for installation and basic information, and the
[User Guide](https://pydicom.github.io/pydicom/stable/pydicom_user_guide.html)
for an overview of how to use the pydicom library.
To contribute to pydicom, read our [contribution guide](https://github.com/pydicom/pydicom/blob/master/CONTRIBUTING.md).
To contribute an example or extension of pydicom that does not belong with
the core software, see our contribution repository,
[contrib-pydicom](https://www.github.com/pydicom/contrib-pydicom).
