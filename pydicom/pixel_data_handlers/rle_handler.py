import sys
import pydicom.uid
import pydicom.encaps
from struct import unpack
have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

sys_is_little_endian = (sys.byteorder == 'little')

RLESupportedTransferSyntaxes = [
    pydicom.uid.RLELossless,
]


def supports_transfer_syntax(dicom_dataset):
    return (dicom_dataset.file_meta.TransferSyntaxUID in
            RLESupportedTransferSyntaxes)


def needs_to_convert_to_RGB(dicom_dataset):
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    return False


def get_pixeldata(dicom_dataset):
    """If NumPy is available, return an ndarray of the Pixel Data.
    Raises
    ------
    TypeError
        If there is no Pixel Data or not a supported data type.
    ImportError
        If NumPy isn't found
    NotImplementedError
        If cannot handle the format
    Returns
    -------
    numpy.ndarray
       The contents of the Pixel Data element (7FE0,0010) as an ndarray.
    """
    if (dicom_dataset.file_meta.TransferSyntaxUID not in
            RLESupportedTransferSyntaxes):
        raise NotImplementedError("Pixel Data is compressed in a "
                                  "format this RLE decompressor"
                                  "does not yet handle. "
                                  "Cannot return array. Pydicom might "
                                  "be able to convert the pixel data "
                                  "using GDCM if it is installed.")
    if not have_numpy:
        msg = ("The Numpy package is required to use pixel_array, and "
               "numpy could not be imported.")
        raise ImportError(msg)

    if 'PixelData' not in dicom_dataset:
        raise TypeError("No pixel data found in this dataset.")

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

    UncompressedPixelData = bytearray()

    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):

        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(
            dicom_dataset.PixelData)

        for frame in CompressedPixelDataSeq:
            decompressed_frame = _rle_decode_frame(frame,
                                                   rows=dicom_dataset.Rows,
                                                   columns=dicom_dataset.Columns,  # noqa
                                                   samples_per_pixel=dicom_dataset.SamplesPerPixel,  # noqa
                                                   bits_allocated=dicom_dataset.BitsAllocated)  # noqa

            UncompressedPixelData.extend(decompressed_frame)

    else:

        CompressedPixelData = pydicom.encaps.defragment_data(
            dicom_dataset.PixelData)

        decompressed_frame = _rle_decode_frame(CompressedPixelData,
                                               rows=dicom_dataset.Rows,
                                               columns=dicom_dataset.Columns,
                                               samples_per_pixel=dicom_dataset.SamplesPerPixel,  # noqa
                                               bits_allocated=dicom_dataset.BitsAllocated)  # noqa

        UncompressedPixelData.extend(decompressed_frame)

    pixel_array = numpy.frombuffer(UncompressedPixelData, numpy_format)
    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"
    return pixel_array


def _rle_decode_frame(data, rows, columns, samples_per_pixel, bits_allocated):
    """Decodes a single frame of RLE encoded data.
    Reads the plane information at the beginning of the data.
    If more than pixel size > 1 byte appropriately interleaves the data from
    the high and low planes. Data is always stored big endian. Output always
    little endian

    Parameters
    ----------
    data: bytes
        The RLE frame data
    rows: int
        The number of output rows
    columns: int
        The number of output columns
    samples_per_pixel: int
        Number of samples per pixel (e.g. 3 for RGB data).
    bits_allocated: int
        Number of bits per sample - must be a multiple of 8

    Returns
    -------
    bytearray
        The decompressed data
    """

    rle_start = 0
    rle_len = len(data)

    number_of_planes = unpack(b'<L', data[rle_start: rle_start + 4])[0]

    if bits_allocated % 8 != 0:
        raise NotImplementedError("Don't know how to handle BitsAllocated "
                                  "not being a multiple of bytes")

    bytes_allocated = bits_allocated // 8

    expected_number_of_planes = samples_per_pixel * bytes_allocated

    if number_of_planes != expected_number_of_planes:
        raise AttributeError("Unexpected number of planes")

    plane_start_list = []
    for i in range(number_of_planes):
        header_offset_start = rle_start + 4 + (4 * i)
        header_offset_end = rle_start + 4 + (4 * (i + 1))
        plane_start_in_rle = unpack(b'<L', data[header_offset_start:header_offset_end])[0]  # noqa
        plane_start_list.append(plane_start_in_rle + rle_start)

    plane_end_list = plane_start_list[1:]
    plane_end_list.append(rle_len + rle_start)

    frame_bytes = bytearray(rows * columns * samples_per_pixel * bytes_allocated)  # noqa

    for sample_number in range(samples_per_pixel):
        for byte_number in range(bytes_allocated):

            plane_number = byte_number + (sample_number * bytes_allocated)
            out_plane_number = ((sample_number + 1) * bytes_allocated) - byte_number - 1  # noqa
            plane_start = plane_start_list[plane_number]
            plane_end = plane_end_list[plane_number]

            plane_bytes = _rle_decode_plane(data[plane_start:plane_end])

            if len(plane_bytes) != rows * columns:
                raise AttributeError("Different number of bytes unpacked "
                                     "from RLE than expected")

            frame_bytes[out_plane_number::samples_per_pixel * bytes_allocated] = plane_bytes  # noqa

    return frame_bytes


def _rle_decode_plane(data):
    """Return a single plane of decoded RLE data.

    Parameters
    ----------
    data : bytes
        The data to be decompressed.

    Returns
    -------
    bytearray
        The decompressed data.
    """

    data = bytearray(data)
    result = bytearray()
    pos = 0
    len_data = len(data)

    while pos < len_data:
        header_byte = data[pos]
        pos += 1
        if header_byte > 128:
            # Extend by copying the next byte (-N + 1) times
            # however since using uint8 instead of int8 this will be
            # (256 - N + 1) times
            result.extend(data[pos:pos + 1] * (257 - header_byte))
            pos += 1
            continue

        if header_byte < 128:
            # Extend by literally copying the next (N + 1) bytes
            result.extend(data[pos:pos + header_byte + 1])
            pos += header_byte + 1

    return result
