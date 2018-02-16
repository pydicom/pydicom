<!-- Instructions For Filing a Bug: https://github.com/pydicom/pydicom/blob/master/CONTRIBUTING.md#filing-bugs -->

#### Description
<!-- Example: Attribute Error thrown when printing (0x0010, 0x0020) patient Id> 0-->

#### Steps/Code to Reproduce
<!--
Example:
```py
from io import BytesIO
from pydicom import dcmread

bytestream = b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
             b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00' \
             b'\x55\x49\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38' \
             b'\x2e\x31\x2e\x32\x00\x20\x20\x10\x00\x02\x00\x00\x00\x01\x00\x20\x20' \
             b'\x20\x00\x06\x00\x00\x00\x4e\x4f\x52\x4d\x41\x4c'

fp = BytesIO(bytestream)
ds = dcmread(fp, force=True)

print(ds.PatientID)
```
If the code is too long, feel free to put it in a public gist and link
it in the issue: https://gist.github.com

When possible use pydicom testing examples to reproduce the errors. Otherwise, provide
an anonymous version of the data in order to replicate the errors.
-->

#### Expected Results
<!-- Please paste or describe the expected results.
Example: No error is thrown and the name of the patient is printed.-->

#### Actual Results
<!-- Please paste or specifically describe the actual output or traceback.
(Use %xmode to deactivate ipython's trace beautifier)
Example: ```AttributeError: 'FileDataset' object has no attribute 'PatientID'```
-->

#### Versions
<!--
Please run the following snippet and paste the output below.
import platform; print(platform.platform())
import sys; print("Python", sys.version)
import pydicom; print("pydicom", pydicom.__version__)
-->


<!-- Thanks for contributing! -->
