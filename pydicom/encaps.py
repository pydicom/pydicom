# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Functions for working with encapsulated (compressed) pixel data."""

import pydicom.config
from pydicom.filebase import DicomBytesIO
from pydicom.tag import (Tag, ItemTag, SequenceDelimiterTag)


def get_frame_offsets(fp):
    """Return a list of the fragment offsets from the Basic Offset Table.

    Basic Offset Table
    ~~~~~~~~~~~~~~~~~~
    The Basic Offset Table Item must be present and have a tag (FFFE,E000) and
    a length, however it may or may not have a value.

    Basic Offset Table with no value
    Item Tag   | Length    |
    FE FF 00 E0 00 00 00 00

    Basic Offset Table with value (2 frames)
    Item Tag   | Length    | Offset 1  | Offset 2  |
    FE FF 00 E0 08 00 00 00 00 00 00 00 10 00 00 00

    For single or multi-frame images with only one frame, the Basic Offset
    Table may or may not have a value. When it has no value then its length
    shall be 0x00000000.

    For multi-frame images with more than one frame, the Basic Offset Table
    should have a value containing concatenated 32-bit unsigned integer values
    that are the byte offsets to the first byte of the Item tag of the first
    fragment of each frame as measured from the first byte of the first item
    tag following the Basic Offset Table Item.

    All decoders, both for single and multi-frame images should accept both
    an empty Basic Offset Table and one containing offset values.

    Parameters
    ----------
    fp : pydicom.filebase.DicomBytesIO
        The encapsulated pixel data positioned at the start of the Basic Offset
        Table. `fp.is_little_endian` should be set to True.

    Returns
    -------
    offsets : list of int
        The byte offsets to the first fragment of each frame, as measured from
        the start of the first item following the Basic Offset Table item.

    Raises
    ------
    ValueError
        If the Basic Offset Table item's tag is not (FFEE,E000) or if the
        length in bytes of the item's value is not a multiple of 4.

    References
    ----------
    DICOM Standard Part 5, Annex A.4
    """
    if not fp.is_little_endian:
        raise ValueError("'fp.is_little_endian' must be True")

    tag = Tag(fp.read_tag())

    if tag != 0xfffee000:
        raise ValueError("Unexpected tag '{}' when parsing the Basic Table "
                         "Offset item.".format(tag))

    length = fp.read_UL()
    if length % 4:
        raise ValueError("The length of the Basic Offset Table item is not "
                         "a multiple of 4.")

    offsets = []
    # Always return at least a 0 offset
    if length == 0:
        offsets.append(0)

    for ii in range(length // 4):
        offsets.append(fp.read_UL())

    return offsets


def get_pixel_data_fragments(fp):
    """Return the encapsulated pixel data fragments as a list of bytes.

    For compressed (encapsulated) Transfer Syntaxes, the (7fe0,0010) 'Pixel
    Data' element is encoded in an encapsulated format.

    Encapsulation
    -------------
    The encoded pixel data stream is fragmented into one or more Items. The
    stream may represent a single or multi-frame image.

    Each 'Data Stream Fragment' shall have tag of (fffe,e000), followed by a 4
    byte 'Item Length' field encoding the explicit number of bytes in the Item.
    All Items containing an encoded fragment shall have an even number of bytes
    greater than or equal to 2, with the last fragment being padded if
    necessary.

    The first Item in the Sequence of Items shall be a 'Basic Offset Table',
    however the Basic Offset Table item value is not required to be present.
    It is assumed that the Basic Offset Table item has already been read prior
    to calling this function (and that `fp` is positioned past this item).

    The remaining items in the Sequence of Items are the pixel data fragments
    and it is these items that will be read and returned by this function.

    The Sequence of Items is terminated by a Sequence Delimiter Item with tag
    (fffe,e0dd) and an Item Length field of value 0x00000000. The presence or
    absence of the Sequence Delimiter Item in `fp` has no effect on the
    returned fragments.

    Encoding
    ~~~~~~~~
    The encoding of the data shall be little endian.

    Parameters
    ----------
    fp : pydicom.filebase.DicomBytesIO
        The encoded (7fe0,0010) 'Pixel Data' element value, positioned at the
        start of the item tag for the first item after the Basic Offset Table
        item. `fp.is_little_endian` should be set to True.

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
    if not fp.is_little_endian:
        raise ValueError("'fp.is_little_endian' must be True")

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
            # Sequence Delimiter
            # Behave nicely and rewind back to the end of the items
            fp.seek(-4, 1)
            break
        else:
            raise ValueError("Unexpected tag '{0}' at offset {1} when parsing "
                             "the encapsulated pixel data fragment items."
                             .format(tag, fp.tell() - 4))

    return fragments


def get_pixel_data_frames(bytestream):
    """Return the encapsulated pixel data frame(s) as a list of frame data.

    Parameters
    ----------
    bytestream : bytes
        The value of the (7fe0, 0010) 'Pixel Data' element from an encapsulated
        dataset. The Basic Offset Table item should be present and the
        Sequence Delimiter item may or may not be present.

    Returns
    -------
    list of bytes
        The frame(s) contained in the encapsulated pixel data.

    References
    ----------
    DICOM Standard Part 5, Annex A
    """
    return [b''.join(fragments) for fragments in get_pixel_data(bytestream)]


def get_pixel_data(bytestream):
    """Return the encapsulated pixel data as a list of tuples of bytes.

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

    Parameters
    ----------
    bytestream : bytes
        The value of the (7fe0, 0010) 'Pixel Data' element from an encapsulated
        dataset. The Basic Offset Table item should be present and the
        Sequence Delimiter item may or may not be present.

    Returns
    -------
    list of tuple of bytes
        A list of tuples, with each tuple representing an encapsulated pixel
        data frame and the contents of the tuple the frame's fragmented data.

    References
    ----------
    DICOM Standard Part 5, Annex A
    """
    fp = DicomBytesIO(bytestream)
    fp.is_little_endian = True

    # `offsets` is a list of the offsets to the first fragment in each frame
    offsets = get_frame_offsets(fp)
    # Define it now because we change `offsets` later
    no_frames = len(offsets)

    fragments = get_pixel_data_fragments(fp)

    # Need to know the total size of the item fragments
    end = 0
    frag_ends = []
    for frag in fragments:
        # Add 8 bytes for the item tag and length
        end += len(frag) + 8
        frag_ends.append(end)

    offsets.append(frag_ends[-1])

    # For each frame, extend the frame using the next fragment as long as the
    # total frame_length so far is less than the offset for the next frame
    frames = []
    frame_length = 0
    fragment_no = 0
    for ii in range(no_frames):
        frame = []
        while frame_length < offsets[ii + 1]:
            frame.append(fragments[fragment_no])
            # Add 8 bytes for the item tag and length
            frame_length += len(fragments[fragment_no]) + 8
            fragment_no += 1

        frames.append(tuple(frame))

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
