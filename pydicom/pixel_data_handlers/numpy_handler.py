import sys
have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

sys_is_little_endian = (sys.byteorder == 'little')


def get_pixeldata(self):
    """If NumPy is available, return an ndarray of the Pixel Data.
    Raises
    ------
    TypeError
        If there is no Pixel Data or not a supported data type.
    ImportError
        If NumPy isn't found
    Returns
    -------
    numpy.ndarray
        The contents of the Pixel Data element (7FE0,0010) as an ndarray.
    """
    if not self._is_uncompressed_transfer_syntax():
        raise NotImplementedError("Pixel Data is compressed in a "
                                  "format pydicom does not yet handle. "
                                  "Cannot return array. Pydicom might "
                                  "be able to convert the pixel data "
                                  "using GDCM if it is installed.")
    if not have_numpy:
        msg = "The Numpy package is required to use pixel_array, and " \
              "numpy could not be imported."
        raise ImportError(msg)
    if 'PixelData' not in self:
        raise TypeError("No pixel data found in this dataset.")

    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    #    self.PixelRepresentation -- 0 for unsigned, 1 for signed;
    #    self.BitsAllocated -- 8, 16, or 32
    format_str = '%sint%d' % (('u', '')[self.PixelRepresentation],
                              self.BitsAllocated)
    try:
        numpy_dtype = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='%s', PixelRepresentation=%d, BitsAllocated=%d")
        raise TypeError(msg % (format_str, self.PixelRepresentation,
                               self.BitsAllocated))

    if self.is_little_endian != sys_is_little_endian:
        numpy_dtype = numpy_dtype.newbyteorder('S')

    pixel_bytearray = self.PixelData

    pixel_array = numpy.fromstring(pixel_bytearray, dtype=numpy_dtype)
    length_of_pixel_array = pixel_array.nbytes
    expected_length = self.Rows * self.Columns
    if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
        expected_length *= self.NumberOfFrames
    if 'SamplesPerPixel' in self and self.SamplesPerPixel > 1:
        expected_length *= self.SamplesPerPixel
    if self.BitsAllocated > 8:
        expected_length *= (self.BitsAllocated // 8)
    if length_of_pixel_array != expected_length:
        raise AttributeError("Amount of pixel data %d does not match the expected data %d" % (length_of_pixel_array, expected_length))
    return pixel_array
