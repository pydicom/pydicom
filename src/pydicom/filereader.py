# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Read a dicom media file"""


# Need zlib and io.BytesIO for deflate-compressed file
import os
from struct import Struct, unpack
from typing import BinaryIO, Any, cast
from collections.abc import Callable, MutableSequence, Iterator
import zlib

from pydicom import config
from pydicom.charset import default_encoding, convert_encodings
from pydicom.config import logger
from pydicom.datadict import _dictionary_vr_fast
from pydicom.dataelem import (
    DataElement,
    RawDataElement,
    convert_raw_data_element,
    empty_value_for_VR,
)
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.errors import InvalidDicomError
from pydicom.filebase import ReadableBuffer, DicomBytesIO
from pydicom.fileutil import (
    read_undefined_length_value,
    path_from_pathlike,
    PathType,
    _unpack_tag,
)
from pydicom.misc import size_in_bytes, warn_and_log
from pydicom.sequence import Sequence
from pydicom.tag import (
    ItemTag,
    SequenceDelimiterTag,
    Tag,
    BaseTag,
    TagListType,
)
import pydicom.uid
from pydicom.util.hexutil import bytes2hex
from pydicom.valuerep import EXPLICIT_VR_LENGTH_32, VR as VR_


ENCODED_VR = {vr.encode(default_encoding) for vr in VR_}


def data_element_generator(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    stop_when: Callable[[BaseTag, str | None, int], bool] | None = None,
    defer_size: int | str | float | None = None,
    encoding: str | MutableSequence[str] = default_encoding,
    specific_tags: list[BaseTag | int] | None = None,
) -> Iterator[RawDataElement | DataElement]:
    """Create a generator to efficiently return the raw data elements.

    .. note::

        This function is used internally - usually there is no need to call it
        from user code. To read data from a DICOM file, :func:`dcmread`
        shall be used instead.

    Parameters
    ----------
    fp : file-like
        The file-like to read from.
    is_implicit_VR : bool
        ``True`` if the data is encoded as implicit VR, ``False`` otherwise.
    is_little_endian : bool
        ``True`` if the data is encoded as little endian, ``False`` otherwise.
    stop_when : None, callable, optional
        If ``None`` (default), then the whole file is read. A callable which
        takes tag, VR, length, and returns ``True`` or ``False``. If it
        returns ``True``, ``read_data_element`` will just return.
    defer_size : int, str or float, optional
        See :func:`dcmread` for parameter info.
    encoding : str | MutableSequence[str]
        Encoding scheme
    specific_tags : list or None
        See :func:`dcmread` for parameter info.

    Yields
    -------
    RawDataElement or DataElement
        Yields DataElement for undefined length UN or SQ, RawDataElement
        otherwise.
    """
    # Summary of DICOM standard PS3.5-2008 chapter 7:
    # If Implicit VR, data element is:
    #    tag, 4-byte length, value.
    #        The 4-byte length can be FFFFFFFF (undefined length)*
    #
    # If Explicit VR:
    #    if OB, OW, OF, SQ, UN, or UT:
    #       tag, VR, 2-bytes reserved (both zero), 4-byte length, value
    #           For all but UT, the length can be FFFFFFFF (undefined length)*
    #   else: (any other VR)
    #       tag, VR, (2 byte length), value
    # * for undefined length, a Sequence Delimitation Item marks the end
    #        of the Value Field.
    # Note, except for the special_VRs, both impl and expl VR use 8 bytes;
    #    the special VRs follow the 8 bytes with a 4-byte length

    # With a generator, state is stored, so we can break down
    #    into the individual cases, and not have to check them again for each
    #    data element
    from pydicom.values import convert_string

    endian_chr = "><"[is_little_endian]

    # assign implicit VR struct to variable as use later if VR assumed missing
    implicit_VR_unpack = Struct(f"{endian_chr}HHL").unpack
    if is_implicit_VR:
        element_struct_unpack = implicit_VR_unpack
    else:  # Explicit VR
        # tag, VR, 2-byte length (or 0 if special VRs)
        element_struct_unpack = Struct(f"{endian_chr}HH2sH").unpack
        extra_length_unpack = Struct(f"{endian_chr}L").unpack  # for lookup speed

    # Make local variables so have faster lookup
    fp_read = fp.read
    fp_seek = fp.seek
    fp_tell = fp.tell
    logger_debug = logger.debug
    debugging = config.debugging
    defer_size = size_in_bytes(defer_size)

    tag_set: set[int] = {tag for tag in specific_tags} if specific_tags else set()
    has_tag_set = bool(tag_set)
    if has_tag_set:
        tag_set.add(0x00080005)  # Specific Character Set

    while True:
        # VR: str | None
        # Read tag, VR, length, get ready to read value
        if len(bytes_read := fp_read(8)) < 8:
            return  # at end of file

        if debugging:
            debug_msg = f"{fp.tell() - 8:08x}: {bytes2hex(bytes_read)}"

        if is_implicit_VR:
            # must reset VR each time; could have set last iteration (e.g. SQ)
            vr = None
            group, elem, length = element_struct_unpack(bytes_read)
        else:  # explicit VR
            group, elem, vr, length = element_struct_unpack(bytes_read)
            # defend against switching to implicit VR, some writer do in SQ's
            # issue 1067, issue 1035

            if vr in ENCODED_VR:  # try most likely solution first
                vr = vr.decode(default_encoding)
                if vr in EXPLICIT_VR_LENGTH_32:
                    bytes_read = fp_read(4)
                    length = extra_length_unpack(bytes_read)[0]
                    if debugging:
                        debug_msg += " " + bytes2hex(bytes_read)
            elif not (b"AA" <= vr <= b"ZZ") and config.assume_implicit_vr_switch:
                # invalid VR, must be 2 cap chrs, assume implicit and continue
                if debugging:
                    logger.warning(
                        f"Unknown VR '0x{vr[0]:02x}{vr[1]:02x}' assuming "
                        "implicit VR encoding"
                    )
                vr = None
                group, elem, length = implicit_VR_unpack(bytes_read)
            else:
                # Either an unimplemented VR or implicit VR encoding
                # Note that we treat an unimplemented VR as having a 2-byte
                #   length, but that may not be correct
                vr = vr.decode(default_encoding)
                if debugging:
                    logger.warning(
                        f"Unknown VR '{vr}' assuming explicit VR encoding with "
                        "2-byte length"
                    )

        if debugging:
            debug_msg = f"{debug_msg:<47s}  ({group:04X},{elem:04X})"
            if not is_implicit_VR:
                debug_msg += f" {vr} "
            if length != 0xFFFFFFFF:
                debug_msg += f"Length: {length}"
            else:
                debug_msg += "Length: Undefined length (FFFFFFFF)"
            logger_debug(debug_msg)

        # Positioned to read the value, but may not want to -- check stop_when
        value_tell = fp_tell()
        tag = group << 16 | elem
        if tag == 0xFFFEE00D:
            # The item delimitation item of an undefined length dataset in
            #   a sequence, length is 0
            # If we hit this then we're at the end of the current dataset
            return

        if stop_when is not None:
            # XXX VR may be None here!! Should stop_when just take tag?
            if stop_when(BaseTag(tag), vr, length):
                if debugging:
                    logger_debug(
                        "Reading ended by stop_when callback. "
                        "Rewinding to start of data element."
                    )
                rewind_length = 8
                if not is_implicit_VR and vr in EXPLICIT_VR_LENGTH_32:
                    rewind_length += 4
                fp_seek(value_tell - rewind_length)
                return

        # Reading the value
        # First case (most common): reading a value with a defined length
        if length != 0xFFFFFFFF:
            # don't defer loading of Specific Character Set value as it is
            # needed immediately to get the character encoding for other tags
            if has_tag_set and tag not in tag_set:
                # skip the tag if not in specific tags
                fp_seek(fp_tell() + length)
                continue

            if (
                defer_size is not None
                and length > defer_size
                and tag != 0x00080005  # charset
            ):
                # Flag as deferred by setting value to None, and skip bytes
                value = None
                if debugging:
                    logger_debug(
                        "Defer size exceeded. Skipping forward to next data element."
                    )
                fp_seek(fp_tell() + length)
            else:
                value = (
                    fp_read(length)
                    if length > 0
                    else cast(bytes | None, empty_value_for_VR(vr, raw=True))
                )
                if debugging:
                    dotdot = "..." if length > 20 else "   "
                    displayed_value = value[:20] if value else b""
                    logger_debug(
                        "%08x: %-34s %s %r %s"
                        % (
                            value_tell,
                            bytes2hex(displayed_value),
                            dotdot,
                            displayed_value,
                            dotdot,
                        )
                    )

            # If the tag is (0008,0005) Specific Character Set, then store it
            if tag == 0x00080005:
                # *Specific Character String* is b'' for empty value
                encoding = convert_string(cast(bytes, value) or b"", is_little_endian)
                # Store the encoding value in the generator
                # for use with future elements (SQs)
                encoding = convert_encodings(encoding)

            yield RawDataElement(
                BaseTag(tag),
                vr,
                length,
                value,
                value_tell,
                is_implicit_VR,
                is_little_endian,
            )

        # Second case: undefined length - must seek to delimiter,
        # unless is SQ type, in which case is easier to parse it, because
        # undefined length SQs and items of undefined lengths can be nested
        # and it would be error-prone to read to the correct outer delimiter
        else:
            # VR UN with undefined length shall be handled as SQ
            # see PS 3.5, section 6.2.2
            if vr == VR_.UN and config.settings.infer_sq_for_un_vr:
                vr = VR_.SQ
            # Try to look up type to see if is a SQ
            # if private tag, won't be able to look it up in dictionary,
            #   in which case just ignore it and read the bytes unless it is
            #   identified as a Sequence
            if vr is None or vr == VR_.UN and config.replace_un_with_known_vr:
                try:
                    vr = _dictionary_vr_fast(tag)
                except KeyError:
                    # Look ahead to see if it consists of items
                    # and is thus a SQ
                    next_tag = _unpack_tag(fp_read(4), endian_chr)
                    # Rewind the file
                    fp_seek(fp_tell() - 4)
                    if next_tag == ItemTag:
                        vr = VR_.SQ

            if vr == VR_.SQ:
                if debugging:
                    logger_debug(
                        f"{fp_tell():08X}: Reading/parsing undefined length sequence"
                    )

                seq = read_sequence(
                    fp, is_implicit_VR, is_little_endian, length, encoding
                )
                if has_tag_set and tag not in tag_set:
                    continue

                yield DataElement(
                    BaseTag(tag), vr, seq, value_tell, is_undefined_length=True
                )
            else:
                if debugging:
                    logger_debug("Reading undefined length data element")

                value = read_undefined_length_value(
                    fp, is_little_endian, SequenceDelimiterTag, defer_size
                )

                # tags with undefined length are skipped after read
                if has_tag_set and tag not in tag_set:
                    continue

                yield RawDataElement(
                    BaseTag(tag),
                    vr,
                    length,
                    value,
                    value_tell,
                    is_implicit_VR,
                    is_little_endian,
                )


def _is_implicit_vr(
    fp: BinaryIO,
    implicit_vr_is_assumed: bool,
    is_little_endian: bool,
    stop_when: Callable[[BaseTag, str | None, int], bool] | None,
    is_sequence: bool,
) -> bool:
    """Check if the real VR is explicit or implicit.

    Parameters
    ----------
    fp : an opened file object
    implicit_vr_is_assumed : bool
        True if implicit VR is assumed.
        If this does not match with the real transfer syntax, a user warning
        will be issued.
    is_little_endian : bool
        True if file has little endian transfer syntax.
        Needed to interpret the first tag.
    stop_when : None, optional
        Optional call_back function which can terminate reading.
        Needed to check if the next tag still belongs to the read dataset.
    is_sequence : bool
        True if called for a sequence, False for a top-level dataset.

    Returns
    -------
    True if implicit VR is used, False otherwise.
    """
    # sequences do not switch from implicit to explicit encoding,
    # but they are allowed to use implicit encoding if the dataset
    # is encoded as explicit VR
    if is_sequence and implicit_vr_is_assumed:
        return True

    tag_bytes = fp.read(4)
    raw_vr = fp.read(2)
    if len(raw_vr) < 2:
        return implicit_vr_is_assumed

    # it is sufficient to check if the VR is in valid ASCII range, as it is
    # extremely unlikely that the tag length accidentally has such a
    # representation - this would need the first tag to be longer than 16kB
    # (e.g. it should be > 0x4141 = 16705 bytes)
    found_implicit = not (0x40 < raw_vr[0] < 0x5B and 0x40 < raw_vr[1] < 0x5B)
    if found_implicit != implicit_vr_is_assumed:
        # first check if the tag still belongs to the dataset if stop_when
        # is given - if not, the dataset is empty and we just return
        endian_chr = "<" if is_little_endian else ">"
        tag = _unpack_tag(tag_bytes, endian_chr)
        vr = raw_vr.decode(default_encoding)
        if stop_when is not None and stop_when(tag, vr, 0):
            return found_implicit

        # sequences with undefined length can be encoded in implicit VR,
        # see PS 3.5, section 6.2.2
        if found_implicit and is_sequence:
            return True

        # got to the real problem - warn or raise depending on config
        found_vr = "implicit" if found_implicit else "explicit"
        expected_vr = "implicit" if not found_implicit else "explicit"
        msg = f"Expected {expected_vr} VR, but found {found_vr} VR"
        if config.settings.reading_validation_mode == config.RAISE:
            raise InvalidDicomError(msg)

        warn_and_log(f"{msg} - using {found_vr} VR for reading", UserWarning)

    return found_implicit


def read_dataset(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    bytelength: int | None = None,
    stop_when: Callable[[BaseTag, str | None, int], bool] | None = None,
    defer_size: str | int | float | None = None,
    parent_encoding: str | MutableSequence[str] = default_encoding,
    specific_tags: list[BaseTag | int] | None = None,
    at_top_level: bool = True,
) -> Dataset:
    """Return a :class:`~pydicom.dataset.Dataset` instance containing the next
    dataset in the file.

    Parameters
    ----------
    fp : file-like
        An opened file-like object.
    is_implicit_VR : bool
        ``True`` if file transfer syntax is implicit VR.
    is_little_endian : bool
        ``True`` if file has little endian transfer syntax.
    bytelength : int, None, optional
        ``None`` to read until end of file or ItemDelimiterTag, else a fixed
        number of bytes to read
    stop_when : None, optional
        Optional call_back function which can terminate reading. See help for
        :func:`data_element_generator` for details
    defer_size : int, str or float, optional
        Size to avoid loading large elements in memory. See :func:`dcmread` for
        more parameter info.
    parent_encoding : str or List[str]
        Optional encoding to use as a default in case (0008,0005) *Specific
        Character Set* isn't specified.
    specific_tags : list of BaseTag, optional
        See :func:`dcmread` for parameter info.
    at_top_level: bool
        If dataset is top level (not within a sequence).
        Used to turn off explicit VR heuristic within sequences

    Returns
    -------
    dataset.Dataset
        A Dataset instance.

    See Also
    --------
    :class:`~pydicom.dataset.Dataset`
        A collection (dictionary) of DICOM
        :class:`~pydicom.dataelem.DataElement` instances.
    """
    raw_data_elements: dict[BaseTag, RawDataElement | DataElement] = {}
    fp_tell = fp.tell
    fp_start = fp.tell()
    is_implicit_VR = _is_implicit_vr(
        fp, is_implicit_VR, is_little_endian, stop_when, is_sequence=not at_top_level
    )
    fp.seek(fp_start)
    de_gen = data_element_generator(
        fp,
        is_implicit_VR,
        is_little_endian,
        stop_when,
        defer_size,
        parent_encoding,
        specific_tags,
    )
    try:
        if bytelength is None:
            raw_data_elements = {e.tag: e for e in de_gen}
        else:
            while fp_tell() - fp_start < bytelength:
                raw_data_element = next(de_gen)
                raw_data_elements[raw_data_element.tag] = raw_data_element
    except StopIteration:
        pass
    except EOFError as details:
        if config.settings.reading_validation_mode == config.RAISE:
            raise
        msg = str(details) + " in file " + getattr(fp, "name", "<no filename>")
        warn_and_log(msg, UserWarning)
    except NotImplementedError as details:
        logger.error(details)

    ds = Dataset(raw_data_elements, parent_encoding=parent_encoding)

    encoding: str | MutableSequence[str]
    if 0x00080005 in raw_data_elements:
        elem = cast(RawDataElement, raw_data_elements[BaseTag(0x00080005)])
        char_set = cast(
            str | MutableSequence[str] | None, convert_raw_data_element(elem).value
        )
        encoding = convert_encodings(char_set)  # -> List[str]
    else:
        encoding = parent_encoding  # -> str | MutableSequence[str]

    ds.set_original_encoding(is_implicit_VR, is_little_endian, encoding)
    return ds


def read_sequence(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    bytelength: int,
    encoding: str | MutableSequence[str],
    offset: int = 0,
) -> Sequence:
    """Read and return a :class:`~pydicom.sequence.Sequence` -- i.e. a
    :class:`list` of :class:`Datasets<pydicom.dataset.Dataset>`.
    """
    seq = []  # use builtin list to start for speed, convert to Sequence at end
    is_undefined_length = False
    if bytelength != 0:  # SQ of length 0 possible (PS 3.5-2008 7.5.1a (p.40)
        if bytelength == 0xFFFFFFFF:
            is_undefined_length = True
            bytelength = 0

        fp_tell = fp.tell  # for speed in loop
        fpStart = fp_tell()
        while (not bytelength) or (fp_tell() - fpStart < bytelength):
            file_tell = fp_tell()
            dataset = read_sequence_item(
                fp, is_implicit_VR, is_little_endian, encoding, offset
            )
            if dataset is None:  # None is returned if hit Sequence Delimiter
                break

            dataset.file_tell = file_tell + offset
            seq.append(dataset)

    sequence = Sequence(seq)
    sequence.is_undefined_length = is_undefined_length
    return sequence


def read_sequence_item(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    encoding: str | MutableSequence[str],
    offset: int = 0,
) -> Dataset | None:
    """Read and return a single :class:`~pydicom.sequence.Sequence` item, i.e.
    a :class:`~pydicom.dataset.Dataset`.
    """
    seq_item_tell = fp.tell() + offset
    tag_length_format = "<HHL" if is_little_endian else ">HHL"

    try:
        bytes_read = fp.read(8)
        group, element, length = unpack(tag_length_format, bytes_read)
    except BaseException:
        raise OSError(f"No tag to read at file position {fp.tell() + offset:X}")

    tag = (group, element)
    if tag == SequenceDelimiterTag:  # No more items, time to stop reading
        if config.debugging:
            logger.debug(f"{fp.tell() - 8 + offset:08x}: End of Sequence")
            if length != 0:
                logger.warning(
                    f"Expected 0x00000000 after delimiter, found 0x{length:X}, "
                    f"at position 0x{fp.tell() - 4 + offset:X}"
                )
        return None

    if config.debugging:
        if tag != ItemTag:
            # Flag the incorrect item encoding, will usually raise an
            #   exception afterwards due to the misaligned format
            logger.warning(
                f"Expected sequence item with tag {ItemTag} at file position "
                f"0x{fp.tell() - 4 + offset:X}"
            )
        else:
            logger.debug(
                f"{fp.tell() - 4 + offset:08x}: {bytes2hex(bytes_read)}  "
                "Found Item tag (start of item)"
            )

    if length == 0xFFFFFFFF:
        ds = read_dataset(
            fp,
            is_implicit_VR,
            is_little_endian,
            bytelength=None,
            parent_encoding=encoding,
            at_top_level=False,
        )
        ds.is_undefined_length_sequence_item = True
    else:
        ds = read_dataset(
            fp,
            is_implicit_VR,
            is_little_endian,
            length,
            parent_encoding=encoding,
            at_top_level=False,
        )
        ds.is_undefined_length_sequence_item = False

        if config.debugging:
            logger.debug(f"{fp.tell() + offset:08X}: Finished sequence item")

    ds.seq_item_tell = seq_item_tell
    return ds


def _read_command_set_elements(fp: BinaryIO) -> Dataset:
    """Return a Dataset containing any Command Set (0000,eeee) elements
    in `fp`.

    Command Set elements are always Implicit VR Little Endian (DICOM Standard,
    Part 7, :dcm:`Section 6.3<part07/sect_6.3.html>`). Once any Command Set
    elements are read `fp` will be positioned at the start of the next group
    of elements.

    Parameters
    ----------
    fp : file-like
        The file-like positioned at the start of any command set elements.

    Returns
    -------
    dataset.Dataset
        The command set elements as a Dataset instance. May be empty if no
        command set elements are present.
    """

    def _not_group_0000(tag: BaseTag, vr: str | None, length: int) -> bool:
        """Return True if the tag is not in group 0x0000, False otherwise."""
        return tag >> 16 != 0

    return read_dataset(
        fp, is_implicit_VR=True, is_little_endian=True, stop_when=_not_group_0000
    )


def _read_file_meta_info(fp: BinaryIO) -> FileMetaDataset:
    """Return a Dataset containing any File Meta (0002,eeee) elements in `fp`.

    File Meta elements are always Explicit VR Little Endian (DICOM Standard,
    Part 10, :dcm:`Section 7<part10/chapter_7.html>`). Once any File Meta
    elements are read `fp` will be positioned at the start of the next group
    of elements.

    Parameters
    ----------
    fp : file-like
        The file-like positioned at the start of any File Meta Information
        group elements.

    Returns
    -------
    dataset.Dataset
        The File Meta elements as a Dataset instance. May be empty if no
        File Meta are present.
    """

    def _not_group_0002(tag: BaseTag, vr: str | None, length: int) -> bool:
        """Return True if the tag is not in group 0x0002, False otherwise."""
        return tag >> 16 != 2

    start_file_meta = fp.tell()
    file_meta = FileMetaDataset(
        read_dataset(
            fp, is_implicit_VR=False, is_little_endian=True, stop_when=_not_group_0002
        )
    )
    file_meta.set_original_encoding(
        is_implicit_vr=False, is_little_endian=True, character_encoding=default_encoding
    )
    if not file_meta._dict:
        return file_meta

    # Test the file meta for correct interpretation by requesting the first
    #   data element: if it fails, retry loading the file meta with an
    #   implicit VR (issue #503)
    try:
        file_meta[list(file_meta.elements())[0].tag]
    except NotImplementedError:
        fp.seek(start_file_meta)
        file_meta = FileMetaDataset(
            read_dataset(
                fp,
                is_implicit_VR=True,
                is_little_endian=True,
                stop_when=_not_group_0002,
            )
        )
        file_meta.set_original_encoding(
            is_implicit_vr=True,
            is_little_endian=True,
            character_encoding=default_encoding,
        )

    # Log if the Group Length doesn't match actual length
    if "FileMetaInformationGroupLength" in file_meta:
        # FileMetaInformationGroupLength must be 12 bytes long and its value
        #   counts from the beginning of the next element to the end of the
        #   file meta elements
        actual_len = fp.tell() - (start_file_meta + 12)
        elem_len = file_meta.FileMetaInformationGroupLength
        if elem_len != actual_len:
            logger.info(
                "_read_file_meta_info: (0002,0000) 'File Meta Information "
                "Group Length' value doesn't match the actual File Meta "
                f"Information length ({elem_len} vs {actual_len} bytes)"
            )

    return file_meta


def read_file_meta_info(filename: PathType) -> FileMetaDataset:
    """Read and return the DICOM file meta information only.

    This function is meant to be used in user code, for quickly going through
    a series of files to find one which is referenced to a particular SOP,
    without having to read the entire files.
    """
    with open(filename, "rb") as fp:
        read_preamble(fp, False)  # if no header, raise exception
        return _read_file_meta_info(fp)


def read_preamble(fp: BinaryIO, force: bool) -> bytes | None:
    """Return the 128-byte DICOM preamble in `fp` if present.

    `fp` should be positioned at the start of the file-like. If the preamble
    and prefix are found then after reading `fp` will be positioned at the
    first byte after the prefix (byte offset 133). If either the preamble or
    prefix are missing and `force` is ``True`` then after reading `fp` will be
    positioned at the start of the file-like.

    Parameters
    ----------
    fp : file-like object
        The file-like to read the preamble from.
    force : bool
        Flag to force reading of a file even if no header is found.

    Returns
    -------
    preamble : bytes or None
        The 128-byte DICOM preamble will be returned if the appropriate prefix
        ('DICM') is found at byte offset 128. Returns ``None`` if the 'DICM'
        prefix is not found and `force` is ``True``.

    Raises
    ------
    InvalidDicomError
        If `force` is ``False`` and no appropriate header information found.

    Notes
    -----
    Also reads past the 'DICM' marker. Rewinds file to the beginning if
    no header found.
    """
    logger.debug("Reading File Meta Information preamble...")
    preamble = fp.read(128)
    if config.debugging:
        sample = bytes2hex(preamble[:8]) + "..." + bytes2hex(preamble[-8:])
        logger.debug(f"{fp.tell() - 128:08x}: {sample}")

    logger.debug("Reading File Meta Information prefix...")
    magic = fp.read(4)
    if magic != b"DICM" and force:
        logger.info(
            "File is not conformant with the DICOM File Format: 'DICM' "
            "prefix is missing from the File Meta Information header "
            "or the header itself is missing. Assuming no header and "
            "continuing."
        )
        fp.seek(0)
        return None

    if magic != b"DICM" and not force:
        raise InvalidDicomError(
            "File is missing DICOM File Meta Information header or the 'DICM' "
            "prefix is missing from the header. Use force=True to force "
            "reading."
        )
    else:
        logger.debug(f"{fp.tell() - 4:08x}: 'DICM' prefix found")

    return preamble


def _at_pixel_data(tag: BaseTag, vr: str | None, length: int) -> bool:
    return tag in {0x7FE00010, 0x7FE00009, 0x7FE00008}


def read_partial(
    fileobj: BinaryIO,
    stop_when: Callable[[BaseTag, str | None, int], bool] | None = None,
    defer_size: int | str | float | None = None,
    force: bool = False,
    specific_tags: list[BaseTag | int] | None = None,
) -> FileDataset:
    """Parse a DICOM file until a condition is met.

    Parameters
    ----------
    fileobj : a file-like object
        Note that the file will not close when the function returns.
    stop_when :
        Stop condition. See :func:`read_dataset` for more info.
    defer_size : int, str or float, optional
        See :func:`dcmread` for parameter info.
    force : bool
        See :func:`dcmread` for parameter info.
    specific_tags : list or None
        See :func:`dcmread` for parameter info.

    Notes
    -----
    Use :func:`dcmread` unless you need to stop on some condition other than
    reaching pixel data.

    Returns
    -------
    dataset.FileDataset
        The read dataset.

    See Also
    --------
    dcmread
        More generic file reading function.
    """
    # Read File Meta Information

    # Read preamble (if present)
    preamble = read_preamble(fileobj, force)
    # Read any File Meta Information group (0002,eeee) elements (if present)
    file_meta = _read_file_meta_info(fileobj)

    # Read Dataset

    # Read any Command Set group (0000,eeee) elements (if present)
    command_set = _read_command_set_elements(fileobj)

    # Check to see if there's anything left to read
    peek = fileobj.read(1)
    if peek != b"":
        fileobj.seek(-1, 1)

    # `filobj` should be positioned at the start of the dataset by this point.
    # Ensure we have appropriate values for `is_implicit_VR` and
    # `is_little_endian` before we try decoding. We assume an initial
    # transfer syntax of implicit VR little endian and correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    transfer_syntax = file_meta.get("TransferSyntaxUID")
    if peek == b"":  # EOF
        pass
    elif transfer_syntax is None:  # issue 258
        # If no TransferSyntaxUID element then we have to try and figure out
        #   the correct values for `is_little_endian` and `is_implicit_VR`.
        # Peek at the first 6 bytes to get the first element's tag group and
        #   (possibly) VR
        group, _, vr = unpack("<HH2s", fileobj.read(6))
        fileobj.seek(-6, 1)

        # Test the VR to see if it's valid, and if so then assume explicit VR
        from pydicom.values import converters

        vr = vr.decode(default_encoding)
        if vr in converters.keys():
            is_implicit_VR = False
            # Big endian encoding can only be explicit VR
            #   Big endian 0x0004 decoded as little endian will be 1024
            #   Big endian 0x0100 decoded as little endian will be 1
            # Therefore works for big endian tag groups up to 0x00FF after
            #   which it will fail, in which case we leave it as little endian
            #   and hope for the best (big endian is retired anyway)
            if group >= 1024:
                is_little_endian = False
    elif transfer_syntax == pydicom.uid.ImplicitVRLittleEndian:
        pass
    elif transfer_syntax == pydicom.uid.ExplicitVRLittleEndian:
        is_implicit_VR = False
    elif transfer_syntax == pydicom.uid.ExplicitVRBigEndian:
        is_implicit_VR = False
        is_little_endian = False
    elif transfer_syntax == pydicom.uid.DeflatedExplicitVRLittleEndian:
        # See PS3.5 section A.5
        # when written, the entire dataset following
        #     the file metadata was prepared the normal way,
        #     then "deflate" compression applied.
        #  All that is needed here is to decompress and then
        #     use as normal in a file-like object
        zipped = fileobj.read()
        name = getattr(fileobj, "name", None)

        # -MAX_WBITS part is from comp.lang.python answer:
        # groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
        unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
        buffer = DicomBytesIO(unzipped)
        buffer.name = name
        fileobj = cast(BinaryIO, buffer)  # a file-like object
        is_implicit_VR = False
    elif transfer_syntax in pydicom.uid.PrivateTransferSyntaxes:
        # Replace with the registered UID as it has the encoding information
        index = pydicom.uid.PrivateTransferSyntaxes.index(transfer_syntax)
        transfer_syntax = pydicom.uid.PrivateTransferSyntaxes[index]
        is_implicit_VR = transfer_syntax.is_implicit_VR
        is_little_endian = transfer_syntax.is_little_endian
    else:
        # Any other syntax should be Explicit VR Little Endian,
        #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE
        #        by Standard PS 3.5-2008 A.4 (p63)
        is_implicit_VR = False

    # Try and decode the dataset
    #   By this point we should be at the start of the dataset and have
    #   the transfer syntax (whether read from the file meta or guessed at)
    try:
        dataset = read_dataset(
            fileobj,
            is_implicit_VR,
            is_little_endian,
            stop_when=stop_when,
            defer_size=defer_size,
            specific_tags=specific_tags,
        )
    except EOFError:
        if config.settings.reading_validation_mode == config.RAISE:
            raise
        # warning already logged in read_dataset

    # Add the command set elements to the dataset (if any)
    if command_set:
        dataset.update(command_set)

    ds = FileDataset(
        fileobj,
        dataset,
        preamble,
        file_meta,
        is_implicit_VR,
        is_little_endian,
    )
    # save the originally read transfer syntax properties in the dataset
    ds.set_original_encoding(is_implicit_VR, is_little_endian, dataset._character_set)
    return ds


def dcmread(
    fp: PathType | BinaryIO | ReadableBuffer,
    defer_size: str | int | float | None = None,
    stop_before_pixels: bool = False,
    force: bool = False,
    specific_tags: TagListType | None = None,
) -> FileDataset:
    """Read and parse a DICOM dataset stored in the DICOM File Format.

    Read a DICOM dataset stored in accordance with the :dcm:`DICOM File
    Format <part10/chapter_7.html>`. If the dataset is not stored in
    accordance with the File Format (i.e. the preamble and prefix are missing,
    there are missing required Type 1 *File Meta Information Group* elements
    or the entire *File Meta Information* is missing) then you will have to
    set `force` to ``True``.

    Examples
    --------
    Read and return a dataset stored in accordance with the DICOM File Format:

    >>> ds = pydicom.dcmread("CT_small.dcm")
    >>> ds.PatientName

    Read and return a dataset not in accordance with the DICOM File Format:

    >>> ds = pydicom.dcmread("rtplan.dcm", force=True)
    >>> ds.PatientName

    Use within a context manager:

    >>> with pydicom.dcmread("rtplan.dcm") as ds:
    ...     ds.PatientName

    Parameters
    ----------
    fp : str, PathLike, file-like or readable buffer
        A file-like object, a string containing the file name or the
        path to the file or a buffer-like object. The buffer-like object must
        have ``seek()``, ``read()`` and ``tell()`` methods and the caller is
        responsible for closing it (if required).
    defer_size : int, str or float, optional
        If not used then all elements are read into memory. If specified,
        then if a data element's stored value is larger than `defer_size`, the
        value is not read into memory until it is accessed in code. Should be
        the number of bytes to be read as :class:`int` or as a :class:`str`
        with units, e.g. ``'512 KB'``, ``'2 MB'``.
    stop_before_pixels : bool, optional
        If ``False`` (default), the full file will be read and parsed. Set
        ``True`` to stop before reading (7FE0,0010) *Pixel Data* (and all
        subsequent elements).
    force : bool, optional
        If ``False`` (default), raises an
        :class:`~pydicom.errors.InvalidDicomError` if the file is
        missing the *File Meta Information* header. Set to ``True`` to force
        reading even if no *File Meta Information* header is found.
    specific_tags : list of (int or str or 2-tuple of int), optional
        If used the only the supplied tags will be returned. The supplied
        elements can be tags or keywords. Note that the element (0008,0005)
        *Specific Character Set* is always returned if present - this ensures
        correct decoding of returned text values.

    Returns
    -------
    FileDataset
        An instance of :class:`~pydicom.dataset.FileDataset` that represents
        a parsed DICOM file.

    Raises
    ------
    InvalidDicomError
        If `force` is ``False`` and the file is not a valid DICOM file.
    TypeError
        If `fp` is ``None`` or of an unsupported type.

    See Also
    --------
    pydicom.dataset.FileDataset
        Data class that is returned.
    pydicom.filereader.read_partial
        Only read part of a DICOM file, stopping on given conditions.
    """
    # Open file if not already a file object
    caller_owns_file = True
    fp = path_from_pathlike(fp)
    if isinstance(fp, str):
        # caller provided a file name; we own the file handle
        caller_owns_file = False
        logger.debug(f"Reading file '{fp}'")
        fp = open(fp, "rb")
    elif (
        fp is None
        or not hasattr(fp, "read")
        or not hasattr(fp, "seek")
        or not hasattr(fp, "tell")
    ):
        raise TypeError(
            "dcmread: Expected a file path, file-like or readable buffer, "
            f"but got {type(fp).__name__}"
        )

    if config.debugging:
        logger.debug("\n" + "-" * 80)
        logger.debug("Call to dcmread()")
        logger.debug(
            f"filename: {getattr(fp, 'name', '<none>')}, defer_size={defer_size}, "
            f"stop_before_pixels={stop_before_pixels}, force={force}, "
            f"specific_tags={specific_tags}"
        )
        if caller_owns_file:
            logger.debug("Caller passed file object")
        else:
            logger.debug("Caller passed file name")
        logger.debug("-" * 80)

    if specific_tags:
        specific_tags = [Tag(t) for t in specific_tags]

    specific_tags = cast(list[BaseTag | int] | None, specific_tags)

    # Iterate through all items and store them --include file meta if present
    stop_when = None
    if stop_before_pixels:
        stop_when = _at_pixel_data
    try:
        dataset = read_partial(
            fp,
            stop_when,
            defer_size=size_in_bytes(defer_size),
            force=force,
            specific_tags=specific_tags,
        )
    finally:
        if not caller_owns_file:
            fp.close()
    # XXX need to store transfer syntax etc.
    return dataset


def data_element_offset_to_value(is_implicit_VR: bool, VR: str | None) -> int:
    """Return number of bytes from start of data element to start of value"""
    if is_implicit_VR:
        return 8  # tag of 4 plus 4-byte length

    if cast(str, VR) in EXPLICIT_VR_LENGTH_32:
        return 12  # tag 4 + 2 VR + 2 reserved + 4 length

    return 8  # tag 4 + 2 VR + 2 length


def read_deferred_data_element(
    fileobj_type: Any,
    filename_or_obj: PathType | BinaryIO,
    timestamp: float | None,
    raw_data_elem: RawDataElement,
) -> RawDataElement:
    """Read the previously deferred value from the file into memory
    and return a raw data element.

    .. note:

        This is called internally by pydicom and will normally not be
        needed in user code.

    Parameters
    ----------
    fileobj_type : type
        The type of the original file object.
    filename_or_obj : str or file-like
        The filename of the original file if one exists, or the file-like
        object where the data element persists.
    timestamp : float or None
        The time (as given by stat.st_mtime) the original file has been
        read, if not a file-like.
    raw_data_elem : dataelem.RawDataElement
        The raw data element with no value set.

    Returns
    -------
    dataelem.RawDataElement
        The data element with the value set.

    Raises
    ------
    OSError
        If `filename_or_obj` is ``None``.
    OSError
        If `filename_or_obj` is a filename and the corresponding file does
        not exist.
    ValueError
        If the VR or tag of `raw_data_elem` does not match the read value.
    """
    if config.debugging:
        logger.debug(f"Reading deferred element {raw_data_elem.tag}")
    # If it wasn't read from a file, then return an error
    if filename_or_obj is None:
        raise OSError("Deferred read -- original filename not stored. Cannot re-open")

    # Check that the file is the same as when originally read
    is_filename = isinstance(filename_or_obj, str)
    if isinstance(filename_or_obj, str):
        if not os.path.exists(filename_or_obj):
            raise OSError(
                f"Deferred read -- original file {filename_or_obj} is missing"
            )

        if timestamp is not None:
            statinfo = os.stat(filename_or_obj)
            if statinfo.st_mtime != timestamp:
                warn_and_log(
                    "Deferred read warning -- file modification time has changed"
                )

    # Open the file, position to the right place
    fp = fileobj_type(filename_or_obj, "rb") if is_filename else filename_or_obj
    is_implicit_VR = raw_data_elem.is_implicit_VR
    is_little_endian = raw_data_elem.is_little_endian
    offset = data_element_offset_to_value(is_implicit_VR, raw_data_elem.VR)
    # Seek back to the start of the deferred element
    fp.seek(raw_data_elem.value_tell - offset)
    elem_gen = data_element_generator(
        fp, is_implicit_VR, is_little_endian, defer_size=None
    )

    # Read the data element and check matches what was stored before
    # The first element out of the iterator should be the same type as the
    #   the deferred element == RawDataElement
    elem = cast(RawDataElement, next(elem_gen))
    if is_filename:
        fp.close()
    if elem.VR != raw_data_elem.VR:
        raise ValueError(
            f"Deferred read VR {elem.VR} does not match original {raw_data_elem.VR}"
        )

    if elem.tag != raw_data_elem.tag:
        raise ValueError(
            f"Deferred read tag {elem.tag!r} does not match "
            f"original {raw_data_elem.tag!r}"
        )

    # Everything is ok, now this object should act like usual DataElement
    return elem
