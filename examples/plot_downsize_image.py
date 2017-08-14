"""
================================
Downsize MRI image using pydicom
================================

This example shows how to downsize an MR image from :math:`512 \times 512` to
:math:`64 \times 64`. The downsizing is performed by taking the central section
instead of averagin the pixels. Finally, the image is store as a dicom image.

"""

# Authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# License :

import pydicom as pdcm
