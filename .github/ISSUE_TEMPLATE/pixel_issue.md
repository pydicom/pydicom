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
Please run the following and paste the output.
```bash
$ python -c "import platform; print(platform.platform())"
$ python -c "import sys; print('Python ', sys.version)"
$ python -c "import pydicom; print('pydicom ', pydicom.__version__)"
```
