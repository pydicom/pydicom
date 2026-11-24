---
name: Pixel Data issue
about: For issues related to Pixel Data or one of the bulk data handlers
title: ''
labels: pixel-data
assignees: ''

---

<!--
All AI-generated content must be explicitly labelled as such. Failure to abide by
this rule will result in your issue being de-prioritised or closed.

If you are experiencing a real world issue with real world code or DICOM data please
say so and you will be given a higher priority.
-->

**Describe the issue**

Please include:
* A clear description of what the issue is
* (If relevant) **anonymized** screenshots that demonstrate the issue
* The output from `python -m pydicom.env_info`


**Steps to reproduce**

A way for us to reproduce and troubleshoot the issue:
* A minimum working code sample that demonstrates the issue.
* The *entire* traceback (if one occurred).

It's also extremely helpful if you can include one of the following:
* The **anonymized** DICOM dataset, which can be attached to the issue as a zip archive, or
* The output from:

  ```python
  from pydicom import dcmread
  from pydicom.util import debug_pixel_data

  ds = dcmread("/path/to/the/dataset")
  debug_pixel_data(ds)
