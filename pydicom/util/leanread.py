# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Read a dicom media file"""

import pathlib
from struct import Struct, unpack
from types import TracebackType
from typing import (
    Iterator, Tuple, Optional, Union, Type, cast, BinaryIO, Callable
)

from pydicom.misc import size_in_bytes
from pydicom.datadict import dictionary_VR
from pydicom.tag import TupleTag
from pydicom.uid import UID

extra_length_VRs_b = (b'OB', b'OW', b'OF', b'SQ', b'UN', b'UT')
ExplicitVRLittleEndian = b'1.2.840.10008.1.2.1'
ImplicitVRLittleEndian = b'1.2.840.10008.1.2'
DeflatedExplicitVRLittleEndian = b'1.2.840.10008.1.2.1.99'
ExplicitVRBigEndian = b'1.2.840.10008.1.2.2'

ItemTag = 0xFFFEE000  # start of Sequence Item

_ElementType = Tuple[
    Tuple[int, int], Optional[bytes], int, Optional[bytes], int
]


class dicomfile:
    """Context-manager based DICOM file object with data element iteration"""

    def __init__(self, filename: Union[str, pathlib.Path]) -> None:
        self.fobj = fobj = open(filename, "rb")

        # Read the DICOM preamble, if present
        self.preamble: Optional[bytes] = fobj.read(0x80)
        dicom_prefix = fobj.read(4)
        if dicom_prefix != b"DICM":
            self.preamble = None
            fobj.seek(0)

    def __enter__(self) -> "dicomfile":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        self.fobj.close()

        return None

    def __iter__(self) -> Iterator[_ElementType]:
        # Need the transfer_syntax later
        tsyntax: Optional[bytes] = None

        # Yield the file meta info elements
        file_meta_gen = data_element_generator(
            self.fobj,
            is_implicit_VR=False,
            is_little_endian=True,
            stop_when=lambda gp, elem: gp != 2
        )

        for data_elem in file_meta_gen:
            if data_elem[0] == (0x0002, 0x0010):
                tsyntax = data_elem[3]

            yield data_elem

        # Continue to yield elements from the main data
        if tsyntax:
            if tsyntax.endswith(b' ') or tsyntax.endswith(b'\0'):
                tsyntax = tsyntax[:-1]
            is_implicit_VR, is_little_endian = transfer_syntax(tsyntax)
            # print is_implicit_VR
        else:
            raise NotImplementedError("No transfer syntax in file meta info")

        ds_gen = data_element_generator(
            self.fobj, is_implicit_VR, is_little_endian
        )
        for data_elem in ds_gen:
            yield data_elem

        raise StopIteration


def transfer_syntax(uid: bytes) -> Tuple[bool, bool]:
    """Parse the transfer syntax
    :return: is_implicit_VR, is_little_endian
    """
    # Assume a transfer syntax, correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    s = uid.decode('ascii')
    if s == ImplicitVRLittleEndian:
        pass
    elif s == ExplicitVRLittleEndian:
        is_implicit_VR = False
    elif s == ExplicitVRBigEndian:
        is_implicit_VR = False
        is_little_endian = False
    elif s == DeflatedExplicitVRLittleEndian:
        raise NotImplementedError("This reader does not handle deflate files")
    else:
        # PS 3.5-2008 A.4 (p63): other syntax (e.g all compressed)
        #    should be Explicit VR Little Endian,
        is_implicit_VR = False
    return is_implicit_VR, is_little_endian


####
def data_element_generator(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    stop_when: Optional[Callable[[int, int], bool]] = None,
    defer_size: Optional[Union[str, int, float]] = None,
) -> Iterator[_ElementType]:
    """:return: (tag, VR, length, value, value_tell,
                                 is_implicit_VR, is_little_endian)
    """
    if is_little_endian:
        endian_chr = "<"
    else:
        endian_chr = ">"
    if is_implicit_VR:
        element_struct = Struct(endian_chr + "HHL")
    else:  # Explicit VR
        # tag, VR, 2-byte length (or 0 if special VRs)
        element_struct = Struct(endian_chr + "HH2sH")
        extra_length_struct = Struct(endian_chr + "L")  # for special VRs
        extra_length_unpack = extra_length_struct.unpack  # for lookup speed

    # Make local variables so have faster lookup
    fp_read = fp.read
    fp_tell = fp.tell
    element_struct_unpack = element_struct.unpack
    defer_size = size_in_bytes(defer_size)

    while True:
        # Read tag, VR, length, get ready to read value
        bytes_read = fp_read(8)
        if len(bytes_read) < 8:
            raise StopIteration  # at end of file

        if is_implicit_VR:
            # must reset VR each time; could have set last iteration (e.g. SQ)
            VR = None
            group, elem, length = element_struct_unpack(bytes_read)
        else:  # explicit VR
            group, elem, VR, length = element_struct_unpack(bytes_read)
            if VR in extra_length_VRs_b:
                bytes_read = fp_read(4)
                length = extra_length_unpack(bytes_read)[0]

        # Positioned to read the value, but may not want to -- check stop_when
        value_tell = fp_tell()
        if stop_when is not None:
            if stop_when(group, elem):
                rewind_length = 8
                if not is_implicit_VR and VR in extra_length_VRs_b:
                    rewind_length += 4
                fp.seek(value_tell - rewind_length)
                raise StopIteration

        # Reading the value
        # First case (most common): reading a value with a defined length
        if length != 0xFFFFFFFF:
            if defer_size is not None and length > defer_size:
                # Flag as deferred by setting value to None, and skip bytes
                value = None
                fp.seek(fp_tell() + length)
            else:
                value = fp_read(length)
            # import pdb;pdb.set_trace()
            yield ((group, elem), VR, length, value, value_tell)

        # Second case: undefined length - must seek to delimiter,
        # unless is SQ type, in which case is easier to parse it, because
        # undefined length SQs and items of undefined lengths can be nested
        # and it would be error-prone to read to the correct outer delimiter
        else:
            # Try to look up type to see if is a SQ
            # if private tag, won't be able to look it up in dictionary,
            #   in which case just ignore it and read the bytes unless it is
            #   identified as a Sequence
            if VR is None:
                try:
                    VR = dictionary_VR((group, elem)).encode('ascii')
                except KeyError:
                    # Look ahead to see if it consists of items and
                    # is thus a SQ
                    next_tag = TupleTag(
                        cast(
                            Tuple[int, int],
                            unpack(endian_chr + "HH", fp_read(4)),
                        )
                    )
                    # Rewind the file
                    fp.seek(fp_tell() - 4)
                    if next_tag == ItemTag:
                        VR = b'SQ'

            if VR == b'SQ':
                yield ((group, elem), VR, length, None, value_tell)
            else:
                raise NotImplementedError("This reader does not handle "
                                          "undefined length except for SQ")
