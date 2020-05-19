# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Read a dicom media file"""

from pydicom.misc import size_in_bytes
from struct import Struct, unpack

extra_length_VRs_b = (b'OB', b'OW', b'OF', b'SQ', b'UN', b'UT')
ExplicitVRLittleEndian = b'1.2.840.10008.1.2.1'
ImplicitVRLittleEndian = b'1.2.840.10008.1.2'
DeflatedExplicitVRLittleEndian = b'1.2.840.10008.1.2.1.99'
ExplicitVRBigEndian = b'1.2.840.10008.1.2.2'

ItemTag = 0xFFFEE000  # start of Sequence Item
ItemDelimiterTag = 0xFFFEE00D  # end of Sequence Item
SequenceDelimiterTag = 0xFFFEE0DD  # end of Sequence of undefined length


class dicomfile:
    """Context-manager based DICOM file object with data element iteration"""

    def __init__(self, filename):
        self.fobj = fobj = open(filename, "rb")

        # Read the DICOM preamble, if present
        self.preamble = fobj.read(0x80)
        dicom_prefix = fobj.read(4)
        if dicom_prefix != b"DICM":
            self.preamble = None
            fobj.seek(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.fobj.close()

    def __iter__(self):
        # Need the transfer_syntax later
        transfer_syntax_uid = None

        # Yield the file meta info elements
        file_meta_gen = data_element_generator(
            self.fobj,
            is_implicit_VR=False,
            is_little_endian=True,
            stop_when=lambda gp, elem: gp != 2)
        for data_elem in file_meta_gen:
            if data_elem[0] == (0x0002, 0x0010):
                transfer_syntax_uid = data_elem[3]
            yield data_elem

        # Continue to yield elements from the main data
        if transfer_syntax_uid:
            if transfer_syntax_uid.endswith(b' ') or \
                    transfer_syntax_uid.endswith(b'\0'):
                transfer_syntax_uid = transfer_syntax_uid[:-1]
            is_implicit_VR, is_little_endian = transfer_syntax(
                transfer_syntax_uid)
            # print is_implicit_VR
        else:
            raise NotImplementedError("No transfer syntax in file meta info")

        ds_gen = data_element_generator(self.fobj, is_implicit_VR,
                                        is_little_endian)
        for data_elem in ds_gen:
            yield data_elem

        raise StopIteration


def transfer_syntax(uid):
    """Parse the transfer syntax
    :return: is_implicit_VR, is_little_endian
    """
    # Assume a transfer syntax, correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    if uid == ImplicitVRLittleEndian:
        pass
    elif uid == ExplicitVRLittleEndian:
        is_implicit_VR = False
    elif uid == ExplicitVRBigEndian:
        is_implicit_VR = False
        is_little_endian = False
    elif uid == DeflatedExplicitVRLittleEndian:
        raise NotImplementedError("This reader does not handle deflate files")
    else:
        # PS 3.5-2008 A.4 (p63): other syntax (e.g all compressed)
        #    should be Explicit VR Little Endian,
        is_implicit_VR = False
    return is_implicit_VR, is_little_endian


####
def data_element_generator(fp,
                           is_implicit_VR,
                           is_little_endian,
                           stop_when=None,
                           defer_size=None):
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
                    VR = dictionary_VR(tag)
                except KeyError:
                    # Look ahead to see if it consists of items and
                    # is thus a SQ
                    next_tag = TupleTag(unpack(endian_chr + "HH", fp_read(4)))
                    # Rewind the file
                    fp.seek(fp_tell() - 4)
                    if next_tag == ItemTag:
                        VR = b'SQ'

            if VR == b'SQ':
                yield ((group, elem), VR, length, None, value_tell)
                # seq = read_sequence(fp, is_implicit_VR,
                #                     is_little_endian, length, encoding)
                # yield DataElement(tag, VR, seq, value_tell,
                #                   is_undefined_length=True)
            else:
                raise NotImplementedError("This reader does not handle "
                                          "undefined length except for SQ")
                from pydicom.fileio.fileutil import read_undefined_length_value

                delimiter = SequenceDelimiterTag
                value = read_undefined_length_value(fp, is_little_endian,
                                                    delimiter, defer_size)
                yield ((group, elem), VR, length, value, value_tell)
