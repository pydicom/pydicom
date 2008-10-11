# image.py
"""Routines for viewing DICOM image data

"""
#
# Copyright (C) 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

have_PIL=True
try:
    import PIL.Image
except:
    have_PIL = False

# Display an image using the Python Imaging Library (PIL)
def show_PIL(dataset):
    if not have_PIL:
        raise ImportError, "Python Imaging Library is not available. See http://www.pythonware.com/products/pil/ to download and install"
    if 'PixelData' not in dataset:
        raise TypeError, "Cannot show image -- DICOM dataset does not have pixel data"

    # Map BitsAllocated and SamplesperPixel to PIL's "mode"
    # PIL mode info from http://www.pythonware.com/library/pil/handbook/concepts.htm    
    bits = dataset.BitsAllocated
    samples = dataset.SamplesperPixel
    if bits == 8 and samples == 1:
        mode = "L"
    elif bits == 8 and samples == 3:
        mode = "RGB"
    elif bits == 16:
        mode = "I;16" # not sure about this -- PIL source says is 'experimental' and no documentation. Also, should bytes swap depedning on endian of file and system??
    else:
        raise TypeError, "Don't know PIL mode for %d BitsAllocated and %d SamplesPerPixel" % (bits, samples)
    
    # PIL size = (width, height)
    size = (dataset.Columns, dataset.Rows)
    
    im = PIL.Image.frombuffer(mode, size, dataset.PixelData, "raw", mode, 0, 1) # Recommended to specifiy all details by http://www.pythonware.com/library/pil/handbook/image.htm
    im.show()
        
