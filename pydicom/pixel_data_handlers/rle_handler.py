# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `numpy <https://numpy.org/>`_ package to convert RLE lossless *Pixel
Data* to a :class:`numpy.ndarray`.

**Supported transfer syntaxes**

* 1.2.840.10008.1.2.5 : RLE Lossless

**Supported data**

The RLE handler supports the conversion of data in the (7FE0,0010)
*Pixel Data* element to a numpy ndarray provided the related
:dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements have values given
in the table below.

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
| (0028,0100) | BitsAllocated             | 1    | 8, 16, 32    | Required |
+-------------+---------------------------+------+--------------+----------+
| (0028,0103) | PixelRepresentation       | 1    | 0, 1         | Required |
+-------------+---------------------------+------+--------------+----------+

"""

from itertools import groupby
from struct import pack, unpack
import sys

try:
    import numpy as np
    HAVE_RLE = True
except ImportError:
    HAVE_RLE = False

from pydicom.encaps import decode_data_sequence, defragment_data
from pydicom.pixel_data_handlers.util import pixel_dtype
import pydicom.uid


HANDLER_NAME = 'RLE Lossless'

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
}

SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.RLELossless
]


def is_available():
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_RLE


def supports_transfer_syntax(transfer_syntax):
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


def needs_to_convert_to_RGB(ds):
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def get_pixeldata(ds, rle_segment_order='>'):
    """Return an :class:`numpy.ndarray` of the *Pixel Data*.

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`Dataset` containing an Image Pixel module and the RLE
        encoded *Pixel Data* to be converted.
    rle_segment_order : str
        The order of segments used by the RLE decoder when dealing with *Bits
        Allocated* > 8. Each RLE segment contains 8-bits of the pixel data,
        and segments are supposed to be ordered from MSB to LSB. A value of
        ``'>'`` means interpret the segments as being in big endian order
        (default) while a value of ``'<'`` means interpret the segments as
        being in little endian order which may be possible if the encoded data
        is non-conformant.

    Returns
    -------
    numpy.ndarray
        The decoded contents of (7FE0,0010) *Pixel Data* as a 1D array.

    Raises
    ------
    AttributeError
        If `ds` is missing a required element.
    NotImplementedError
        If `ds` contains pixel data in an unsupported format.
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

    # The segment order should be big endian by default but make it possible
    #   to switch if the RLE is non-conformant
    dtype = pixel_dtype(ds).newbyteorder(rle_segment_order)
    arr = np.frombuffer(pixel_data, dtype)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return arr


# RLE decoding functions
def _parse_rle_header(header):
    """Return a list of byte offsets for the segments in RLE data.

    **RLE Header Format**

    The RLE Header contains the number of segments for the image and the
    starting offset of each segment. Each of these numbers is represented as
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
    DICOM Standard, Part 5, :dcm:`Annex G<part05/chapter_G.html>`
    """
    if len(header) != 64:
        raise ValueError('The RLE header can only be 64 bytes long')

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
    if nr_bits % 8:
        raise NotImplementedError(
            "Unable to decode RLE encoded pixel data with a (0028,0100) "
            "'Bits Allocated' value of {}".format(nr_bits)
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

    # Preallocate with null bytes
    decoded = bytearray(rows * columns * nr_samples * bytes_per_sample)

    # Example:
    # RLE encoded data is ordered like this (for 16-bit, 3 sample):
    #  Segment: 1     | 2     | 3     | 4     | 5     | 6
    #           R MSB | R LSB | G MSB | G LSB | B MSB | B LSB
    #  A segment contains only the MSB or LSB parts of all the sample pixels

    # To minimise the amount of array manipulation later, and to make things
    # faster we interleave each segment in a manner consistent with a planar
    # configuration of 1 (and maintain big endian byte ordering):
    #    All red samples             | All green samples           | All blue
    #    Pxl 1   Pxl 2   ... Pxl N   | Pxl 1   Pxl 2   ... Pxl N   | ...
    #    MSB LSB MSB LSB ... MSB LSB | MSB LSB MSB LSB ... MSB LSB | ...

    # `stride` is the total number of bytes of each sample plane
    stride = bytes_per_sample * rows * columns
    for sample_number in range(nr_samples):
        for byte_offset in range(bytes_per_sample):
            # Decode the segment
            # ii is 0, 1, 2, 3, ..., (nr_segments - 1)
            ii = sample_number * bytes_per_sample + byte_offset
            segment = _rle_decode_segment(data[offsets[ii]:offsets[ii + 1]])
            # Check that the number of decoded pixels is correct
            if len(segment) != rows * columns:
                raise ValueError(
                    "The amount of decoded RLE segment data doesn't match the "
                    "expected amount ({} vs. {} bytes)"
                    .format(len(segment), rows * columns)
                )

            # For 100 pixel/plane, 32-bit, 3 sample data `start` will be
            #   0, 1, 2, 3, 400, 401, 402, 403, 800, 801, 802, 803
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


# RLE encoding functions
def rle_encode_frame(arr):
    """Return an :class:`numpy.ndarray` image frame as RLE encoded
    :class:`bytearray`.

    .. versionadded:: 1.3

    Parameters
    ----------
    arr : numpy.ndarray
        A 2D (if *Samples Per Pixel* = 1) or 3D (if *Samples Per Pixel* = 3)
        ndarray containing a single frame of the image to be RLE encoded.

    Returns
    -------
    bytearray
        An RLE encoded frame, including the RLE header, following the format
        specified by the DICOM Standard, Part 5,
        :dcm:`Annex G<part05/chapter_G.html>`.
    """
    shape = arr.shape
    if len(shape) > 3:
        # Note: only raises if multi-sample pixel data with multiple frames
        raise ValueError(
            "Unable to encode multiple frames at once, please encode one "
            "frame at a time"
        )

    # Check the expected number of segments
    nr_segments = arr.dtype.itemsize
    if len(shape) == 3:
        # Number of samples * bytes per sample
        nr_segments *= shape[-1]

    if nr_segments > 15:
        raise ValueError(
            "Unable to encode as the DICOM standard only allows "
            "a maximum of 15 segments in RLE encoded data"
        )

    rle_data = bytearray()
    seg_lengths = []
    if len(shape) == 3:
        # Samples Per Pixel > 1
        for ii in range(arr.shape[-1]):
            # Need a contiguous array in order to be able to split it up
            # into byte segments
            for segment in _rle_encode_plane(arr[..., ii].copy()):
                rle_data.extend(segment)
                seg_lengths.append(len(segment))
    else:
        # Samples Per Pixel = 1
        for segment in _rle_encode_plane(arr):
            rle_data.extend(segment)
            seg_lengths.append(len(segment))

    # Add the number of segments to the header
    rle_header = bytearray(pack('<L', len(seg_lengths)))

    # Add the segment offsets, starting at 64 for the first segment
    # We don't need an offset to any data at the end of the last segment
    offsets = [64]
    for ii, length in enumerate(seg_lengths[:-1]):
        offsets.append(offsets[ii] + length)
    rle_header.extend(pack('<{}L'.format(len(offsets)), *offsets))

    # Add trailing padding to make up the rest of the header (if required)
    rle_header.extend(b'\x00' * (64 - len(rle_header)))

    return rle_header + rle_data


def _rle_encode_plane(arr):
    """Yield RLE encoded segments from an image plane as bytearray.

    A plane of N-byte samples must be split into N segments, with each segment
    containing the same byte of the N-byte samples. For example, in a plane
    containing 16 bits per sample, the first segment will contain the most
    significant 8 bits of the samples and the second segment the 8 least
    significant bits. Each segment is RLE encoded prior to being yielded.

    Parameters
    ----------
    arr : numpy.ndarray
        A 2D ndarray containing a single plane of the image data to be RLE
        encoded. The dtype of the array should be a multiple of 8 (i.e. uint8,
        uint32, int16, etc.).

    Yields
    ------
    bytearray
        An RLE encoded segment of the plane, following the format specified
        by the DICOM Standard, Part 5, :dcm:`Annex G<part05/chapter_G.html>`.
        The segments are yielded in order from most significant to least.
    """
    # Determine the byte order of the array
    byte_order = arr.dtype.byteorder
    if byte_order == '=':
        byte_order = '<' if sys.byteorder == 'little' else '>'

    # Re-view the N-bit array data as N / 8 x uint8s
    arr8 = arr.view(np.uint8)

    # Reshape the uint8 array data into 1 or more segments and encode
    bytes_per_sample = arr.dtype.itemsize
    for ii in range(bytes_per_sample):
        # If the original byte order is little endian we need to segment
        #   in reverse order
        if byte_order == '<':
            ii = bytes_per_sample - ii - 1
        segment = arr8.ravel()[ii::bytes_per_sample].reshape(arr.shape)

        yield _rle_encode_segment(segment)


def _rle_encode_segment(arr):
    """Return a 2D numpy ndarray as an RLE encoded bytearray.

    Each row of the image is encoded separately as required by the DICOM
    Standard.

    Parameters
    ----------
    arr : numpy.ndarray
        A 2D ndarray of 8-bit uint data, representing a Byte Segment as in
        the DICOM Standard, Part 5, :dcm:`Annex G.2<part05/sect_G.2.html>`.

    Returns
    -------
    bytearray
        The RLE encoded segment, following the format specified by the DICOM
        Standard. Odd length encoded segments are padded by a trailing ``0x00``
        to be even length.
    """
    out = bytearray()
    if len(arr.shape) > 1:
        for row in arr:
            out.extend(_rle_encode_row(row))
    else:
        out.extend(_rle_encode_row(arr))

    # Pad odd length data with a trailing 0x00 byte
    out.extend(b'\x00' * (len(out) % 2))

    return out


def _rle_encode_row(arr):
    """Return a numpy array as an RLE encoded bytearray.

    Parameters
    ----------
    arr : numpy.ndarray
        A 1D ndarray of 8-bit uint data.

    Returns
    -------
    bytes
        The RLE encoded row, following the format specified by the DICOM
        Standard, Part 5, :dcm:`Annex G<part05/chapter_G.html>`

    Notes
    -----
    * 2-byte repeat runs are always encoded as Replicate Runs rather than
      only when not preceeded by a Literal Run as suggested by the Standard.
    """
    out = []
    out_append = out.append
    out_extend = out.extend

    literal = []
    for key, group in groupby(arr.astype('uint8').tolist()):
        group = list(group)
        if len(group) == 1:
            literal.append(group[0])
        else:
            if literal:
                # Literal runs
                for ii in range(0, len(literal), 128):
                    _run = literal[ii:ii + 128]
                    out_append(len(_run) - 1)
                    out_extend(_run)

                literal = []

            # Replicate run
            for ii in range(0, len(group), 128):
                if len(group[ii:ii + 128]) > 1:
                    # Replicate run
                    out_append(257 - len(group[ii:ii + 128]))
                    out_append(group[0])
                else:
                    # Literal run only if last replicate part is length 1
                    out_append(0)
                    out_append(group[0])

    # Final literal run if literal isn't followed by a replicate run
    for ii in range(0, len(literal), 128):
        _run = literal[ii:ii + 128]
        out_append(len(_run) - 1)
        out_extend(_run)

    return pack('{}B'.format(len(out)), *out)
