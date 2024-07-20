[![unit-tests](https://github.com/pydicom/pydicom/workflows/unit-tests/badge.svg)](https://github.com/pydicom/pydicom/actions?query=workflow%3Aunit-tests)
[![type-hints](https://github.com/pydicom/pydicom/workflows/type-hints/badge.svg)](https://github.com/pydicom/pydicom/actions?query=workflow%3Atype-hints)
[![doc-build](https://circleci.com/gh/pydicom/pydicom/tree/main.svg?style=shield)](https://circleci.com/gh/pydicom/pydicom/tree/main)
[![test-coverage](https://codecov.io/gh/pydicom/pydicom/branch/main/graph/badge.svg)](https://codecov.io/gh/pydicom/pydicom)
[![Python version](https://img.shields.io/pypi/pyversions/pydicom.svg)](https://img.shields.io/pypi/pyversions/pydicom.svg)
[![PyPI version](https://badge.fury.io/py/pydicom.svg)](https://badge.fury.io/py/pydicom)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8034250.svg)](https://doi.org/10.5281/zenodo.8034250)

# *pydicom*

*pydicom* is a pure Python package for working with [DICOM](https://www.dicomstandard.org/) files.
It lets you read, modify and write DICOM data in an easy "pythonic" way. As a pure Python package,
*pydicom* can run anywhere Python runs without any other requirements, although if you're working
with *Pixel Data* then we recommend you also install [NumPy](https://numpy.org).

Note that *pydicom* is a general-purpose DICOM framework concerned with
reading and writing DICOM datasets. In order to keep the
project manageable, it does not handle the specifics of individual SOP classes
or other aspects of DICOM. Other libraries both inside and outside the
[pydicom organization](https://github.com/pydicom) are based on *pydicom*
and provide support for other aspects of DICOM, and for more
specific applications.

Examples are [pynetdicom](https://github.com/pydicom/pynetdicom), which
is a Python library for DICOM networking, and [deid](https://github.com/pydicom/deid),
which supports the anonymization of DICOM files.


## Installation

Using [pip](https://pip.pypa.io/en/stable/):
```
pip install pydicom
```
Using [conda](https://docs.conda.io/en/latest/):
```
conda install -c conda-forge pydicom
```

For more information, including installation instructions for the development version, see the [installation guide](https://pydicom.github.io/pydicom/stable/tutorials/installation.html).


## Documentation

The *pydicom* [user guide](https://pydicom.github.io/pydicom/stable/guides/user/index.html), [tutorials](https://pydicom.github.io/pydicom/stable/tutorials/index.html), [examples](https://pydicom.github.io/pydicom/stable/auto_examples/index.html) and [API reference](https://pydicom.github.io/pydicom/stable/reference/index.html) documentation is available for both the [current release](https://pydicom.github.io/pydicom/stable) and the [development version](https://pydicom.github.io/pydicom/dev) on GitHub Pages.

## *Pixel Data*

Compressed and uncompressed *Pixel Data* is always available to
be read, changed and written as [bytes](https://docs.python.org/3/library/stdtypes.html#bytes-objects):
```python
>>> from pydicom import dcmread
>>> from pydicom.data import get_testdata_file
>>> path = get_testdata_file("CT_small.dcm")
>>> ds = dcmread(path)
>>> type(ds.PixelData)
<class 'bytes'>
>>> len(ds.PixelData)
32768
>>> ds.PixelData[:2]
b'\xaf\x00'

```

If [NumPy](https://www.numpy.org) is installed, *Pixel Data* can be converted to an [ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html) using the [Dataset.pixel_array](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.dataset.Dataset.html#pydicom.dataset.Dataset.pixel_array) property:

```python
>>> arr = ds.pixel_array
>>> arr.shape
(128, 128)
>>> arr
array([[175, 180, 166, ..., 203, 207, 216],
       [186, 183, 157, ..., 181, 190, 239],
       [184, 180, 171, ..., 152, 164, 235],
       ...,
       [906, 910, 923, ..., 922, 929, 927],
       [914, 954, 938, ..., 942, 925, 905],
       [959, 955, 916, ..., 911, 904, 909]], dtype=int16)
```
### Decompressing *Pixel Data*
#### JPEG, JPEG-LS and JPEG 2000
Converting JPEG, JPEG-LS or JPEG 2000 compressed *Pixel Data* to an ``ndarray`` requires installing one or more additional Python libraries. For information on which libraries are required, see the [pixel data handler documentation](https://pydicom.github.io/pydicom/stable/guides/user/image_data_handlers.html#guide-compressed).

#### RLE
Decompressing RLE *Pixel Data* only requires NumPy, however it can be quite slow. You may want to consider [installing one or more additional Python libraries](https://pydicom.github.io/pydicom/stable/guides/user/image_data_compression.html) to speed up the process.

### Compressing *Pixel Data*
Information on compressing *Pixel Data* using one of the below formats can be found in the corresponding [encoding guides](https://pydicom.github.io/pydicom/stable/guides/encoding/index.html). These guides cover the specific requirements for each encoding method and we recommend you be familiar with them when performing image compression.

#### JPEG-LS, JPEG 2000
Compressing image data from an ``ndarray`` or ``bytes`` object to JPEG-LS or JPEG 2000 requires installing the following:

* JPEG-LS requires [pyjpegls](https://github.com/pydicom/pyjpegls)
* JPEG 2000 requires [pylibjpeg](https://github.com/pydicom/pylibjpeg) and the [pylibjpeg-openjpeg](https://github.com/pydicom/pylibjpeg-openjpeg) plugin

#### RLE
Compressing using RLE requires no additional packages but can be quite slow. It can be sped up by installing [pylibjpeg](https://github.com/pydicom/pylibjpeg) with the [pylibjpeg-rle](https://github.com/pydicom/pylibjpeg-rle) plugin, or [gdcm](https://github.com/tfmoraes/python-gdcm).


## Examples
More [examples](https://pydicom.github.io/pydicom/stable/auto_examples/index.html) are available in the documentation.

**Change a patient's ID**
```python
from pydicom import dcmread

ds = dcmread("/path/to/file.dcm")
# Edit the (0010,0020) 'Patient ID' element
ds.PatientID = "12345678"
ds.save_as("/path/to/file_updated.dcm")
```

**Display the Pixel Data**

With [NumPy](https://numpy.org) and [matplotlib](https://matplotlib.org/)
```python
import matplotlib.pyplot as plt
from pydicom import dcmread
from pydicom.data import get_testdata_file

# The path to a pydicom test dataset
path = get_testdata_file("CT_small.dcm")
ds = dcmread(path)
# `arr` is a numpy.ndarray
arr = ds.pixel_array

plt.imshow(arr, cmap="gray")
plt.show()
```

## Contributing

We are all volunteers working on *pydicom* in our free time. As our
resources are limited, we very much value your contributions, be it bug fixes, new
core features, or documentation improvements. For more information, please
read our [contribution guide](https://github.com/pydicom/pydicom/blob/main/CONTRIBUTING.md).
