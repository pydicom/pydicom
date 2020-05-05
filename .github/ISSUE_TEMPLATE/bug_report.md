---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**Expected behavior**
What you expected to happen (please include a reference to the DICOM standard
if relevant).

**Steps To Reproduce**
How to reproduce the issue. Please include a minimum working code sample, the
traceback (if any) and the anonymized DICOM dataset (if relevant).

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