"""
=======================================
Read DICOM and ploting using matplotlib
=======================================

This example illustrates how to open a DICOM file and show it using matplotlib.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import matplotlib.pyplot as plt
import pydicom
from pydicom.data import get_testdata_files

print(__doc__)

filename = get_testdata_files('CT_small.dcm')[0]
dataset = pydicom.read_file(filename)
plt.imshow(dataset.pixel_array, cmap=plt.cm.bone)
plt.show()
