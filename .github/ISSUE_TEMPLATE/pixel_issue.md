---
name: Pixel Data issue
about: For issues related to Pixel Data or one of the bulk data handlers
title: ''
labels: pixel-data
assignees: ''

---

**Describe the issue**
A clear and concise description of what the issue is. It is very helpful if you
can upload screenshots showing the issue.

**Expected behavior**
What you expected to happen.

**Steps To Reproduce**
How to reproduce the issue. Please include:
1. A minimum working code sample
2. The traceback (if one occurred)
3. Which of the following packages are available and their versions:
  * Numpy
  * Pillow
  * JPEG-LS
  * GDCM
4. The anonymized DICOM dataset (if possible).

**Your environment**
If you're using **pydicom 2 or later**, please use the `pydicom.env_info`
module to gather information about your environment and paste it in the issue:

```bash
$ python -m pydicom.env_info
```

For **pydicom 1.x**, please run the following code snippet and paste the
output.

```python
import platform, sys, pydicom
print(platform.platform(),
      "\nPython", sys.version,
      "\npydicom", pydicom.__version__)
```
