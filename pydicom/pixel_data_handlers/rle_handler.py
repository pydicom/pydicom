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


def get_pixeldata(ds):
    """Return an ndarray of the Pixel Data.

    Parameters
    ----------
    ds : dataset.Dataset
        The DICOM dataset containing an Image Pixel module and the Pixel Data
        to be converted.

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

    # Use a byte array to store the decompressed pixel data
    pixel_data = bytearray()

    # Decompress each frame of the pixel data
    if getattr(ds, 'NumberOfFrames', 1) > 1:
        for rle_frame in decode_data_sequence(ds.PixelData):
            frame = _rle_decode_frame(rle_frame,
                                      rows=ds.Rows,
                                      columns=ds.Columns,
                                      nr_samples=ds.SamplesPerPixel,
                                      bits_alloc=ds.BitsAllocated)
            pixel_data.extend(frame)
    else:
        frame = _rle_decode_frame(defragment_data(ds.PixelData),
                                  rows=ds.Rows,
                                  columns=ds.Columns,
                                  nr_samples=ds.SamplesPerPixel,
                                  bits_alloc=ds.BitsAllocated)

        pixel_data.extend(frame)

    # As pixel_data is mutable the numpy ndarray will be writable
    arr = np.frombuffer(pixel_data, dtype=pixel_dtype(ds))

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr


def _dev_rle_decode_frame(frame, rows, cols, nr_samples, bits_alloc):
    """Return the decoded bytes from a single RLE encoded `frame`.

    An RLE compressed frame is stored as a Header, then RLE Segment 1, RLE
    Segment 2, ..., RLE Segment N.

    As an example, the table below describes the overall structure of an RLE
    encoded frame with 3 Segments.

    +--------------+--------+----------------+
    | Byte offset  | Length | Description    |
    +==============+========+================+
    | 0            | 64     | RLE Header     |
    +--------------+--------+----------------+
    | 64           | N      | Segment 1 data |
    +--------------+--------+----------------+
    | 64 + N       | M      | Segment 2 data |
    +--------------+--------+----------------+
    | 64 + N + M   | P      | Segment 3 data |
    +--------------+--------+----------------+

    **Segmentation of pixel data**

    BitsAllocated 8, SamplesPerPixel 1
    +---------+------------------+
    | Segment | 0                |
    +---------+------------------+
    | bit     | 0 to 7           |
    +---------+------------------+
    | Channel | Greyscale        |
    +---------+------------------+

    BitsAllocated 16, SamplesPerPixel 1
    +---------+--------+---------+
    | Segment | 0      | 1       |
    +---------+--------+---------+
    | bit     | 0 to 7 | 8 to 15 |
    +---------+------------------+
    | Channel | Greyscale        |
    +---------+------------------+

    BitsAllocated 8, SamplesPerPixel 3
    +---------+---------+--------+--------+
    | Segment | 0       | 1      | 2      |
    +---------+---------+--------+--------+
    | n-bit   | 0 to 8  | 0 to 8 | 0 to 8 |
    +---------+---------+--------+--------+
    | Channel | Red     | Green  | Blue   |
    +---------+---------+--------+--------+

    BitsAllocated 16, SamplesPerPixel 3
    +---------+-----+------+-------+-------+-------+-------+
    | Segment | 0   | 1    | 2     | 3     | 4     | 5     |
    +---------+-----+------+-------+-------+-------+-------+
    | k-bit   | 0-7 | 8-15 | 16-23 | 24-31 | 32-39 | 40-47 |
    +---------+-----+------+-------+-------+-------+-------+
    | Channel | Red        | Green         | Blue          |
    +---------+------------+---------------+---------------+

    Parameters
    ----------
    frame : bytes
        The RLE encoded frame data.
    rows : int
        The number of output rows.
    cols : int
        The number of output columns.
    nr_samples : int
        Number of samples per pixel (e.g. 3 for RGB data).
    bits_alloc : int
        Number of bits per sample - must be a multiple of 8.

    Returns
    -------
    bytearray
        The decoded data.

    References
    ----------
    DICOM Standard, Part 5, Annex G
    DICOM Standard, Part 3, C.7.6.3.1.1
    """
    # XXX: FIXME
    if bits_alloc > 0 and bits_alloc % 8:
        raise NotImplementedError(
            "Don't know how to handle BitsAllocated not being a multiple of bytes"
        )

    # If BitsAllocated is 16 then bytes_allocated is 2; 2 bytes per pixel
    bytes_allocated = bits_alloc // 8

    # Parse the RLE Header
    offsets = _parse_rle_header(frame[:64])

    # Check that the actual number of segments is as expected
    if len(offsets) != nr_samples * bytes_allocated:
        raise ValueError(
            "The number of RLE segments in the pixel data doesn't match the "
            "expected amount ({0} vs. {1} segments). The dataset may be "
            "corrupted or there may be an issue with the pixel data handler."
            .format(nr_samples * bytes_allocated, len(offsets))
        )

    # Add the total length of the frame to ensure the last segment gets decoded
    offsets.append(len(frame))

    # Parse and decode the RLE segments

    # Preallocate so can index later
    #frame_bytes = bytearray(rows * cols * nr_samples * bytes_allocated)

    frame_bytes = bytearray()
    for ii, offset in enumerate(offsets[:-1]):
        #segment_data = frame[offset:offsets[ii + 1]]
        #print(len(segment_data))
        frame_bytes.extend(_rle_decode_segment(frame[offset:offsets[ii + 1]]))

    #print(len(frame_bytes))
    return frame_bytes



    # Annex G.2
    # A Byte Segment is a series of bytes generated by decomposing the
    #   Composite Pixel Code (PS3.3 C.7.6.3.1.1).
    # If the Composite Pixel Code is not an integral number of bytes in size
    #   sufficient Most Significant zero bits are added to make it so. This
    #   is known as the Padded Composite Pixel Code (PC2).
    # The first Segment is generated by stripping off the most significant byte
    #   of each PC2 and ordering these bytes
    #   sequentially. The second Segment is generated by repeating this process
    #   on the stripped PC2 continuing until the last
    #   Pixel Segment is generated by ordering the least significant byte of
    #   each PC2 sequentially.
    #
    # If PhotometricInterpretation is RGB and BitsStored is 8 then three
    #   Segments are generated, the first holds all the Red values, the second
    #   all the Green values and the third all the Blue values.

    # Little endian
    # LSB 0D 0C 0B 0A MSB
    # Big endian
    # MSB 0A 0B 0C 0D LSB

    # Composite Pixel Code
    #   If SamplesPerPixel == 1, CPC is just the 'n' bit pixel sample, where
    #   'n' = BitsAllocated. If SamplesPerPixel > 1, CPC is a 'k' bit
    #   concatenation of samples, where 'k' = BitsAllocated * SamplesPerPixel
    #   and with the sample representing the vector colour designated first in
    #   the PhotometricInterpretation name comprising the most significant bits
    #   of the CPC.
    # For example, with RGB, the most significant BitsAllocated bits contain
    #   the Red sample, the next BitsAllocated bits contain the Green and the
    #   least significant BitsAllocated bits contain the Blue sample.

    '''
    for segment_nr in range(len(offsets)):
        # sample_number, 0, ...
        for byte_number in range(bytes_allocated):
            # byte_number, 0, 1, ...
            #
            # plane_number 0, 1; 2, 3; 4, 5;
            # plane_number 0, 1; 0, 1; 0, 5;
            plane_number = byte_number + (segment_nr * bytes_allocated)
            # 1, 0; 3, 2; 5, 4; little endian?
            # 1, 0;
            output_nr = (segment_nr + 1) * bytes_allocated - byte_number - 1

            # Decode the segment
            print(plane_number)
            plane_bytes = _rle_decode_segment(
                frame[offset[plane_number]:offset[plane_number + 1]]
            )

            # Check the length is correct
            # TODO: Update exception message
            if len(plane_bytes) != rows * cols:
                raise ValueError(
                    "Different number of bytes unpacked from RLE than expected"
                )

            # Write the plane data back to frame_bytes
            frame_bytes[output_nr::nr_samples * bytes_allocated] = plane_bytes

    return frame_bytes
    '''


def _parse_rle_header(header):
    """Return a list of byte offsets for the segments in RLE data.

    **RLE Header Format**

    The RLE Header contains the number of segments for the image and the
    starting offset of each segment. Each of these number is represented as
    an unsigned long stored in little-endian. The RLE Header is 16 long words
    in length (i.e. 64 bytes) which allows it to describe a compressed image
    with up to 15 segments. All unused segment offsets shall be set to zero.

    As an example, the table below describes an RLE Header with 3 segments as
    would typically be used with RGB or YCbCr data (with 1 Segment per
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
            "The RLE header specifies an invalid number of segments"
        )

    offsets = unpack('<{}L'.format(nr_segments),
                     header[4:4 * (nr_segments + 1)])

    return list(offsets)


def _rle_decode_frame(data, rows, columns, nr_samples, bits_alloc):
    """Decodes a single frame of RLE encoded data.

    Reads the plane information at the beginning of the data.
    If more than pixel size > 1 byte appropriately interleaves the data from
    the high and low planes. Data is always stored big endian. Output always
    little endian

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
    bits_alloc : int
        Number of bits per sample - must be a multiple of 8

    Returns
    -------
    bytearray
        The decompressed data
    """
    # XXX: FIXME
    if bits_alloc > 0 and bits_alloc % 8:
        raise NotImplementedError(
            "Don't know how to handle BitsAllocated not being a multiple of bytes"
        )

    # If BitsAllocated is 16 then bytes_allocated is 2; 2 bytes per pixel
    bytes_allocated = bits_alloc // 8

    # Parse the RLE Header
    offsets = _parse_rle_header(data[:64])

    # Check that the actual number of segments is as expected
    if len(offsets) != nr_samples * bytes_allocated:
        raise ValueError(
            "The number of RLE segments in the pixel data doesn't match the "
            "expected amount ({0} vs. {1} segments)"
            .format(len(offsets), nr_samples * bytes_allocated)
        )

    # Add the total length of the frame to ensure the last segment gets decoded
    offsets.append(len(data))

    frame_bytes = bytearray(rows * columns * nr_samples * bytes_allocated)  # noqa

    for sample_number in range(nr_samples):
        for byte_number in range(bytes_allocated):

            plane_number = byte_number + (sample_number * bytes_allocated)
            out_plane_number = ((sample_number + 1) * bytes_allocated) - byte_number - 1  # noqa

            plane_bytes = _rle_decode_segment(
                data[offsets[plane_number]:offsets[plane_number + 1]]
            )

            if len(plane_bytes) != rows * columns:
                raise AttributeError("Different number of bytes unpacked "
                                     "from RLE than expected")

            frame_bytes[out_plane_number::nr_samples * bytes_allocated] = plane_bytes  # noqa

    return frame_bytes


def _rle_decode_segment(data):
    """Return a single segment of decoded RLE data.

    Parameters
    ----------
    data : bytes
        The segment data to be decompressed.

    Returns
    -------
    bytearray
        The decompressed segment.
    """

    data = bytearray(data)
    result = bytearray()
    pos = 0
    result_extend = result.extend

    try:
        while True:
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
