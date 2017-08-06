import sys
import pydicom.uid
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
    return (dicom_dataset.file_meta.TransferSyntaxUID in RLESupportedTransferSyntaxes)


def get_pixeldata(dicom_dataset):
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

    print("Decoding RLE")
    UncompressedPixelData = bytearray()

    if ('NumberOfFrames' in dicom_dataset and
            dicom_dataset.NumberOfFrames > 1):

        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(
            dicom_dataset.PixelData)

        for frame in CompressedPixelDataSeq:
            decompressed_frame = rle_decode_frame(frame,
                                                  Rows=dicom_dataset.Rows,
                                                  Columns=dicom_dataset.Columns,
                                                  SamplesPerPixel=dicom_dataset.SamplesPerPixel,
                                                  numpy_format=numpy_format)

            UncompressedPixelData.extend(decompressed_frame)

    else:

        CompressedPixelData = pydicom.encaps.defragment_data(
            dicom_dataset.PixelData)

        decompressed_frame = rle_decode_frame(CompressedPixelData,
                                              Rows=dicom_dataset.Rows,
                                              Columns=dicom_dataset.Columns,
                                              SamplesPerPixel=dicom_dataset.SamplesPerPixel,
                                              numpy_format=numpy_format)

        UncompressedPixelData.extend(decompressed_frame)

    pixel_array = numpy.frombuffer(UncompressedPixelData, numpy_format)

    return pixel_array


def rle_decode_frame(d, Rows, Columns, SamplesPerPixel, numpy_format):
    rle_start = 0
    rle_len = len(d)

    number_of_planes = unpack(b'<L', d[rle_start: rle_start + 4])[0]

    SampleSize = numpy_format.itemsize

    expected_number_of_planes = SamplesPerPixel * SampleSize

    if number_of_planes != expected_number_of_planes:
        raise Exception("Unexpected number of planes")

    plane_start_list = []
    for i in range(number_of_planes):
        plane_start_in_rle = unpack(b'<L', d[rle_start + 4 + (4 * i):rle_start + 4 + (4 * (i + 1))])[0]
        plane_start_list.append(plane_start_in_rle + rle_start)

    plane_end_list = plane_start_list[1:]
    plane_end_list.append(rle_len + rle_start)

    frame_bytes = bytearray(Rows * Columns * SamplesPerPixel * SampleSize)

    for plane_number in range(number_of_planes):
        plane_start = plane_start_list[plane_number]
        plane_end = plane_end_list[plane_number]

        plane_bytes = rle_decode_plane(d[plane_start:plane_end])

        if len(plane_bytes) != Rows * Columns:
            raise Exception("Error unpacking bytes from RLE")

        frame_bytes[plane_number::SamplesPerPixel*SampleSize] = plane_bytes

    return frame_bytes


def rle_decode_plane(data):

    data = bytearray(data)
    result = bytearray()
    pos = 0
    len_data = len(data)

    while pos < len_data:
        header_byte = data[pos]

        pos += 1

        if header_byte > 128:
            result.extend([data[pos]] * (255 - header_byte + 2))
            pos += 1
            continue

        if header_byte <= 127:
            result.extend(data[pos:pos+header_byte+1])
            pos += header_byte+1
            continue

    return result
