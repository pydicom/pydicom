"""
================================
Downsize MRI image using pydicom
================================

This example shows how to downsize an MR image from :math:`512 \times 512` to
:math:`64 \times 64`. The downsizing is performed by taking the central section
instead of averagin the pixels. Finally, the image is store as a dicom image.

.. note::

   This example requires the Numpy library to manipulate the pixel data.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import pydicom
from pydicom.data import get_testdata_file

print(__doc__)

# FIXME: add a full-sized MR image in the testing data
filename = get_testdata_file('MR_small.dcm')
ds = pydicom.dcmread(filename)

# get the pixel information into a numpy array
data = ds.pixel_array
print('The image has {} x {} voxels'.format(data.shape[0],
                                            data.shape[1]))
data_downsampling = data[::8, ::8]
print('The downsampled image has {} x {} voxels'.format(
    data_downsampling.shape[0], data_downsampling.shape[1]))

# copy the data back to the original data set
ds.PixelData = data_downsampling.tobytes()
# update the information regarding the shape of the data array
ds.Rows, ds.Columns = data_downsampling.shape

# print the image information given in the dataset
print('The information of the data set after downsampling: \n')
print(ds)
