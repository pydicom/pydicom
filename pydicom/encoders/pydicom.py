# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from pydicom.uid import RLELossless

try:
    import numpy
    import numpy as np
    HAVE_RLE = True
except ImportError:
    HAVE_RLE = False


ENCODER_DEPENDENCIES = {RLELossless: ('numpy', )}


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    return HAVE_RLE


# New methods for use with RLELosslessEncoder
def _encode_frame(src: bytes, **kwargs) -> bytes:
    """Wrapper for use with the encoder interface.

    .. versionadded:: 2.2

    Parameters
    ----------
    src : bytes
        A single frame of image data to be RLE encoded.
    **kwargs
        Optional parameters for the encoding function.

    Returns
    -------
    bytes
        An RLE encoded frame.
    """
    samples_per_pixel = kwargs['samples_per_pixel']

    rle_data = bytearray()

    seg_lengths = []
    if samples_per_pixel == 3
        for idx in range(samples_per_pixel):
            # Need a contiguous array in order to be able to split it up
            # into byte segments
            segments = _encode_plane(src[idx::samples_per_pixel], **kwargs)
            for segment in segments:
                rle_data.extend(segment)
                seg_lengths.append(len(segment))
    else:
        # Samples Per Pixel = 1
        for segment in _encode_plane(src, **kwargs):
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


def _encode_plane(src: bytes, **kwargs) -> Generator[bytearray, None, None]:
    """Yield RLE encoded segments from an image plane as bytearray.

    A plane of N-byte samples must be split into N segments, with each segment
    containing the same byte of the N-byte samples. For example, in a plane
    containing 16 bits per sample, the first segment will contain the most
    significant 8 bits of the samples and the second segment the 8 least
    significant bits. Each segment is RLE encoded prior to being yielded.

    Parameters
    ----------
    src : bytes
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
    bytes_per_sample = kwargs['bits_allocated'] // 8
    for offset in range(bytes_per_sample - 1, -1, -1):
        yield _encode_segment(src[offset::bytes_per_sample], **kwargs)


def _encode_segment(src: bytes, **kwargs) -> bytearray:
    """Return `src` as an RLE encoded bytearray.

    Each row of the image is encoded separately as required by the DICOM
    Standard.

    Parameters
    ----------
    src : numpy.ndarray
        The little-endian ordered data to be encoded, representing a Byte
        Segment as in the DICOM Standard, Part 5,
        :dcm:`Annex G.2<part05/sect_G.2.html>`.

    Returns
    -------
    bytearray
        The RLE encoded segment, following the format specified by the DICOM
        Standard. Odd length encoded segments are padded by a trailing ``0x00``
        to be even length.
    """
    row_length = kwargs['columns']

    out = bytearray()
    for idx in range(kwargs['rows']):
        offset = idx * row_length
        out.extend(_encode_row(src[offset:offset + row_length]))

    # Pad odd length data with a trailing 0x00 byte
    out.extend(b'\x00' * (len(out) % 2))

    return out


def _encode_row(src: bytes) -> bytes:
    """Return `src` as RLE encoded bytes.

    Parameters
    ----------
    src : bytes
        The little-endian ordered data to be encoded.

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
    for key, group in groupby(list(src)):
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


# Old function kept for backwards compatibility
def rle_encode_frame(arr: "numpy.ndarray") -> bytearray:
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

    dtype = arr.dtype
    kwargs = {
        'bits_allocated': arr.dtype.itemsize * 8,
        'rows': shape[0],
        'columns': shape[1],
        'samples_per_pixel': 3 if len(arr.shape) == 3 else 1,
    }

    sys_endianness = '<' if sys.byteorder == 'little' else '>'
    byteorder = dtype.byteorder
    byteorder = sys_endianness if byteorder == '=' else byteorder
    if byteorder == '>':
        arr = arr.astype(dtype.newbyteorder('<'))

    return _encode(arr.tobytes(), **kwargs)
