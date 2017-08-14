# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Functions for working with encapsulated (compressed) pixel data."""

# Encapsulated Pixel Data --  3.5-2008 A.4
# Encapsulated Pixel data is in a number of Items
# (start with Item tag (0xFFFE,E000) and ending ultimately
# with SQ delimiter and Item Length field of 0 (no value),
# just like SQ of undefined length,
# but here Item must have explicit length.

# PixelData length is Undefined Length if encapsulated
# First item is an Offset Table. It can have 0 length and no value,
# or it can have a table of US pointers to first byte
# of the Item tag starting each *Frame*, where 0 of pointer
# is at first Item tag following the Offset table
# If a single frame, it may be 0 length/no value,
# or it may have a single pointer (0).

from io import BytesIO
from struct import unpack

import pydicom.config
from pydicom.filebase import DicomBytesIO
from pydicom.tag import (Tag, ItemTag, SequenceDelimiterTag)


def get_frame_offsets(fp):
    """Return a list of the fragment offsets from the Basic Offset Table.

    For single or multi-frame images with only one frame this will return
    an empty list. For multi-frame images with multiple frames this will return
    a list containing the byte offsets to the first fragment of each frame, as
    measured from the end of the Basic Offset Table Item.

    Basic Offset Table
    ~~~~~~~~~~~~~~~~~~
    The Basic Offset Table Item must be present and have a tag (FFEE,E000) and
    a length, however it may or may not have a value.
    
    For single or multi-frame images with only one frame, the Basic Offset
    Table may or may not have a value.

    For multi-frame images with more than one frame, the Basic Offset Table
    should have a value.
    
    When the Basic Offset Table has no value then its length shall be
    0x00000000. When it has a value, then it shall contain concatenated 32-bit
    unsigned integer values that are the byte offsets to the first byte of the
    Item tag of the first fragment in each frame in the Sequence of Items.
    These offsets are measured from the first byte of the first item tag
    following the Basic Offset Table Item.

    All decoders, both for single and multi-frame images should accept both
    an empty Basic Offset Table and one containing offset values.

    Parameters
    ----------
    fp : pydicom.filebase.DicomBytesIO
        The encapsulated pixel data positioned at the start of the Basic Offset
        Table.

    Returns
    -------
    offsets : list of int
        The byte offsets to the first fragment of each frame, as measured from
        the end of the Basic Offset Table item.

    Raises
    ------
    ValueError
        If the Basic Offset Table item's tag is not (FFEE,E000) or if the length
        of the item in bytes is not a multiple of 4.
    """
    # Just in case the user forgot to set it beforehand
    fp.is_little_endian = True

    tag = Tag(fp.read_tag())

    if tag != 0xfffee000:
        raise ValueError("Unexpected tag '{}' when parsing the Basic Table "
                         "Offset item.".format(tag))

    length = fp.read_UL()
    if length % 4:
        raise ValueError("The length of the Basic Offset Table item is not "
                           "a multiple of 4.")

    offsets = []
    for ii in range(length / 4):
        offsets.append(fp.read_UL())

    return offsets


def get_pixel_data_fragments(fp):
    """Return the encapsulated pixel data fragments as a list of bytes.

    For compressed (encapsulated) Transfer Syntaxes, the (7fe0,0010) 'Pixel
    Data' element is encoded in an encapsulated format. 

    (7fe0,0010) Pixel Data
    ----------------------
    Encoding
    ~~~~~~~~
    The encoding of the element shall be explicit VR little endian.

    VR
    ~~
    The Pixel Data shall have a VR of 'OB'.

    Length
    ~~~~~~
    The element's length shall be 0xFFFFFFFF (i.e. undefined).

    Encapsulation
    -------------
    The encoded pixel data stream is fragmented into one or more Items. The
    stream may represent a single or multi-frame image (whether or not one
    fragment per frame is permitted or not is defined per Transfer Syntax).

    Each 'Data Stream Fragment' shall have tag of (fffe,e000), followed by a 4
    byte 'Item Length' field encoding the explicit number of bytes in the Item.
    All Items containing an encoded fragment shall have an even number of bytes
    greater than or equal to 2, with the last fragment being padded if
    necessary.

    The first Item in the 'Sequence of Items' shall be a 'Basic Offset Table',
    however the Basic Offset Table item value is not required to be present.

    The Sequence of Items is terminated by a Sequence Delimiter Item with tag
    (fffe,e0dd) and an Item Length field of value 0x00000000.

    Sample Fragment Data
    ~~~~~~~~~~~~~~~~~~~~
    Item : First Fragment of Frame 1 (4958 bytes item length)
    | Tag     | Length    | Value --->
    fe ff 00 e0 5e 13 00 00 ...

    Item : First Fragment of Frame 2 (4742 bytes item length)
    | Tag     | Length    | Value --->
    fe ff 00 e0 86 12 00 00 ...

    Item: Sequence Delimiter
    | Tag     | Length    |
    fe ff dd e0 00 00 00 00

    Parameters
    ----------
    fp : pydicom.filebase.DicomBytesIO
        The encoded (7fe0,0010) 'Pixel Data' element value, positioned after
        the Basic Offset Table item.

    Returns
    -------
    fragments : list of bytes
        A list containing the pixel data fragments.

    Raises
    ------
    ValueError
        If the data contains an item with an undefined length or an unknown
        tag.

    References
    ----------
    DICOM Standard Part 5, Annex A.4
    """
    # Just in case the user forgot to set it beforehand
    fp.is_little_endian = True

    # We should be positioned at the start of the Item Tag for the first
    # fragment after the Basic Offset Table
    fragments = []
    while True:
        try:
            tag = Tag(fp.read_tag())
        except EOFError:
            break

        if tag == 0xFFFEE000:
            # Item
            length = fp.read_UL()
            if length == 0xFFFFFFFF:
                raise ValueError("Undefined item length at offset {} when "
                                 "parsing the encapsulated pixel data "
                                 "fragments.".format(fp.tell() - 4))
            fragments.append(fp.read(length))
        elif tag == 0xFFFEE0DD:
            # Rewind back to the end of the items
            fp.seek(-4, 1)
            break
        else:
            raise ValueError("Unexpected tag '{0}' at offset {1} when parsing "
                             "the encapsulated pixel data fragment items."
                             .format(tag, fp.tell() - 4))

    return fragments


def get_pixel_data_frames(bytestream):
    """Return the encapsulated pixel data frame(s) as a list of bytearray.

    For the following transfer syntaxes, a fragment may not contain encoded
    data from more than one frame. However data from one frame may span
    multiple fragments.

    1.2.840.10008.1.2.4.50 - JPEG Baseline (Process 1)
    1.2.840.10008.1.2.4.51 - JPEG Baseline (Process 2 and 4)
    1.2.840.10008.1.2.4.57 - JPEG Lossless, Non-Hierarchical (Process 14)
    1.2.840.10008.1.2.4.70 - JPEG Lossless, Non-Hierarchical, First-Order
        Prediction (Process 14 [Selection Value 1])
    1.2.840.10008.1.2.4.80 - JPEG-LS Lossless Image Compression
    1.2.840.10008.1.2.4.81 - JPEG-LS Lossy (Near-Lossless) Image Compression
    1.2.840.10008.1.2.4.90 - JPEG 2000 Image Compression (Lossless Only)
    1.2.840.10008.1.2.4.91 - JPEG 2000 Image Compression
    1.2.840.10008.1.2.4.92 - JPEG 2000 Part 2 Multi-component Image Compression
        (Lossless Only)
    1.2.840.10008.1.2.4.93 - JPEG 2000 Part 2 Multi-component Image Compression

    For the following transfer syntaxes, each frame shall be encoded in one and
    only one fragment.

    1.2.840.10008.1.2.5 - RLE Lossless

    Sample Encapsulated Pixel Data
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Pixel Data
    | Tag     | VR  | Rsvd| Length    |
    e0 7f 10 00 4f 42 00 00 ff ff ff ff

    Item: Basic Offset Table (40 bytes item length)
    | Tag     | Length    | Value (0 and 4966)    |
    fe ff 00 e0 28 00 00 00 00 00 00 00 66 13 00 00

    Item : First Fragment of Frame 1 (4958 bytes item length)
    | Tag     | Length    | Value --->
    fe ff 00 e0 5e 13 00 00 ...

    Item : First Fragment of Frame 2 (4742 bytes item length)
    | Tag     | Length    | Value --->
    fe ff 00 e0 86 12 00 00 ...

    Item: Sequence Delimiter
    | Tag     | Length    |
    fe ff dd e0 00 00 00 00

    Parameters
    ----------
    bytestream : str or bytes
        The value of the (7fe0, 0010) 'Pixel Data' element from an encapsulated
        dataset. The Basic Offset Table item should be present and the
        Sequence Delimiter item may or may not be present.

    Returns
    -------
    list of bytearray
        The frame(s) contained in the encapsulated pixel data.

    References
    ----------
    DICOM Standard Part 5, Annex A
    """
    fp = DicomBytesIO(bytestream)
    fp.is_little_endian = True
    
    # offsets contains the byte offset for the first fragment in each frame
    offsets = parse_basic_offset_table(fp)
    # - N * (8 bytes for item tag and length), where N is fragment number
    # FIXME: This is wrong, only works when 1:1 ratio of fragment to frame
    offsets = [val - ii * 8 for ii, val in enumerate(offsets)]
    fragments = parse_pixel_data_fragments(fp)

    frames = []
    if offsets:
        # We start at the second offset so we'll need to do the final frame
        # once we've iterated through the offsets
        fragment_no = 0
        frame_length = 0
        for frame_offset in offsets[1:]:
            frame = bytearray()
            while frame_length < frame_offset:
                frame.extend(fragments[fragment_no])
                frame_length += len(fragments[fragment_no])
                fragment_no += 1

            frames.append(frame)

        # Final frame
        frames.append(bytearray(b''.join(fragments[fragment_no:])))
    else:
        frames.append(bytearray(b''.join(fragments)))

    return frames


def decode_data_sequence(data):
    """Read encapsulated data and return a list of strings.

    Parameters
    ----------
    data : str
        String of encapsulated data, typically dataset.PixelData

    Returns
    -------
    list of bytes
        All fragments in a list of byte strings
    """
    # Convert data into a memory-mapped file
    with DicomBytesIO(data) as fp:

        # DICOM standard requires this
        fp.is_little_endian = True
        BasicOffsetTable = read_item(fp)  # NOQA
        seq = []

        while True:
            item = read_item(fp)

            # None is returned if get to Sequence Delimiter
            if not item:
                break
            seq.append(item)

        # XXX should
        return seq


def defragment_data(data):
    """Read encapsulated data and return the fragments as one continuous string.

    Parameters
    ----------
    data : list of bytes
        The encapsulated pixel data fragments.

    Returns
    -------
    bytes
        All fragments concatenated together.
    """
    return b"".join(decode_data_sequence(data))


# read_item modeled after filereader.ReadSequenceItem
def read_item(fp):
    """Read and return a single Item in the fragmented data stream.

    Parameters
    ----------
    fp : pydicom.filebase.DicomIO
        The file-like to read the item from.

    Returns
    -------
    bytes
        The Item's raw bytes (value?).
    """

    logger = pydicom.config.logger
    try:
        tag = fp.read_tag()

    # already read delimiter before passing data here
    # so should just run out
    except EOFError:
        return None

    # No more items, time for sequence to stop reading
    if tag == SequenceDelimiterTag:
        length = fp.read_UL()
        logger.debug(
            "%04x: Sequence Delimiter, length 0x%x",
            fp.tell() - 8,
            length)

        if length != 0:
            logger.warning(
                "Expected 0x00000000 after delimiter, found 0x%x,"
                " at data position 0x%x",
                length,
                fp.tell() - 4)
        return None

    if tag != ItemTag:
        logger.warning(
            "Expected Item with tag %s at data position 0x%x",
            ItemTag,
            fp.tell() - 4)
        length = fp.read_UL()
    else:
        length = fp.read_UL()
        logger.debug(
            "%04x: Item, length 0x%x",
            fp.tell() - 8,
            length)

    if length == 0xFFFFFFFF:
        raise ValueError(
            "Encapsulated data fragment had Undefined Length"
            " at data position 0x%x" % (fp.tell() - 4, ))

    item_data = fp.read(length)
    return item_data
