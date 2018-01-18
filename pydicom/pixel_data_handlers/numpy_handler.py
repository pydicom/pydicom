"""Use the numpy package to decode pixel transfer syntaxes."""
import sys
import pydicom.uid
have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

sys_is_little_endian = (sys.byteorder == 'little')

NumpySupportedTransferSyntaxes = [
    pydicom.uid.ExplicitVRLittleEndian,
    pydicom.uid.ImplicitVRLittleEndian,
    pydicom.uid.DeflatedExplicitVRLittleEndian,
    pydicom.uid.ExplicitVRBigEndian,
]


def supports_transfer_syntax(dicom_dataset):
    """
    Returns
    -------
    bool
        True if this pixel data handler might support this transfer syntax.

        False to prevent any attempt to try to use this handler
        to decode the given transfer syntax
    """
    return (dicom_dataset.file_meta.TransferSyntaxUID in
            NumpySupportedTransferSyntaxes)


def needs_to_convert_to_RGB(dicom_dataset):
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    return False


def get_pixeldata(dicom_dataset, frame_list=None):
    """If NumPy is available, return an ndarray of the Pixel Data.

    Parameters
    ----------
    frame_list : List[int], optional
        One-based indices of frames within the Pixel Data Element.

    Raises
    ------
    TypeError
        If there is no Pixel Data or not a supported data type.

    ImportError
        If NumPy isn't found

    NotImplementedError
        if the transfer syntax is not supported

    AttributeError
        if the decoded amount of data does not match the expected amount

    ValueError
        if specified frames do not exist

    Returns
    -------
    numpy.ndarray
       The contents of the Pixel Data element (7FE0,0010) as an ndarray.
    """
    if (dicom_dataset.file_meta.TransferSyntaxUID not in
            NumpySupportedTransferSyntaxes):
        raise NotImplementedError("Pixel Data is compressed in a "
                                  "format pydicom does not yet handle. "
                                  "Cannot return array. Pydicom might "
                                  "be able to convert the pixel data "
                                  "using GDCM if it is installed.")
    if not have_numpy:
        msg = ("The Numpy package is required to use pixel_array, and "
               "numpy could not be imported.")
        raise ImportError(msg)
    if 'PixelData' not in dicom_dataset:
        raise TypeError("No pixel data found in this dataset.")

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
        numpy_dtype = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='{}', PixelRepresentation={}, "
               "BitsAllocated={}".format(
                   format_str,
                   dicom_dataset.PixelRepresentation,
                   dicom_dataset.BitsAllocated))
        raise TypeError(msg)

    if dicom_dataset.is_little_endian != sys_is_little_endian:
        numpy_dtype = numpy_dtype.newbyteorder('S')

    expected_length = dicom_dataset.Rows * dicom_dataset.Columns
    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        expected_length *= dicom_dataset.NumberOfFrames
    if ('SamplesPerPixel' in dicom_dataset and
            dicom_dataset.SamplesPerPixel > 1):
        expected_length *= dicom_dataset.SamplesPerPixel
    if dicom_dataset.BitsAllocated > 8:
        expected_length *= (dicom_dataset.BitsAllocated // 8)

    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        if frame_list is not None and data_elem.value is None:
            filename = dicom_dataset.filename
            fileobj_type = dicom_dataset.fileobj_type
            is_little_endian = data_elem.is_little_endian
            data_elem_offset = data_elem.value_tell
            # Causes ImportError when imported at top level
            from pydicom.filereader import read_frame
            with fileobj_type(filename, 'rb') as fp:
                CompressedPixelDataSeq = []
                pixel_bytearray = b''
                for frame_num in frame_list:
                    data = read_frame(fp, is_little_endian,
                                      data_elem_offset, frame_num)
                    pixel_bytearray += data
        else:
            pixel_bytearray = dicom_dataset.PixelData
    else:
        pixel_bytearray = dicom_dataset.PixelData

    pixel_array = numpy.fromstring(pixel_bytearray, dtype=numpy_dtype)
    length_of_pixel_array = pixel_array.nbytes

    if length_of_pixel_array != expected_length:
        raise AttributeError(
            "Amount of pixel data %d does not "
            "match the expected data %d" %
            (length_of_pixel_array, expected_length))
    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"

    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):
        if frame_list is not None:
            frame_indices = [frame_num-1 for frame_num in frame_list]
            pixel_array = pixel_array[frame_indices, ...]
    return pixel_array
