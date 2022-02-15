---
name: Pixel Data issue
about: For issues related to Pixel Data or one of the bulk data handlers
title: ''
labels: pixel-data
assignees: ''

---

<!--
If your issue is that the pixel data "looks green/teal", or has strange colors, you probably need to apply a YCbCr to RGB color space conversion using `pydicom.pixel_data_handlers.convert_color_space()`.

See also: https://github.com/pydicom/pydicom/discussions/1577
-->

**Describe the issue**

Please include:
* A clear description of what the issue is
* (If relevant) **anonymized** screenshots that demonstrate the issue
* The output from `python -m pydicom.env_info`


**Steps to reproduce**

A way for us to reproduce and troubleshoot the issue:
* A minimum working code sample
* The *entire* traceback (if one occurred).

It's also extremely helpful if you can include one of the following:
* The **anonymized** DICOM dataset, which can be attached to the issue as a zip archive, or
* The output from:

  For **pydicom >= 2.3**:
  ```python
  from pydicom import dcmread
  from pydicom.util import debug_pixel_data

  ds = dcmread("/path/to/the/dataset")
  debug_pixel_data(ds)
  ```

  For **pydicom < 2.3**:
  ```python
  from pydicom import dcmread

  ds = dcmread("/path/to/the/dataset")
  print(ds.file_meta.get("TransferSyntaxUID", "(no transfer syntax)"))
  print(ds.group_dataset(0x0028))
  print(ds.group_dataset(0x7FE0))
  ```
