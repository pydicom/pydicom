import sys
import pydicom
import pydicom.uid
have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

have_jpeg_ls = True
try:
    import jpeg_ls
except ImportError:
    have_jpeg_ls = False
    raise
sys_is_little_endian = (sys.byteorder == 'little')


def get_pixeldata(self):
    """Use jpeg_ls to decompress compressed Pixel Data.

    Returns
    -------
    bytes or str
        The decompressed Pixel Data

    Raises
    ------
    ImportError
        If jpeg_ls is not available.
    """
    if self.file_meta.TransferSyntaxUID not in pydicom.uid.JPEGLSSupportedCompressedPixelTransferSyntaxes:
        msg = "The jpeg_ls does not support this transfer syntax {0}.".format(self.file_meta.TransferSyntaxUID)
        raise NotImplementedError(msg)

    if not have_jpeg_ls:
        msg = "The jpeg_ls package is required to use pixel_array for " \
              "this transfer syntax {0}, and jpeg_ls could not be " \
              "imported.".format(self.file_meta.TransferSyntaxUID)
        raise ImportError(msg)
    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    #    self.PixelRepresentation -- 0 for unsigned, 1 for signed;
    #    self.BitsAllocated -- 8, 16, or 32
    format_str = '%sint%d' % (('u', '')[self.PixelRepresentation],
                              self.BitsAllocated)
    try:
        numpy_format = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='%s', PixelRepresentation=%d, BitsAllocated=%d")
        raise TypeError(msg % (format_str, self.PixelRepresentation,
                               self.BitsAllocated))

    if self.is_little_endian != sys_is_little_endian:
        numpy_format = numpy_format.newbyteorder('S')

    # decompress here
    UncompressedPixelData = ''
    if 'NumberOfFrames' in self and self.NumberOfFrames > 1:
        # multiple compressed frames
        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(self.PixelData)
        # print len(CompressedPixelDataSeq)
        for frame in CompressedPixelDataSeq:
            decompressed_image = jpeg_ls.decode(numpy.fromstring(frame, dtype=numpy.uint8))
            UncompressedPixelData += decompressed_image.tobytes()
    else:
        # single compressed frame
        CompressedPixelData = pydicom.encaps.defragment_data(self.PixelData)
        decompressed_image = jpeg_ls.decode(numpy.fromstring(CompressedPixelData, dtype=numpy.uint8))
        UncompressedPixelData = decompressed_image.tobytes()

    pixel_array = numpy.fromstring(UncompressedPixelData, numpy_format)
    return pixel_array
