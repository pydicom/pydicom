# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the numpy package to convert RLE lossless pixel data to an ndarray.

**Supported transfer syntaxes**

* 1.2.840.10008.1.2.5 : RLE Lossless

**Supported data**

The RLE handler supports the conversion of data in the (7fe0,0010)
*Pixel Data* element to a numpy ndarray provided the related Image Pixel module
elements have values given in the table below.

+------------------------------------------------+--------------+----------+
| Element                                        | Supported    |          |
+-------------+---------------------------+------+ values       |          |
| Tag         | Keyword                   | Type |              |          |
+=============+===========================+======+==============+==========+
| (0028,0002) | SamplesPerPixel           | 1    | N            | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0006) | PlanarConfiguration       | 1C   | 1            | Optional |
+-------------+---------------------------+------+--------------+----------+
| (0028,0008) | NumberOfFrames            | 1C   | N            | Optional |
+-------------+---------------------------+------+--------------+----------+
| (0028,0010) | Rows                      | 1    | N            | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0011) | Columns                   | 1    | N            | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0100) | BitsAllocated             | 1    | 1, 8, 16, 32 | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0103) | PixelRepresentation       | 1    | 0, 1         | Required |
+-------------+---------------------------+------+--------------+----------+

"""

from struct import unpack

import numpy as np

from pydicom.encaps import decode_data_sequence, defragment_data
from pydicom.pixel_data_handlers.numpy_handler import pixel_dtype
from pydicom.uid import RLELossless


SUPPORTED_TRANSFER_SYNTAXES = [
    RLELossless
]


def supports_transfer_syntax(ds):
    """Return True if the handler supports the transfer syntax used in `ds`."""
    return ds.file_meta.TransferSyntaxUID in SUPPORTED_TRANSFER_SYNTAXES


def needs_to_convert_to_RGB(ds):
    """Return True if the pixel data should to be converted from YCbCr to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return True if the PhotometricInterpretation should be changed to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def get_pixeldata(ds, rle_segment_order='>'):
    """Return an ndarray of the Pixel Data.

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing an Image Pixel module and the Pixel Data
        to be converted.
    rle_segment_order : str
        The order of segments used by the RLE encoder when dealing with Bits
        Allocated > 8. Each segment contains 8-bits of the pixel data, which
        are supposed to be ordered from MSB to LSB. A value of '>' means
        interpret the segments as being in big endian order (default) while a
        value of '<' means interpret the segments as being in little endian
        order.

    Returns
    -------
    np.ndarray
        The contents of the Pixel Data element (7FE0,0010) as a 1D array.

    Raises
    ------
    AttributeError
        If the dataset is missing a required element.
    NotImplementedError
        If the dataset contains pixel data in an unsupported format.
    ValueError
        If the actual length of the pixel data doesn't match the expected
        length.
    """
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if transfer_syntax not in SUPPORTED_TRANSFER_SYNTAXES:
        raise NotImplementedError(
            "Unable to convert the pixel data as the transfer syntax "
            "is not supported by the RLE pixel data handler."
        )

    # Check required elements
    required_elements = ['PixelData', 'BitsAllocated', 'Rows', 'Columns',
                         'PixelRepresentation', 'SamplesPerPixel']
    missing = [elem for elem in required_elements if elem not in ds]
    if missing:
        raise AttributeError(
            "Unable to convert the pixel data as the following required "
            "elements are missing from the dataset: " + ", ".join(missing)
        )

    nr_bits = ds.BitsAllocated
    nr_samples = ds.SamplesPerPixel
    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    rows = ds.Rows
    cols = ds.Columns

    # Decompress each frame of the pixel data
    pixel_data = bytearray()
    if nr_frames > 1:
        for rle_frame in decode_data_sequence(ds.PixelData):
            frame = _rle_decode_frame(rle_frame, rows, cols, nr_samples,
                                      nr_bits)
            pixel_data.extend(frame)
    else:
        frame = _rle_decode_frame(defragment_data(ds.PixelData),
                                  rows, cols, nr_samples, nr_bits)

        pixel_data.extend(frame)

    # At this point `pixel_data` is ordered as (for 16-bit, 3 sample, 2 frame):
    #    Frame 1           | Frame 2
    #    R1 R2 G1 G2 B1 B2 R1 R2 G1 G2 B1 B2
    # Where each of R1, R2, G1, G2, B1, B2 represents a segment and each
    # segment is half of a 2 byte pixel split into 2 8-bit uints as shown below
    #
    #   Segment 1 (R1)       | Segment 2 (R2)     | Segment 3 (G1) ...
    #   Px 1  Px 2  ... Px N | Px 1 Px 2 ... Px N | Px 1 Px 2 ...
    #   MSB   MSB   ... MSB  | LSB  LSB  ... LSB  | MSB  MSB  ...
    # For each 2-byte pixel, R1 is the MSB half and R2 the LSB half
    # We interpret the data as uint8 because its not yet in the right order

    # The segment order should be big endian by default but make it possible
    #   to switch if the RLE is non-conformant
    dtype = pixel_dtype(ds).newbyteorder(rle_segment_order)
    arr = np.frombuffer(pixel_data, dtype)

    # Reshape so the array is ordered as
    #   Segment 1:  [[R MSB values -> ],
    #   Segment 2:   [R LSB values -> ], etc
    #nr_segments = nr_frames * nr_bits // 8 * nr_samples

    #arr = arr.reshape((-1, nr_segments), order='F')

    #dtype =
    # Apply new view on the array with the correct final dtype
    #arr = arr.view(dtype)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr


def _parse_rle_header(header):
    """Return a list of byte offsets for the segments in RLE data.

    **RLE Header Format**

    The RLE Header contains the number of segments for the image and the
    starting offset of each segment. Each of these number is represented as
    an unsigned long stored in little-endian. The RLE Header is 16 long words
    in length (i.e. 64 bytes) which allows it to describe a compressed image
    with up to 15 segments. All unused segment offsets shall be set to zero.

    As an example, the table below describes an RLE Header with 3 segments as
    would typically be used with 8-bit RGB or YCbCr data (with 1 segment per
    channel).

    +--------------+---------------------------------+------------+
    | Byte  offset | Description                     | Value      |
    +==============+=================================+============+
    | 0            | Number of segments              | 3          |
    +--------------+---------------------------------+------------+
    | 4            | Offset of segment 1, N bytes    | 64         |
    +--------------+---------------------------------+------------+
    | 8            | Offset of segment 2, M bytes    | 64 + N     |
    +--------------+---------------------------------+------------+
    | 12           | Offset of segment 3             | 64 + N + M |
    +--------------+---------------------------------+------------+
    | 16           | Offset of segment 4 (not used)  | 0          |
    +--------------+---------------------------------+------------+
    | ...          | ...                             | 0          |
    +--------------+---------------------------------+------------+
    | 60           | Offset of segment 15 (not used) | 0          |
    +--------------+---------------------------------+------------+

    Parameters
    ----------
    header : bytes
        The RLE header data (i.e. the first 64 bytes of an RLE frame).

    Returns
    -------
    list of int
        The byte offsets for each segment in the RLE data.

    Raises
    ------
    ValueError
        If there are more than 15 segments or if the header is not 64 bytes
        long.

    References
    ----------
    DICOM Standard, Part 5, Annex G
    """
    if len(header) != 64:
        raise ValueError('The RLE header can only be 64 bytes long')

    # The number of segments
    nr_segments = unpack('<L', header[:4])[0]
    if nr_segments > 15:
        raise ValueError(
            "The RLE header specifies an invalid number of segments ({})"
            .format(nr_segments)
        )

    offsets = unpack('<{}L'.format(nr_segments),
                     header[4:4 * (nr_segments + 1)])

    return list(offsets)


def _rle_decode_frame(data, rows, columns, nr_samples, nr_bits):
    """Decodes a single frame of RLE encoded data.

    Each frame may contain up to 15 segments of encoded data.

    Parameters
    ----------
    data : bytes
        The RLE frame data
    rows : int
        The number of output rows
    columns : int
        The number of output columns
    nr_samples : int
        Number of samples per pixel (e.g. 3 for RGB data).
    nr_bits : int
        Number of bits per sample - must be a multiple of 8

    Returns
    -------
    bytearray
        The frame's decoded data in big endian and planar configuration 1
        byte ordering (i.e. for RGB data this is all red pixels then all
        green then all blue, with the bytes for each pixel ordered from
        MSB to LSB when reading left to right).
    """
    # XXX: FIXME
    if nr_bits % 8:
        raise NotImplementedError(
            "Don't know how to handle BitsAllocated not being a multiple of bytes"
        )

    # Parse the RLE Header
    offsets = _parse_rle_header(data[:64])
    nr_segments = len(offsets)

    # Check that the actual number of segments is as expected
    bytes_per_sample = nr_bits // 8
    if nr_segments != nr_samples * bytes_per_sample:
        raise ValueError(
            "The number of RLE segments in the pixel data doesn't match the "
            "expected amount ({} vs. {} segments)"
            .format(nr_segments, nr_samples * bytes_per_sample)
        )

    # Ensure the last segment gets decoded
    offsets.append(len(data))

    # Decode
    decoded = bytearray(rows * columns * nr_samples * bytes_per_sample)

    # Interleave the segments now to make things faster later

    # For 16 bit, 3 sample data we want Planar Configuration 1 ordering
    # which is all red pixels, then all green, then all blue
    #    Red                         | Green                       | Blue
    #    Pxl 1   Pxl 2   ... Pxl N   | Pxl 1   Pxl 2   ... Pxl N   | ...
    #    MSB LSB MSB LSB ... MSB LSB | MSB LSB MSB LSB ... MSB LSB | ...

    # `stride` is the total number of bytes of each sample plane
    stride = bytes_per_sample * rows * columns
    for sample_number in range(nr_samples):
        for byte_offset in range(bytes_per_sample):
            # Decode the segment
            # ii is 0, 1, 2, 3, ... nr_segments
            ii = sample_number * bytes_per_sample + byte_offset
            segment = _rle_decode_segment(data[offsets[ii]:offsets[ii + 1]])
            # Check that the number of decoded pixels is correct
            if len(segment) != rows * columns:
                raise AttributeError(
                    "The amount of decoded RLE segment data doesn't match the "
                    "expected amount ({} vs {} bytes)"
                    .format(len(segment), rows * columns)
                )

            # `start` is where the segment should be inserted
            # For 100 pixel, 16-bit, 3 sample data this is
            # 0, 1, 200, 201, 400, 401
            start = byte_offset + sample_number * stride
            decoded[start:start + stride:bytes_per_sample] = segment

    return decoded


def _rle_decode_segment(data):
    """Return a single segment of decoded RLE data as bytearray.

    Parameters
    ----------
    data : bytes
        The segment data to be decoded.

    Returns
    -------
    bytearray
        The decoded segment.
    """

    data = bytearray(data)
    result = bytearray()
    pos = 0
    result_extend = result.extend

    try:
        while True:
            # header_byte is N + 1
            header_byte = data[pos] + 1
            pos += 1
            if header_byte > 129:
                # Extend by copying the next byte (-N + 1) times
                # however since using uint8 instead of int8 this will be
                # (256 - N + 1) times
                result_extend(data[pos:pos + 1] * (258 - header_byte))
                pos += 1
            elif header_byte < 129:
                # Extend by literally copying the next (N + 1) bytes
                result_extend(data[pos:pos + header_byte])
                pos += header_byte

    except IndexError:
        pass

    return result
