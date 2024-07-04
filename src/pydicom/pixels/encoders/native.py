# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from itertools import groupby
import math
from struct import pack

from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.uid import RLELossless


ENCODER_DEPENDENCIES = {RLELossless: ()}


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    return True


def _encode_frame(src: bytes, runner: EncodeRunner) -> bytes:
    """Wrapper for use with the encoder interface.

    Parameters
    ----------
    src : bytes
        A single frame of little-endian ordered image data to be RLE encoded.
    runner : pydicom.pixels.encoders.base.EncodeRunner
        The runner managing the encoding process.

    Returns
    -------
    bytes
        An RLE encoded frame.
    """
    if runner.get_option("byteorder", "<") == ">":
        raise ValueError("Unsupported option \"byteorder = '>'\"")

    bytes_allocated = math.ceil(runner.bits_allocated / 8)

    nr_segments = bytes_allocated * runner.samples_per_pixel
    if nr_segments > 15:
        raise ValueError(
            "Unable to encode as the DICOM standard only allows "
            "a maximum of 15 segments in RLE encoded data"
        )

    rle_data = bytearray()
    seg_lengths = []

    columns = runner.columns
    for sample_nr in range(runner.samples_per_pixel):
        for byte_offset in reversed(range(bytes_allocated)):
            idx = byte_offset + bytes_allocated * sample_nr
            segment = _encode_segment(src[idx::nr_segments], columns)
            rle_data.extend(segment)
            seg_lengths.append(len(segment))

    # Add the number of segments to the header
    rle_header = bytearray(pack("<L", len(seg_lengths)))

    # Add the segment offsets, starting at 64 for the first segment
    # We don't need an offset to any data at the end of the last segment
    offsets = [64]
    for ii, length in enumerate(seg_lengths[:-1]):
        offsets.append(offsets[ii] + length)
    rle_header.extend(pack(f"<{len(offsets)}L", *offsets))

    # Add trailing padding to make up the rest of the header (if required)
    rle_header.extend(b"\x00" * (64 - len(rle_header)))

    return bytes(rle_header + rle_data)


def _encode_segment(src: bytes, columns: int) -> bytearray:
    """Return `src` as an RLE encoded bytearray.

    Each row of the image is encoded separately as required by the DICOM
    Standard.

    Parameters
    ----------
    src : bytes
        The little-endian ordered data to be encoded, representing a Byte
        Segment as in the DICOM Standard, Part 5,
        :dcm:`Annex G.2<part05/sect_G.2.html>`.
    columns : int
        The number of columns in the image.

    Returns
    -------
    bytearray
        The RLE encoded segment, following the format specified by the DICOM
        Standard. Odd length encoded segments are padded by a trailing ``0x00``
        to be even length.
    """
    out = bytearray()
    for idx in range(0, len(src), columns):
        out.extend(_encode_row(src[idx : idx + columns]))

    # Pad odd length data with a trailing 0x00 byte
    out.extend(b"\x00" * (len(out) % 2))

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
      only when not preceded by a Literal Run as suggested by the Standard.
    """
    out: list[int] = []
    out_append = out.append
    out_extend = out.extend

    literal = []
    for _, iter_group in groupby(src):
        group = list(iter_group)
        if len(group) == 1:
            literal.append(group[0])
        else:
            if literal:
                # Literal runs
                nr_full_runs, len_partial_run = divmod(len(literal), 128)
                for idx in range(nr_full_runs):
                    idx *= 128
                    out_append(127)
                    out_extend(literal[idx : idx + 128])

                if len_partial_run:
                    out_append(len_partial_run - 1)
                    out_extend(literal[-len_partial_run:])

                literal = []

            # Replicate runs
            nr_full_runs, len_partial_run = divmod(len(group), 128)
            if nr_full_runs:
                out_extend((129, group[0]) * nr_full_runs)

            if len_partial_run > 1:
                out_extend((257 - len_partial_run, group[0]))
            elif len_partial_run == 1:
                # Literal run - only if last replicate part is length 1
                out_extend((0, group[0]))

    # Final literal run if literal isn't followed by a replicate run
    for ii in range(0, len(literal), 128):
        _run = literal[ii : ii + 128]
        out_append(len(_run) - 1)
        out_extend(_run)

    return pack(f"{len(out)}B", *out)
