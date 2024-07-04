# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use Python to decode RLE Lossless encoded *Pixel Data*.

This module is not intended to be used directly.
"""

from struct import unpack

from pydicom.misc import warn_and_log
from pydicom.pixels.decoders.base import DecodeRunner
from pydicom.uid import RLELossless


DECODER_DEPENDENCIES = {RLELossless: ()}


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    return uid in DECODER_DEPENDENCIES


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytearray:
    """Wrapper for use with the decoder interface.

    Parameters
    ----------
    src : bytes
        A single frame of RLE encoded data.
    runner : pydicom.pixels.decoders.base.DecodeRunner


        Required parameters:

        * `rows`: int
        * `columns`: int
        * `samples_per_pixel`: int
        * `bits_allocated`: int

        Optional parameters:

        * `rle_segment_order`: str, "<" for little endian segment order, or
          ">" for big endian (default)

    Returns
    -------
    bytearray
        The decoded frame, ordered as planar configuration 1.
    """
    frame = _rle_decode_frame(
        src,
        runner.rows,
        runner.columns,
        runner.samples_per_pixel,
        runner.bits_allocated,
        runner.get_option("rle_segment_order", ">"),
    )
    # Update the runner options to ensure the reshaping is correct
    # Only do this if we successfully decoded the frame
    runner.set_option("planar_configuration", 1)

    return frame


def _rle_decode_frame(
    src: bytes,
    rows: int,
    columns: int,
    nr_samples: int,
    nr_bits: int,
    segment_order: str = ">",
) -> bytearray:
    """Decodes a single frame of RLE encoded data.

    Each frame may contain up to 15 segments of encoded data.

    Parameters
    ----------
    src : bytes
        The RLE frame data
    rows : int
        The number of output rows
    columns : int
        The number of output columns
    nr_samples : int
        Number of samples per pixel (e.g. 3 for RGB data).
    nr_bits : int
        Number of bits per sample - must be a multiple of 8
    segment_order : str
        The segment order of the `data`, '>' for big endian (default),
        '<' for little endian (non-conformant).

    Returns
    -------
    bytearray
        The frame's decoded data in little endian and planar configuration 1
        byte ordering (i.e. for RGB data this is all red pixels then all
        green then all blue, with the bytes for each pixel ordered from
        MSB to LSB when reading left to right).
    """
    if nr_bits % 8:
        raise NotImplementedError(
            f"Unable to decode RLE encoded pixel data with {nr_bits} bits allocated"
        )

    # Parse the RLE Header
    offsets = _rle_parse_header(src[:64])
    nr_segments = len(offsets)

    # Check that the actual number of segments is as expected
    bytes_per_sample = nr_bits // 8
    if nr_segments != nr_samples * bytes_per_sample:
        raise ValueError(
            "The number of RLE segments in the pixel data doesn't match the "
            f"expected amount ({nr_segments} vs. {nr_samples * bytes_per_sample} "
            "segments)"
        )

    # Ensure the last segment gets decoded
    offsets.append(len(src))

    # Preallocate with null bytes
    decoded = bytearray(rows * columns * nr_samples * bytes_per_sample)

    # Example:
    # RLE encoded data is ordered like this (for 16-bit, 3 sample):
    #  Segment: 0     | 1     | 2     | 3     | 4     | 5
    #           R MSB | R LSB | G MSB | G LSB | B MSB | B LSB
    #  A segment contains only the MSB or LSB parts of all the sample pixels

    # To minimise the amount of array manipulation later, and to make things
    # faster we interleave each segment in a manner consistent with a planar
    # configuration of 1 (and use little endian byte ordering):
    #    All red samples             | All green samples           | All blue
    #    Pxl 1   Pxl 2   ... Pxl N   | Pxl 1   Pxl 2   ... Pxl N   | ...
    #    LSB MSB LSB MSB ... LSB MSB | LSB MSB LSB MSB ... LSB MSB | ...

    # `stride` is the total number of bytes of each sample plane
    stride = bytes_per_sample * rows * columns
    for sample_number in range(nr_samples):
        le_gen = range(bytes_per_sample)
        byte_offsets = le_gen if segment_order == "<" else reversed(le_gen)
        for byte_offset in byte_offsets:
            # Decode the segment
            ii = sample_number * bytes_per_sample + byte_offset
            # ii is 1, 0, 3, 2, 5, 4 for the example above
            # This is where the segment order correction occurs
            segment = _rle_decode_segment(src[offsets[ii] : offsets[ii + 1]])

            # Check that the number of decoded bytes is correct
            actual_length = len(segment)
            if actual_length < rows * columns:
                raise ValueError(
                    "The amount of decoded RLE segment data doesn't match the "
                    f"expected amount ({actual_length} vs. {rows * columns} bytes)"
                )
            elif actual_length != rows * columns:
                warn_and_log(
                    "The decoded RLE segment contains non-conformant padding "
                    f"- {actual_length} vs. {rows * columns} bytes expected"
                )

            if segment_order == ">":
                byte_offset = bytes_per_sample - byte_offset - 1

            # For 100 pixel/plane, 32-bit, 3 sample data, `start` will be
            #   0, 1, 2, 3, 400, 401, 402, 403, 800, 801, 802, 803
            start = byte_offset + (sample_number * stride)
            decoded[start : start + stride : bytes_per_sample] = segment[
                : rows * columns
            ]

    return decoded


def _rle_decode_segment(src: bytes) -> bytearray:
    """Return a single segment of decoded RLE data as bytearray.

    Parameters
    ----------
    buffer : bytes
        The segment data to be decoded.

    Returns
    -------
    bytearray
        The decoded segment.
    """
    result = bytearray()
    pos = 0
    result_extend = result.extend

    try:
        while True:
            # header_byte is N + 1
            header_byte = src[pos] + 1
            pos += 1
            if header_byte > 129:
                # Extend by copying the next byte (-N + 1) times
                # however since using uint8 instead of int8 this will be
                # (256 - N + 1) times
                result_extend(src[pos : pos + 1] * (258 - header_byte))
                pos += 1
            elif header_byte < 129:
                # Extend by literally copying the next (N + 1) bytes
                result_extend(src[pos : pos + header_byte])
                pos += header_byte

    except IndexError:
        pass

    return result


def _rle_parse_header(header: bytes) -> list[int]:
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
        raise ValueError("The RLE header can only be 64 bytes long")

    nr_segments = unpack("<L", header[:4])[0]
    if nr_segments > 15:
        raise ValueError(
            f"The RLE header specifies an invalid number of segments ({nr_segments})"
        )

    return list(unpack(f"<{nr_segments}L", header[4 : 4 * (nr_segments + 1)]))
