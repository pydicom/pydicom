# encaps.py
"""Routines for working with encapsulated (compressed) data

"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom

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

import pydicom.config

from pydicom.filebase import DicomBytesIO
from pydicom.tag import (ItemTag, SequenceDelimiterTag)


def decode_data_sequence(data):
    """Read encapsulated data and return a list of strings
    data -- string of encapsulated data, typically
    dataset.PixelData
    Return all fragments in a list of byte strings
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
    """Read encapsulated data and return one continuous string
    data -- string of encapsulated data, typically dataset.PixelData
    Return all fragments concatenated together as a byte string
    If PixelData has multiple frames, then should separate
    out before calling this routine.
    """
    return b"".join(decode_data_sequence(data))


# read_item modeled after filereader.ReadSequenceItem
def read_item(fp):
    """Read and return a single Item in the
    fragmented data stream"""

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
