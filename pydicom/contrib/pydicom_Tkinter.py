# pydicom_Tkinter.py
#
# Copyright (c) 2009 Daniel Nanz
# This file is released under the pydicom (https://github.com/darcymason/pydicom)
# license, see the file license.txt available at
# (https://github.com/darcymason/pydicom)
#
# revision history:
# Dec-08-2009: version 0.1
#
# 0.1:   tested with pydicom version 0.9.3, Python version 2.6.2 (32-bit)
#        under Windows XP Professional 2002, and Mac OS X 10.5.5,
#        using numpy 1.3.0 and a small random selection of MRI and
#        CT images.
'''
View DICOM images from pydicom

requires numpy:  http://numpy.scipy.org/

Usage:
------
>>> import pydicom              # pydicom
>>> import pydicom.contrib.pydicom_Tkinter as pydicom_Tkinter    # this module

>>> df = pydicom.read_file(filename)
>>> pydicom_Tkinter.show_image(df)
'''

import tempfile
import os

from pydicom.compat import in_py2
if in_py2:
    import Tkinter as tkinter

have_numpy = True
try:
    import numpy as np
except ImportError:
    # will not work...
    have_numpy = False


def get_PGM_bytedata_string(arr):
    '''Given a 2D numpy array as input write gray-value image data in the PGM
    format into a byte string and return it.

    arr: single-byte unsigned int numpy array
    note: Tkinter's PhotoImage object seems to accept only single-byte data
    '''

    if arr.dtype != np.uint8:
        raise ValueError
    if len(arr.shape) != 2:
        raise ValueError

    # array.shape is (#rows, #cols) tuple; PGM input needs this reversed
    col_row_string = ' '.join(reversed([str(x) for x in arr.shape]))

    bytedata_string = '\n'.join(('P5',
                                 col_row_string,
                                 str(arr.max()),
                                 arr.tostring()))
    return bytedata_string


def get_PGM_from_numpy_arr(arr, window_center, window_width,
                           lut_min=0, lut_max=255):
    '''real-valued numpy input  ->  PGM-image formatted byte string

    arr: real-valued numpy array to display as grayscale image
    window_center, window_width: to define max/min values to be mapped to the
                                 lookup-table range. WC/WW scaling is done
                                 according to DICOM-3 specifications.
    lut_min, lut_max: min/max values of (PGM-) grayscale table: do not change
    '''

    if np.isreal(arr).sum() != arr.size:
        raise ValueError

    # currently only support 8-bit colors
    if lut_max != 255:
        raise ValueError

    if arr.dtype != np.float64:
        arr = arr.astype(np.float64)

    # LUT-specific array scaling
    # width >= 1 (DICOM standard)
    window_width = max(1, window_width)

    wc, ww = np.float64(window_center), np.float64(window_width)
    lut_range = np.float64(lut_max) - lut_min

    minval = wc - 0.5 - (ww - 1.0) / 2.0
    maxval = wc - 0.5 + (ww - 1.0) / 2.0

    min_mask = (minval >= arr)
    to_scale = (arr > minval) & (arr < maxval)
    max_mask = (arr >= maxval)

    if min_mask.any():
        arr[min_mask] = lut_min
    if to_scale.any():
        arr[to_scale] = ((arr[to_scale] - (wc - 0.5)) /
                         (ww - 1.0) + 0.5) * lut_range + lut_min
    if max_mask.any():
        arr[max_mask] = lut_max

    # round to next integer values and convert to unsigned int
    arr = np.rint(arr).astype(np.uint8)

    # return PGM byte-data string
    return get_PGM_bytedata_string(arr)


def get_tkinter_photoimage_from_pydicom_image(data):
    '''
    Wrap data.pixel_array in a Tkinter PhotoImage instance,
    after conversion into a PGM grayscale image.

    This will fail if the "numpy" module is not installed in the attempt of
    creating the data.pixel_array.

    data:  object returned from pydicom.read_file()
    side effect: may leave a temporary .pgm file on disk
    '''

    # get numpy array as representation of image data
    arr = data.pixel_array.astype(np.float64)

    # pixel_array seems to be the original, non-rescaled array.
    # If present, window center and width refer to rescaled array
    # -> do rescaling if possible.
    if ('RescaleIntercept' in data) and ('RescaleSlope' in data):
        intercept = data.RescaleIntercept  # single value
        slope = data.RescaleSlope
        arr = slope * arr + intercept

    # get default window_center and window_width values
    wc = (arr.max() + arr.min()) / 2.0
    ww = arr.max() - arr.min() + 1.0

    # overwrite with specific values from data, if available
    if ('WindowCenter' in data) and ('WindowWidth' in data):
        wc = data.WindowCenter
        ww = data.WindowWidth
        try:
            wc = wc[0]            # can be multiple values
        except:
            pass
        try:
            ww = ww[0]
        except:
            pass

    # scale array to account for center, width and PGM grayscale range,
    # and wrap into PGM formatted ((byte-) string
    pgm = get_PGM_from_numpy_arr(arr, wc, ww)

    # create a PhotoImage
    # for as yet unidentified reasons the following fails for certain
    # window center/width values:
    #         photo_image = Tkinter.PhotoImage(data=pgm, gamma=1.0)
    #    Error with Python 2.6.2 under Windows XP:
    #          (self.tk.call(('image', 'create', imgtype, name,) + options)
    #          _tkinter.TclError: truncated PPM data
    #    OsX: distorted images
    # while all seems perfectly OK for other values of center/width or when
    # the PGM is first written to a temporary file and read again

    # write PGM file into temp dir
    (os_id, abs_path) = tempfile.mkstemp(suffix='.pgm')
    with open(abs_path, 'wb') as fd:
        fd.write(pgm)

    photo_image = tkinter.PhotoImage(file=abs_path, gamma=1.0)

    # close and remove temporary file on disk
    # os.close is needed under windows for os.remove not to fail
    try:
        os.close(os_id)
        os.remove(abs_path)
    except:
        pass  # silently leave file on disk in temp-like directory

    return photo_image


def show_image(data, block=True, master=None):
    '''
    Get minimal Tkinter GUI and display a pydicom data.pixel_array

    data: object returned from pydicom.read_file()
    block: if True run Tk mainloop() to show the image
    master: use with block==False and an existing Tk widget as parent widget

    side effects: may leave a temporary .pgm file on disk
    '''
    frame = tkinter.Frame(master=master, background='#000')
    if 'SeriesDescription' in data and 'InstanceNumber' in data:
        title = ', '.join(('Ser: ' + data.SeriesDescription,
                           'Img: ' + str(data.InstanceNumber)))
    else:
        title = 'pydicom image'
    frame.master.title(title)
    photo_image = get_tkinter_photoimage_from_pydicom_image(data)
    label = tkinter.Label(frame, image=photo_image, background='#000')
    # keep a reference to avoid disappearance upon garbage collection
    label.photo_reference = photo_image
    label.grid()
    frame.grid()

    if block:
        frame.mainloop()
