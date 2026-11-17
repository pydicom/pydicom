"""
==========================================================
Load CT slices and plot axial, sagittal and coronal images
==========================================================

This example illustrates loading multiple files, sorting them by slice
location, building a 3D image and reslicing it in different planes.

.. usage:

   reslice.py <glob>
   where <glob> refers to a set of DICOM image files.

   Example: python reslice.py "*.dcm". The quotes are needed to protect
   the glob from your system and leave it for the script.

.. note:

   Uses numpy and matplotlib.

   Tested using series 2 from here
   https://www.pcir.org/researchers/54879843_20060101.html
"""

import pydicom
import numpy as np
import matplotlib.pyplot as plt
import sys
import glob

# load the DICOM files
files = []
print(f"glob: {sys.argv[1]}")
for fname in glob.glob(sys.argv[1], recursive=False):
    print(f"loading: {fname}")
    files.append(pydicom.dcmread(fname))

print(f"file count: {len(files)}")

# skip files with no SliceLocation (eg scout views)
slices = []
skipcount = 0
for f in files:
    if hasattr(f, "SliceLocation"):
        slices.append(f)
    else:
        skipcount = skipcount + 1

print(f"skipped, no SliceLocation: {skipcount}")

# ensure they are in the correct order
slices = sorted(slices, key=lambda s: s.SliceLocation)

# pixel aspects, assuming all slices are the same.
# PixelSpacing is the space BETWEEN rows and BETWEEN columns respectively: the first
# value is the distance between the centers of adjacent rows (vertical spacing) and the
# second the distance between the centers of adjacent columns (horizontal spacing).
# See DICOM PS3.3 Section 10.7.1.3.
row_spacing, col_spacing = slices[0].PixelSpacing
slice_spacing = slices[0].SliceThickness
# set_aspect() takes the displayed size of one y unit over one x unit, for the
# array that each subplot below actually shows.
ax_aspect = row_spacing / col_spacing  # img3d[:, :, k] is (row, column)
sag_aspect = row_spacing / slice_spacing  # img3d[:, j, :] is (row, slice)
cor_aspect = slice_spacing / col_spacing  # img3d[i, :, :].T is (slice, column)

# create 3D array
img_shape = list(slices[0].pixel_array.shape)
img_shape.append(len(slices))
img3d = np.zeros(img_shape)

# fill 3D array with the images from the files
for i, s in enumerate(slices):
    img2d = s.pixel_array
    img3d[:, :, i] = img2d

# plot 3 orthogonal slices
a1 = plt.subplot(2, 2, 1)
plt.imshow(img3d[:, :, img_shape[2] // 2])
a1.set_aspect(ax_aspect)

a2 = plt.subplot(2, 2, 2)
plt.imshow(img3d[:, img_shape[1] // 2, :])
a2.set_aspect(sag_aspect)

a3 = plt.subplot(2, 2, 3)
plt.imshow(img3d[img_shape[0] // 2, :, :].T)
a3.set_aspect(cor_aspect)

plt.show()
