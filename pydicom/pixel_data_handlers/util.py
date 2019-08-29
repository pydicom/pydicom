# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Utility functions used in the pixel data handlers."""

from struct import unpack, pack
from sys import byteorder
import warnings

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.data import get_palette_files
from pydicom.uid import UID


def apply_color_lut(arr, ds=None, palette=None):
    """Apply a color palette lookup table to `arr`.

    Requirements common to supported modules:

    +----------------------------------------------------------------+----------+
    | Element                                                        |          |
    +-------------+-------------------------------------------+------+          |
    | Tag         | Keyword                                   | Type |          |
    +=============+===========================================+======+==========+
    | (0028,1101) | RedPaletteColorLookupTableDescriptor      | 1    | Required |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1102) | BluePaletteColorLookupTableDescriptor     | 1    | Required |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1103) | GreenPaletteColorLookupTableDescriptor    | 1    | Required |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1201) | RedPaletteColorLookupTableData            | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1202) | BluePaletteColorLookupTableData           | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1203) | GreenPaletteColorLookupTableData          | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1204) | AlphaPaletteColorLookupTableData          | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1221) | SegmentedRedPaletteColorLookupTableData   | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1222) | SegmentedGreenPaletteColorLookupTableData | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1223) | SegmentedBluePaletteColorLookupTableData  | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+
    | (0028,1224) | SegmentedAlphaPaletteColorLookupTableData | 1C   | Optional |
    +-------------+-------------------------------------------+------+----------+

    If (0028,1201-3) *Palette Color Lookup Table Data* are missing
    then (0028-1221-3) *Segmented Palette Color Lookup Table Data* must be
    present and vice versa. The presence of (0028,1204) *Alpha Palette Color
    Lookup Table Data* or (0028,1224) *Segmented Palette Color Lookup Table
    Data* is optional.

    Requirements for use with the :dcm:`Image Pixel Module
    <part03/sect_C.7.6.3.html>` or :dcm:`Palette Color LUT Module
    <part03/sect_C.7.9.html>`:

    +------------------------------------------------+---------------+----------+
    | Element                                        | Supported     |          |
    +-------------+---------------------------+------+ values        |          |
    | Tag         | Keyword                   | Type |               |          |
    +=============+===========================+======+===============+==========+
    | (0028,0004) | PhotometricInterpretation | 1    | PALETTE COLOR | Required |
    +-------------+---------------------------+------+---------------+----------+
    | (0028,0100) | BitsAllocated             | 1    | 8, 16         | Required |
    +-------------+---------------------------+------+---------------+----------+

    Requirements for use with the :dcm:`Supplemental Palette Color LUT Module
    <part03/sect_C.7.6.19.html>`:

    +------------------------------------------------+-------------+----------+
    | Element                                        | Supported   |          |
    +-------------+---------------------------+------+ values      |          |
    | Tag         | Keyword                   | Type |             |          |
    +=============+===========================+======+=============+==========+
    | (0008,9205) | PixelPresentation         | 1    | COLOR       | Required |
    +-------------+---------------------------+------+-------------+----------+
    | (0028,0100) | BitsAllocated             | 1    | 8, 16       | Required |
    +-------------+---------------------------+------+-------------+----------+

    Use of this function with the :dcm:`Enhanced Palette Color Lookup Table
    Module<part03/sect_C.7.6.23.html>` is not supported.

    Parameters
    ----------
    arr : numpy.ndarray
        The pixel data to apply the color palette to.
    ds : dataset.Dataset, optional
        Required if `palette` is not supplied. A
        :class:`~pydicom.dataset.Dataset` containing a suitable
        :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` or
        :dcm:`Palette Color Lookup Table<part03/sect_C.7.9.html>` Module.
    palette : str or uid.UID, optional
        Required if `ds` is not supplied. The name of one of the
        :dcm:`well-known<part06/chapter_B.html>` color palettes defined by the
        DICOM Standard. One of: ``'HOT_IRON'``, ``'PET'``,
        ``'HOT_METAL_BLUE'``, ``'PET_20_STEP'``, ``'SPRING'``, ``'SUMMER'``,
         ``'FALL'``, ``'WINTER'`` or the corresponding well-known (0008,0018)
         *SOP Instance UID*.

    Returns
    -------
    numpy.ndarray
        The RGB pixel data.

    References
    ----------

    * :dcm:`Image Pixel Module<part03/sect_C.7.6.3.html>`
    * :dcm:`Supplemental Palette Color LUT Module<part03/sect_C.7.6.19.html>`
    * :dcm:`Enhanced Palette Color LUT Module<part03/sect_C.7.6.23.html>`
    * :dcm:`Palette Colour LUT Module<part03/sect_C.7.9.html>`
    * :dcm:`Supplemental Palette Color LUTs
      <part03/sect_C.8.16.2.html#sect_C.8.16.2.1.1.1>`
    """
    # Note: input value (IV) is either the Palette Color LUT input value from
    #   Enhanced Palette Color Lookup Table Sequence (0028,140B) or if that
    #   is missing, the stored pixel value

    if not ds and not palette:
        raise ValueError("Either 'ds' or 'palette' is required")

    if palette:
        # Well-known palettes are all 8-bits per entry
        datasets = {
            '1.2.840.10008.1.5.1': 'hotiron.dcm',
            '1.2.840.10008.1.5.2': 'pet.dcm',
            '1.2.840.10008.1.5.3': 'hotmetalblue.dcm',
            '1.2.840.10008.1.5.4': 'pet20step.dcm',
            '1.2.840.10008.1.5.5': 'spring.dcm',
            '1.2.840.10008.1.5.6': 'summer.dcm',
            '1.2.840.10008.1.5.7': 'fall.dcm',
            '1.2.840.10008.1.5.8': 'winter.dcm',
        }
        if not UID(palette).is_valid:
            try:
                uids = {
                    'HOT_IRON': '1.2.840.10008.1.5.1',
                    'PET': '1.2.840.10008.1.5.2',
                    'HOT_METAL_BLUE': '1.2.840.10008.1.5.3',
                    'PET_20_STEP': '1.2.840.10008.1.5.4',
                    'SPRING': '1.2.840.10008.1.5.5',
                    'SUMMER': '1.2.840.10008.1.5.6',
                    'FALL': '1.2.840.10008.1.5.8',
                    'WINTER': '1.2.840.10008.1.5.7',
                }
                palette = uids[palette]
            except KeyError:
                raise ValueError("Unknown palette '{}'".format(palette))

        try:
            from pydicom import dcmread
            fname = datasets[palette]
            ds = dcmread(get_palette_files(fname)[0])
        except KeyError:
            raise ValueError("Unknown palette '{}'".format(palette))

    # TODO: Check that the bit depth of `arr` is suitable
    #if arr.dtype != 'uint8':
    #    raise ValueError(
    #        "The bit depth of 'arr' does not match that of the "
    #    )

    # C.8.16.2.1.1.1: Supplemental Palette Color LUT
    is_supplemental = False
    px_presentation = getattr(ds, 'PixelPresentation', None)
    if px_presentation == 'MIXED':
        raise ValueError(
            "A '(0008,9205) Pixel Presentation' value of 'MIXED' is not "
            "currently supported"
        )
    elif px_presentation == 'COLOR':
        is_supplemental = True

    # All channels are supposed to be identical
    lut_desc = ds.RedPaletteColorLookupTableDescriptor

    # A value of 0 = 2^16 entries
    nr_entries = lut_desc[0] or 2**16
    first_map = lut_desc[1]
    # Nominal bit depth - actual bit depth may be smaller
    nominal_depth = lut_desc[2]
    print('Entries:', nr_entries)
    print('First mapping:', first_map)
    print('Nominal bits per entry:', nominal_depth)
    entry_dtype = np.dtype('uint{:.0f}'.format(nominal_depth))

    if 'RedPaletteColorLookupTableData' in ds:
        # LUT Data is described by PS3.3, C.7.6.3.1.6
        r_data = ds.RedPaletteColorLookupTableData
        g_data = ds.GreenPaletteColorLookupTableData
        b_data = ds.BluePaletteColorLookupTableData
        a_data = getattr(ds, 'AlphaPaletteColorLookupTableData', None)

        actual_depth = len(r_data) / nr_entries * 8

        r_data = np.frombuffer(r_data, dtype=entry_dtype)
        g_data = np.frombuffer(g_data, dtype=entry_dtype)
        b_data = np.frombuffer(b_data, dtype=entry_dtype)
        if a_data:
            a_data = np.frombuffer(a_data, dtype=entry_dtype)
    elif 'SegmentedRedPaletteColorLookupTableData' in ds:
        # Segmented LUT Data is described by PS3.3, C.7.9.2
        endianness = '<' if ds.is_little_endian else '>'
        fmt = 'B' if nominal_depth // 8 == 1 else 'H'
        actual_depth = nominal_depth

        # Returns the LUT data as a list
        len_r = len(ds.SegmentedRedPaletteColorLookupTableData)
        r_data = _expand_segmented_lut(
            unpack(
                endianness + str(len_r) + fmt,
                ds.SegmentedRedPaletteColorLookupTableData
            ),
            endianness + fmt
        )
        r_data = np.asarray(r_data, dtype=entry_dtype)

        len_g = len(ds.SegmentedGreenPaletteColorLookupTableData)
        g_data = _expand_segmented_lut(
            unpack(
                endianness + str(len_g) + fmt,
                ds.SegmentedGreenPaletteColorLookupTableData
            ),
            endianness + fmt
        )
        g_data = np.asarray(g_data, dtype=entry_dtype)

        len_b = len(ds.SegmentedBluePaletteColorLookupTableData)
        b_data = _expand_segmented_lut(
            unpack(
                endianness + str(len_b) + fmt,
                ds.SegmentedBluePaletteColorLookupTableData
            ),
            endianness + fmt
        )
        b_data = np.asarray(b_data, dtype=entry_dtype)

        if hasattr(ds, 'SegmentedAlphaPaletteColorLookupTableData'):
            len_a = len(ds.SegmentedAlphaPaletteColorLookupTableData)
            a_data = _expand_segmented_lut(
                unpack(
                    endianness + str(len_a) + fmt,
                    ds.SegmentedAlphaPaletteColorLookupTableData
                ),
                endianness + fmt
            )
            a_data = np.asarray(a_data, dtype=entry_dtype)
        else:
            a_data = None

    # Some implementations have 8-bit data in 16-bit allocations
    if actual_depth not in [8, 16]:
        raise ValueError(
            "The bit depth of the LUT data '{}' is invalid (only 8 or 16 "
            "bits per entry allowed)".format(actual_depth)
        )

    luts = [r_data, g_data, b_data] + ([a_data] if a_data else [])
    if False in [len(item) == len(luts[0]) for item in luts]:
        raise ValueError("LUT data must be the same length")

    # Need to rescale if 8-bit data in 16-bit entries
    if actual_depth == 8 and nominal_depth == 16:
        # In-place modification
        [np.multiply(item, 257, out=item) for item in luts]

    if first_map == 0:
        # IVs > than number of entries get set to last entry
        clipped_iv = np.clip(arr, 0, nr_entries - 1)
    else:
        # If supplemental we will have pixels with no LUT mapping, so use NaN
        clipped_iv = np.full_like(arr, np.nan)

        # IVs >= `first_map` are mapped by the Palette Color LUTs
        colour_pixels = arr >= first_map
        clipped_iv[colour_pixels] = arr[colour_pixels] - first_map
        if not is_supplemental:
            # IVs < `first_map` get set to first LUT entry
            clipped_iv[~colour_pixels] = 0

        # IVs > than number of entries get set to last entry
        np.clip(clipped_iv, 0, nr_entries - 1, out=clipped_iv)

    out_shape = list(arr.shape) + [len(luts)]
    out = np.full(out_shape, np.nan, dtype=entry_dtype)
    for ii, lut in enumerate(luts):
        out[..., ii] = lut[clipped_iv]

    return out


def convert_color_space(arr, current, desired):
    """Convert the image(s) in `arr` from one color space to another.

    Parameters
    ----------
    arr : numpy.ndarray
        The image(s) as a :class:`numpy.ndarray` with
        :attr:`~numpy.ndarray.shape` (frames, rows, columns, planes)
        or (rows, columns, planes).
    current : str
        The current color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of ``'RGB'``, ``'YBR_FULL'``,
        ``'YBR_FULL_422'``.
    desired : str
        The desired color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of ``'RGB'``, ``'YBR_FULL'``,
        ``'YBR_FULL_422'``.

    Returns
    -------
    numpy.ndarray
        The image(s) converted to the desired color space.

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1.2<part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>`
    * ISO/IEC 10918-5:2012 (`ITU T.871
      <https://www.ijg.org/files/T-REC-T.871-201105-I!!PDF-E.pdf>`_),
      Section 7
    """
    def _no_change(arr):
        return arr

    _converters = {
        'YBR_FULL_422': {
            'YBR_FULL_422': _no_change,
            'YBR_FULL': _no_change,
            'RGB': _convert_YBR_FULL_to_RGB,
        },
        'YBR_FULL': {
            'YBR_FULL': _no_change,
            'YBR_FULL_422': _no_change,
            'RGB': _convert_YBR_FULL_to_RGB,
        },
        'RGB': {
            'RGB': _no_change,
            'YBR_FULL': _convert_RGB_to_YBR_FULL,
            'YBR_FULL_422': _convert_RGB_to_YBR_FULL,
        }
    }
    try:
        converter = _converters[current][desired]
    except KeyError:
        raise NotImplementedError(
            "Conversion from {0} to {1} is not supported."
            .format(current, desired)
        )

    return converter(arr)


def _convert_RGB_to_YBR_FULL(arr):
    """Return an ndarray converted from RGB to YBR_FULL color space.

    Parameters
    ----------
    arr : numpy.ndarray
        An ndarray of an 8-bit per channel images in RGB color space.

    Returns
    -------
    numpy.ndarray
        The array in YBR_FULL color space.

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1.2<part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>`
    * ISO/IEC 10918-5:2012 (`ITU T.871
      <https://www.ijg.org/files/T-REC-T.871-201105-I!!PDF-E.pdf>`_),
      Section 7
    """
    orig_dtype = arr.dtype

    rgb_to_ybr = np.asarray(
        [[+0.299, -0.299 / 1.772, +0.701 / 1.402],
         [+0.587, -0.587 / 1.772, -0.587 / 1.402],
         [+0.114, +0.886 / 1.772, -0.114 / 1.402]],
        dtype=np.float
    )

    arr = np.dot(arr, rgb_to_ybr)
    arr += [0.5, 128.5, 128.5]
    # Round(x) -> floor of (arr + 0.5) : 0.5 added in previous step
    arr = np.floor(arr)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    arr = np.clip(arr, 0, 255)

    return arr.astype(orig_dtype)


def _convert_YBR_FULL_to_RGB(arr):
    """Return an ndarray converted from YBR_FULL to RGB color space.

    Parameters
    ----------
    arr : numpy.ndarray
        An ndarray of an 8-bit per channel images in YBR_FULL color space.

    Returns
    -------
    numpy.ndarray
        The array in RGB color space.

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1.2<part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>`
    * ISO/IEC 10918-5:2012, Section 7
    """
    orig_dtype = arr.dtype

    ybr_to_rgb = np.asarray(
        [[1.000, 1.000, 1.000],
         [0.000, -0.114 * 1.772 / 0.587, 1.772],
         [1.402, -0.299 * 1.402 / 0.587, 0.000]],
        dtype=np.float
    )

    arr = arr.astype(np.float)
    arr -= [0, 128, 128]
    arr = np.dot(arr, ybr_to_rgb)

    # Round(x) -> floor of (arr + 0.5)
    arr = np.floor(arr + 0.5)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    arr = np.clip(arr, 0, 255)

    return arr.astype(orig_dtype)


def dtype_corrected_for_endianness(is_little_endian, numpy_dtype):
    """Return a :class:`numpy.dtype` corrected for system and :class:`Dataset`
    endianness.

    Parameters
    ----------
    is_little_endian : bool
        The endianess of the affected :class:`~pydicom.dataset.Dataset`.
    numpy_dtype : numpy.dtype
        The numpy data type used for the *Pixel Data* without considering
        endianess.

    Raises
    ------
    ValueError
        If `is_little_endian` is ``None``, e.g. not initialized.

    Returns
    -------
    numpy.dtype
        The numpy data type used for the *Pixel Data* without considering
        endianess.
    """
    if is_little_endian is None:
        raise ValueError("Dataset attribute 'is_little_endian' "
                         "has to be set before writing the dataset")

    if is_little_endian != (byteorder == 'little'):
        return numpy_dtype.newbyteorder('S')

    return numpy_dtype


def _expand_segmented_lut(data, fmt, nr_segments=None, last_value=None):
    """Return a list containing the expanded lookup table data.

    Parameters
    ----------
    data : tuple of int
        The decoded segmented palette lookup table data. May be padded by a
        trailing null.
    fmt : str
        The format of the data, one of `'H'`, `'<B'`, `'>B'`.
    nr_segments : int, optional
        Expand at most `nr_segments` from the data. Should be used when
        the opcode is ``2`` (indirect). If used then `last_value` should also
        be used.
    last_value : int, optional
        The previous value in the expanded lookup table. Should be used when
        the opcode is ``2`` (indirect). If used then `nr_segments` should also
        be used.

    Returns
    -------
    list of int
        The reconstructed lookup table data.

    References
    ----------

    * DICOM Standard, Part 3, Annex C.7.9
    """
    # Indirect segment byte offset is dependent on endianness for 8-bit
    # Little endian: e.g. 0x0302 0x0100, big endian, e.g. 0x0203 0x0001
    indirect_ii = [3, 2, 1, 0] if '<' in fmt else [2, 3, 0, 1]

    lut = []
    offset = 0
    segments_read = 0
    # Use `offset + 1` to account for possible trailing null
    #   can do this because all segment types are longer than 2
    while offset + 1 < len(data):
        opcode = data[offset]
        length = data[offset + 1]
        offset += 2

        if opcode == 0:
            # C.7.9.2.1: Discrete segment
            lut.extend(data[offset:offset + length])
            offset += length
        elif opcode == 1:
            # C.7.9.2.2: Linear segment
            if lut:
                y0 = lut[-1]
            elif last_value:
                # Indirect segment with linear segment at 0th offset
                y0 = last_value
            else:
                raise ValueError(
                    "Error expanding a segmented palette color lookup table: "
                    "the first segment cannot be a linear segment"
                )

            y1 = data[offset]
            offset += 1

            if y0 == y1:
                lut.extend([y1] * length)
            else:
                step = (y1 - y0) / length
                vals = np.floor(np.arange(y0 + step, y1 + step, step))
                lut.extend([int(vv) for vv in vals])
        elif opcode == 2:
            # C.7.9.2.3: Indirect segment
            if 'B' in fmt:
                # 8-bit segment entries
                ii = [data[offset + vv] for vv in indirect_ii]
                byte_offset = (ii[0] << 8 | ii[1]) << 16 | (ii[2] << 8 | ii[3])
                offset += 4
            else:
                # 16-bit segment entries
                byte_offset = data[offset + 1] << 16 | data[offset]
                offset += 2

            if not lut:
                raise ValueError(
                    "Error expanding a segmented palette color lookup table: "
                    "the first segment cannot be an indirect segment"
                )

            lut.extend(
                _expand_segmented_lut(data[byte_offset:], fmt, length, lut[-1])
            )
        else:
            raise ValueError(
                "Error expanding a segmented palette lookup table: "
                "unknown segment type '{}'".format(opcode)
            )

        segments_read += 1
        if segments_read == nr_segments:
            return lut

    return lut


def get_expected_length(ds, unit='bytes'):
    """Return the expected length (in terms of bytes or pixels) of the *Pixel
    Data*.

    +------------------------------------------+-------------+
    | Element                                  | Required or |
    +-------------+---------------------+------+ optional    |
    | Tag         | Keyword             | Type |             |
    +=============+=====================+======+=============+
    | (0028,0002) | SamplesPerPixel     | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0008) | NumberOfFrames      | 1C   | Optional    |
    +-------------+---------------------+------+-------------+
    | (0028,0010) | Rows                | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0011) | Columns             | 1    | Required    |
    +-------------+---------------------+------+-------------+
    | (0028,0100) | BitsAllocated       | 1    | Required    |
    +-------------+---------------------+------+-------------+

    Parameters
    ----------
    ds : Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image Pixel module
        and *Pixel Data*.
    unit : str, optional
        If ``'bytes'`` then returns the expected length of the *Pixel Data* in
        whole bytes and NOT including an odd length trailing NULL padding
        byte. If ``'pixels'`` then returns the expected length of the *Pixel
        Data* in terms of the total number of pixels (default ``'bytes'``).

    Returns
    -------
    int
        The expected length of the *Pixel Data* in either whole bytes or
        pixels, excluding the NULL trailing padding byte for odd length data.
    """
    length = ds.Rows * ds.Columns * ds.SamplesPerPixel
    length *= getattr(ds, 'NumberOfFrames', 1)

    if unit == 'pixels':
        return length

    # Correct for the number of bytes per pixel
    bits_allocated = ds.BitsAllocated
    if bits_allocated == 1:
        # Determine the nearest whole number of bytes needed to contain
        #   1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits, which
        #   are packed into 12.5 -> 13 bytes
        length = length // 8 + (length % 8 > 0)
    else:
        length *= bits_allocated // 8

    return length


def pixel_dtype(ds):
    """Return a :class:`numpy.dtype` for the *Pixel Data* in `ds`.

    Suitable for use with IODs containing the Image Pixel module.

    +------------------------------------------+--------------+
    | Element                                  | Supported    |
    +-------------+---------------------+------+ values       |
    | Tag         | Keyword             | Type |              |
    +=============+=====================+======+==============+
    | (0028,0101) | BitsAllocated       | 1    | 1, 8, 16, 32 |
    +-------------+---------------------+------+--------------+
    | (0028,0103) | PixelRepresentation | 1    | 0, 1         |
    +-------------+---------------------+------+--------------+

    Parameters
    ----------
    ds : Dataset
        The :class:`~pydicom.dataset.Dataset` containing the *Pixel Data* you
        wish to get the data type for.

    Returns
    -------
    numpy.dtype
        A :class:`numpy.dtype` suitable for containing the *Pixel Data*.

    Raises
    ------
    NotImplementedError
        If the pixel data is of a type that isn't supported by either numpy
        or *pydicom*.
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to determine the dtype.")

    if ds.is_little_endian is None:
        ds.is_little_endian = ds.file_meta.TransferSyntaxUID.is_little_endian

    # (0028,0103) Pixel Representation, US, 1
    #   Data representation of the pixel samples
    #   0x0000 - unsigned int
    #   0x0001 - 2's complement (signed int)
    pixel_repr = ds.PixelRepresentation
    if pixel_repr == 0:
        dtype_str = 'uint'
    elif pixel_repr == 1:
        dtype_str = 'int'
    else:
        raise ValueError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0103) Pixel "
            "Representation' is invalid".format(pixel_repr)
        )

    # (0028,0100) Bits Allocated, US, 1
    #   The number of bits allocated for each pixel sample
    #   PS3.5 8.1.1: Bits Allocated shall either be 1 or a multiple of 8
    #   For bit packed data we use uint8
    bits_allocated = ds.BitsAllocated
    if bits_allocated == 1:
        dtype_str = 'uint8'
    elif bits_allocated > 0 and bits_allocated % 8 == 0:
        dtype_str += str(bits_allocated)
    else:
        raise ValueError(
            "Unable to determine the data type to use to contain the "
            "Pixel Data as a value of '{}' for '(0028,0100) Bits "
            "Allocated' is invalid".format(bits_allocated)
        )

    # Check to see if the dtype is valid for numpy
    try:
        dtype = np.dtype(dtype_str)
    except TypeError:
        raise NotImplementedError(
            "The data type '{}' needed to contain the Pixel Data is not "
            "supported by numpy".format(dtype_str)
        )

    # Correct for endianness of the system vs endianness of the dataset
    if ds.is_little_endian != (byteorder == 'little'):
        # 'S' swap from current to opposite
        dtype = dtype.newbyteorder('S')

    return dtype


def reshape_pixel_array(ds, arr):
    """Return a reshaped :class:`numpy.ndarray` `arr`.

    +------------------------------------------+-----------+----------+
    | Element                                  | Supported |          |
    +-------------+---------------------+------+ values    |          |
    | Tag         | Keyword             | Type |           |          |
    +=============+=====================+======+===========+==========+
    | (0028,0002) | SamplesPerPixel     | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0006) | PlanarConfiguration | 1C   | 0, 1      | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0008) | NumberOfFrames      | 1C   | N > 0     | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0010) | Rows                | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0011) | Columns             | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+

    (0028,0008) *Number of Frames* is required when *Pixel Data* contains
    more than 1 frame. (0028,0006) *Planar Configuration* is required when
    (0028,0002) *Samples per Pixel* is greater than 1. For certain
    compressed transfer syntaxes it is always taken to be either 0 or 1 as
    shown in the table below.

    +---------------------------------------------+-----------------------+
    | Transfer Syntax                             | Planar Configuration  |
    +------------------------+--------------------+                       |
    | UID                    | Name               |                       |
    +========================+====================+=======================+
    | 1.2.840.10008.1.2.4.50 | JPEG Baseline      | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.57 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical   |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.70 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical,  |                       |
    |                        | SV1                |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.80 | JPEG-LS Lossless   | 1                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.81 | JPEG-LS Lossy      | 1                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.90 | JPEG 2000 Lossless | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.91 | JPEG 2000 Lossy    | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.5    | RLE Lossless       | 1                     |
    +------------------------+--------------------+-----------------------+

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image Pixel module
        corresponding to the data in `arr`.
    arr : numpy.ndarray
        The 1D array containing the pixel data.

    Returns
    -------
    numpy.ndarray
        A reshaped array containing the pixel data. The shape of the array
        depends on the contents of the dataset:

        * For single frame, single sample data (rows, columns)
        * For single frame, multi-sample data (rows, columns, planes)
        * For multi-frame, single sample data (frames, rows, columns)
        * For multi-frame, multi-sample data (frames, rows, columns, planes)

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1<part03/sect_C.7.6.3.html#sect_C.7.6.3.1>`
    * DICOM Standard, Part 5, :dcm:`Section 8.2<part05/sect_8.2.html>`
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to reshape the pixel array.")

    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    nr_samples = ds.SamplesPerPixel

    if nr_frames < 1:
        raise ValueError(
            "Unable to reshape the pixel array as a value of {} for "
            "(0028,0008) 'Number of Frames' is invalid."
            .format(nr_frames)
        )

    if nr_samples < 1:
        raise ValueError(
            "Unable to reshape the pixel array as a value of {} for "
            "(0028,0002) 'Samples per Pixel' is invalid."
            .format(nr_samples)
        )

    # Valid values for Planar Configuration are dependent on transfer syntax
    if nr_samples > 1:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        if transfer_syntax in ['1.2.840.10008.1.2.4.50',
                               '1.2.840.10008.1.2.4.57',
                               '1.2.840.10008.1.2.4.70',
                               '1.2.840.10008.1.2.4.90',
                               '1.2.840.10008.1.2.4.91']:
            planar_configuration = 0
        elif transfer_syntax in ['1.2.840.10008.1.2.4.80',
                                 '1.2.840.10008.1.2.4.81',
                                 '1.2.840.10008.1.2.5']:
            planar_configuration = 1
        else:
            planar_configuration = ds.PlanarConfiguration

        if planar_configuration not in [0, 1]:
            raise ValueError(
                "Unable to reshape the pixel array as a value of {} for "
                "(0028,0006) 'Planar Configuration' is invalid."
                .format(planar_configuration)
            )

    if nr_frames > 1:
        # Multi-frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(nr_frames, ds.Rows, ds.Columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(nr_frames, ds.Rows, ds.Columns, nr_samples)
            else:
                arr = arr.reshape(nr_frames, nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(0, 2, 3, 1)
    else:
        # Single frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(ds.Rows, ds.Columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(ds.Rows, ds.Columns, nr_samples)
            else:
                arr = arr.reshape(nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(1, 2, 0)

    return arr
