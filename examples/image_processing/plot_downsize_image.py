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

from pydicom import examples

print(__doc__)

# FIXME: add a full-sized MR image in the testing data
ds = examples.mr

# get the pixel information into a numpy array
arr = ds.pixel_array
print(f"The image has {arr.shape[0]} x {arr.shape[1]} voxels")
arr_downsampled = arr[::8, ::8]
print(
    f"The downsampled image has {arr_downsampled.shape[0]} x {arr_downsampled.shape[1]} voxels"
)

# copy the data back to the original data set
ds.PixelData = arr_downsampled.tobytes()
# update the information regarding the shape of the data array
ds.Rows, ds.Columns = arr_downsampled.shape

# print the image information given in the dataset
print("The information of the data set after downsampling: \n")
print(ds)
