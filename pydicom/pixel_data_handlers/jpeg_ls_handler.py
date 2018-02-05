"""
Use the jpeg_ls (CharPyLS) python package
to decode pixel transfer syntaxes.
"""
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


def needs_to_convert_to_RGB(dicom_dataset):
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    should_change = dicom_dataset.SamplesPerPixel == 3
    return should_change


def supports_transfer_syntax(dicom_dataset):
    """
    Returns
    -------
    bool
        True if this pixel data handler might support this transfer syntax.

        False to prevent any attempt to try to use this handler
        to decode the given transfer syntax
    """
    return (dicom_dataset.file_meta.TransferSyntaxUID
            in JPEGLSSupportedTransferSyntaxes)


def get_pixeldata(dicom_dataset, frame_list=None):
    """
    Use the jpeg_ls package to decode the PixelData attribute

    Parameters
    ----------
    frame_list : List[int], optional
        One-based frame numbers.

    Returns
    -------
    numpy.ndarray

        A correctly sized (but not shaped) numpy array
        of the entire data volume

    Raises
    ------
    ImportError
        if the required packages are not available

    NotImplementedError
        if the transfer syntax is not supported

    TypeError
        if the pixel data type is not supported

    ValueError
        if specified frames do not exist
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

    if frame_list is not None:
        if 'NumberOfFrames' not in dicom_dataset:
            msg = ("The NumberOfFrames attribute is required to read "
                   "individual frames from the Pixel Data element.")
            raise ValueError(msg)
        for frame_num in frame_list:
            if frame_num > int(dicom_dataset.NumberOfFrames):
                msg = ("Frame number {} exceeds total number of frames in "
                       "Pixel Data element.".format(frame_num))
                raise ValueError(msg)

    if (dicom_dataset.is_little_endian !=
            sys_is_little_endian):
        numpy_format = numpy_format.newbyteorder('S')

    # decompress here
    UncompressedPixelData = b''
    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        # multiple compressed frames
        data_elem = dicom_dataset.raw_data_element('PixelData')
        if frame_list is not None and data_elem.value is None:
            filename = dicom_dataset.filename
            fileobj_type = dicom_dataset.fileobj_type
            is_little_endian = data_elem.is_little_endian
            data_elem_offset = data_elem.value_tell
            # Causes ImportError when imported at top level
            from pydicom.filereader import read_frame
            with fileobj_type(filename, 'rb') as fp:
                CompressedPixelDataSeq = []
                for frame_num in frame_list:
                    data = read_frame(fp, is_little_endian,
                                      data_elem_offset, frame_num)
                    seq = pydicom.encaps.decode_data_sequence(data, False)
                    CompressedPixelDataSeq.append(seq)
        else:
            CompressedPixelDataSeq = \
                pydicom.encaps.decode_data_sequence(dicom_dataset.PixelData)
        for index, frame in enumerate(CompressedPixelDataSeq):
            if frame_list is not None and (index + 1) not in frame_list:
                continue
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
    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    return pixel_array
