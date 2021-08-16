[![CircleCI](https://circleci.com/gh/pydicom/pydicom/tree/master.svg?style=shield)](https://circleci.com/gh/pydicom/pydicom/tree/master)
[![codecov](https://codecov.io/gh/pydicom/pydicom/branch/master/graph/badge.svg)](https://codecov.io/gh/pydicom/pydicom)
[![Python version](https://img.shields.io/pypi/pyversions/pydicom.svg)](https://img.shields.io/pypi/pyversions/pydicom.svg)
[![PyPI version](https://badge.fury.io/py/pydicom.svg)](https://badge.fury.io/py/pydicom)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.5164413.svg)](https://doi.org/10.5281/zenodo.5164413)
[![Gitter](https://badges.gitter.im/pydicom/Lobby.svg)](https://gitter.im/pydicom/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

# *pydicom*

*pydicom* is a pure Python package for working with [DICOM](https://www.dicomstandard.org/) files. It lets you read, modify and write DICOM data in an easy "pythonic" way.

As a pure Python package, *pydicom* can run anywhere Python runs without any other requirements, although if you're working with *Pixel Data* then we recommend you also install [NumPy](http://www.numpy.org).

If you're looking for a Python library for DICOM networking then you might be interested in another of our projects: [pynetdicom](https://github.com/pydicom/pynetdicom).

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

The *pydicom* [user guide](https://pydicom.github.io/pydicom/stable/old/pydicom_user_guide.html), [tutorials](https://pydicom.github.io/pydicom/stable/tutorials/index.html), [examples](https://pydicom.github.io/pydicom/stable/auto_examples/index.html) and [API reference](https://pydicom.github.io/pydicom/stable/reference/index.html) documentation is available for both the [current release](https://pydicom.github.io/pydicom/stable) and the [development version](https://pydicom.github.io/pydicom/dev) on GitHub Pages.

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

If [NumPy](http://www.numpy.org) is installed, *Pixel Data* can be converted to an [ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html) using the [Dataset.pixel_array](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.dataset.Dataset.html#pydicom.dataset.Dataset.pixel_array) property:

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
### Compressed *Pixel Data*
#### JPEG, JPEG-LS and JPEG 2000
Converting JPEG compressed *Pixel Data* to an ``ndarray`` requires installing one or more additional Python libraries. For information on which libraries are required, see the [pixel data handler documentation](https://pydicom.github.io/pydicom/stable/old/image_data_handlers.html#guide-compressed).

Compressing data into one of the JPEG formats is not currently supported.

#### RLE
Encoding and decoding RLE *Pixel Data* only requires NumPy, however it can
be quite slow. You may want to consider [installing one or more additional
Python libraries](https://pydicom.github.io/pydicom/stable/old/image_data_compression.html) to speed up the process.

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

With [NumPy](http://www.numpy.org) and [matplotlib](https://matplotlib.org/)
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

To contribute to *pydicom*, read our [contribution guide](https://github.com/pydicom/pydicom/blob/master/CONTRIBUTING.md).

To contribute an example or extension of *pydicom* that doesn't belong with the core software, see our contribution repository:
[contrib-pydicom](https://www.github.com/pydicom/contrib-pydicom).
