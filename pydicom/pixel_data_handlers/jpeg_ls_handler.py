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

JPEGLSSupportedTransferSyntaxes = [
    pydicom.uid.JPEGLSLossless,
    pydicom.uid.JPEGLSLossy,
]


def supports_transfer_syntax(dicom_dataset):
    return (dicom_dataset.file_meta.TransferSyntaxUID
            in JPEGLSSupportedTransferSyntaxes)


def get_pixeldata(dicom_dataset):
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
    if (dicom_dataset.file_meta.TransferSyntaxUID
            not in JPEGLSSupportedTransferSyntaxes):
        msg = ("The jpeg_ls does not support "
               "this transfer syntax {0}.".format(
                   dicom_dataset.file_meta.TransferSyntaxUID))
        raise NotImplementedError(msg)

    if not have_jpeg_ls:
        msg = ("The jpeg_ls package is required to use pixel_array "
               "for this transfer syntax {0}, and jpeg_ls could not "
               "be imported.".format(
                   dicom_dataset.file_meta.TransferSyntaxUID))
        raise ImportError(msg)
    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    # dicom_dataset.PixelRepresentation -- 0 for unsigned, 1 for signed;
    # dicom_dataset.BitsAllocated -- 8, 16, or 32
    if dicom_dataset.PixelRepresentation == 0:
        format_str = 'uint{}'.format(dicom_dataset.BitsAllocated)
    elif dicom_dataset.PixelRepresentation == 1:
        format_str = 'int{}'.format(dicom_dataset.BitsAllocated)
    else:
        format_str = 'bad_pixel_representation'
    try:
        numpy_format = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='{}', PixelRepresentation={}, "
               "BitsAllocated={}".format(
                   format_str,
                   dicom_dataset.PixelRepresentation,
                   dicom_dataset.BitsAllocated))
        raise TypeError(msg)

    if (dicom_dataset.is_little_endian !=
            sys_is_little_endian):
        numpy_format = numpy_format.newbyteorder('S')

    # decompress here
    UncompressedPixelData = b''
    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        # multiple compressed frames
        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(
            dicom_dataset.PixelData)
        # print len(CompressedPixelDataSeq)
        for frame in CompressedPixelDataSeq:
            decompressed_image = jpeg_ls.decode(
                numpy.fromstring(frame, dtype=numpy.uint8))
            UncompressedPixelData += decompressed_image.tobytes()
    else:
        # single compressed frame
        CompressedPixelData = pydicom.encaps.defragment_data(
            dicom_dataset.PixelData)
        decompressed_image = jpeg_ls.decode(
            numpy.fromstring(CompressedPixelData, dtype=numpy.uint8))
        UncompressedPixelData = decompressed_image.tobytes()

    pixel_array = numpy.fromstring(UncompressedPixelData, numpy_format)
    return pixel_array
