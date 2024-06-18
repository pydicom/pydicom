# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Pixel data processing functions."""

from struct import unpack, unpack_from
from typing import TYPE_CHECKING, cast
from collections.abc import Iterable

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.data import get_palette_files
from pydicom.misc import warn_and_log
from pydicom.uid import UID
from pydicom.valuerep import VR

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


def apply_color_lut(
    arr: "np.ndarray", ds: "Dataset | None" = None, palette: str | UID | None = None
) -> "np.ndarray":
    """Apply a color palette lookup table to `arr`.

    If (0028,1201-1203) *Palette Color Lookup Table Data* are missing
    then (0028,1221-1223) *Segmented Palette Color Lookup Table Data* must be
    present and vice versa. The presence of (0028,1204) *Alpha Palette Color
    Lookup Table Data* or (0028,1224) *Alpha Segmented Palette Color Lookup
    Table Data* is optional.

    Use of this function with the :dcm:`Enhanced Palette Color Lookup Table
    Module<part03/sect_C.7.6.23.html>` or :dcm:`Supplemental Palette Color LUT
    Module<part03/sect_C.7.6.19.html>` is not currently supported.

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
        The RGB or RGBA pixel data as an array of ``np.uint8`` or ``np.uint16``
        values, depending on the 3rd value of (0028,1201) *Red Palette Color
        Lookup Table Descriptor*.

    References
    ----------

    * :dcm:`Image Pixel Module<part03/sect_C.7.6.3.html>`
    * :dcm:`Supplemental Palette Color LUT Module<part03/sect_C.7.6.19.html>`
    * :dcm:`Enhanced Palette Color LUT Module<part03/sect_C.7.6.23.html>`
    * :dcm:`Palette Colour LUT Module<part03/sect_C.7.9.html>`
    * :dcm:`Supplemental Palette Color LUTs
      <part03/sect_C.8.16.2.html#sect_C.8.16.2.1.1.1>`
    """
    # Note: input value (IV) is the stored pixel value in `arr`
    # LUTs[IV] -> [R, G, B] values at the IV pixel location in `arr`
    if not ds and not palette:
        raise ValueError("Either 'ds' or 'palette' is required")

    if palette:
        # Well-known palettes are all 8-bits per entry
        datasets = {
            "1.2.840.10008.1.5.1": "hotiron.dcm",
            "1.2.840.10008.1.5.2": "pet.dcm",
            "1.2.840.10008.1.5.3": "hotmetalblue.dcm",
            "1.2.840.10008.1.5.4": "pet20step.dcm",
            "1.2.840.10008.1.5.5": "spring.dcm",
            "1.2.840.10008.1.5.6": "summer.dcm",
            "1.2.840.10008.1.5.7": "fall.dcm",
            "1.2.840.10008.1.5.8": "winter.dcm",
        }
        if not UID(palette).is_valid:
            try:
                uids = {
                    "HOT_IRON": "1.2.840.10008.1.5.1",
                    "PET": "1.2.840.10008.1.5.2",
                    "HOT_METAL_BLUE": "1.2.840.10008.1.5.3",
                    "PET_20_STEP": "1.2.840.10008.1.5.4",
                    "SPRING": "1.2.840.10008.1.5.5",
                    "SUMMER": "1.2.840.10008.1.5.6",
                    "FALL": "1.2.840.10008.1.5.8",
                    "WINTER": "1.2.840.10008.1.5.7",
                }
                palette = uids[palette]
            except KeyError:
                raise ValueError(f"Unknown palette '{palette}'")

        try:
            from pydicom import dcmread

            fname = datasets[palette]
            ds = dcmread(get_palette_files(fname)[0])
        except KeyError:
            raise ValueError(f"Unknown palette '{palette}'")

    ds = cast("Dataset", ds)

    # C.8.16.2.1.1.1: Supplemental Palette Color LUT
    # TODO: Requires greyscale visualisation pipeline
    if getattr(ds, "PixelPresentation", None) in ["MIXED", "COLOR"]:
        raise ValueError(
            "Use of this function with the Supplemental Palette Color Lookup "
            "Table Module is not currently supported"
        )

    if "RedPaletteColorLookupTableDescriptor" not in ds:
        raise ValueError("No suitable Palette Color Lookup Table Module found")

    # All channels are supposed to be identical
    lut_desc = cast(list[int], ds.RedPaletteColorLookupTableDescriptor)
    # A value of 0 = 2^16 entries
    nr_entries = lut_desc[0] or 2**16

    # May be negative if Pixel Representation is 1
    first_map = lut_desc[1]
    # Actual bit depth may be larger (8 bit entries in 16 bits allocated)
    nominal_depth = lut_desc[2]
    dtype = np.dtype(f"uint{nominal_depth:.0f}")

    luts = []
    if "RedPaletteColorLookupTableData" in ds:
        # LUT Data is described by PS3.3, C.7.6.3.1.6
        r_lut = cast(bytes, ds.RedPaletteColorLookupTableData)
        g_lut = cast(bytes, ds.GreenPaletteColorLookupTableData)
        b_lut = cast(bytes, ds.BluePaletteColorLookupTableData)
        a_lut = cast(
            bytes | None, getattr(ds, "AlphaPaletteColorLookupTableData", None)
        )

        actual_depth = len(r_lut) / nr_entries * 8
        dtype = np.dtype(f"uint{actual_depth:.0f}")

        for lut_bytes in [ii for ii in [r_lut, g_lut, b_lut, a_lut] if ii]:
            luts.append(np.frombuffer(lut_bytes, dtype=dtype))
    elif "SegmentedRedPaletteColorLookupTableData" in ds:
        # Segmented LUT Data is described by PS3.3, C.7.9.2
        r_lut = cast(bytes, ds.SegmentedRedPaletteColorLookupTableData)
        g_lut = cast(bytes, ds.SegmentedGreenPaletteColorLookupTableData)
        b_lut = cast(bytes, ds.SegmentedBluePaletteColorLookupTableData)
        a_lut = cast(
            bytes | None, getattr(ds, "SegmentedAlphaPaletteColorLookupTableData", None)
        )

        if hasattr(ds, "file_meta"):
            is_little_endian = ds.file_meta._tsyntax_encoding[1]
        else:
            is_little_endian = ds.original_encoding[1]

        if is_little_endian is None:
            raise AttributeError(
                "Unable to determine the endianness of the dataset, please set "
                "an appropriate Transfer Syntax UID in "
                f"'{type(ds).__name__}.file_meta'"
            )

        endianness = "><"[is_little_endian]
        byte_depth = nominal_depth // 8
        fmt = "B" if byte_depth == 1 else "H"
        actual_depth = nominal_depth

        for seg in [ii for ii in [r_lut, g_lut, b_lut, a_lut] if ii]:
            len_seg = len(seg) // byte_depth
            s_fmt = f"{endianness}{len_seg}{fmt}"
            lut_ints = _expand_segmented_lut(unpack(s_fmt, seg), s_fmt)
            luts.append(np.asarray(lut_ints, dtype=dtype))
    else:
        raise ValueError("No suitable Palette Color Lookup Table Module found")

    if actual_depth not in [8, 16]:
        raise ValueError(
            f"The bit depth of the LUT data '{actual_depth:.1f}' "
            "is invalid (only 8 or 16 bits per entry allowed)"
        )

    lut_lengths = [len(ii) for ii in luts]
    if not all(ii == lut_lengths[0] for ii in lut_lengths[1:]):
        raise ValueError("LUT data must be the same length")

    # IVs < `first_map` get set to first LUT entry (i.e. index 0)
    clipped_iv = np.zeros(arr.shape, dtype=dtype)
    # IVs >= `first_map` are mapped by the Palette Color LUTs
    # `first_map` may be negative, positive or 0
    mapped_pixels = arr >= first_map
    clipped_iv[mapped_pixels] = arr[mapped_pixels] - np.int32(first_map)
    # IVs > number of entries get set to last entry
    np.clip(clipped_iv, 0, nr_entries - 1, out=clipped_iv)

    # Output array may be RGB or RGBA
    out = np.empty(list(arr.shape) + [len(luts)], dtype=dtype)
    for ii, lut in enumerate(luts):
        out[..., ii] = lut[clipped_iv]

    return out


def apply_modality_lut(arr: "np.ndarray", ds: "Dataset") -> "np.ndarray":
    """Apply a modality lookup table or rescale operation to `arr`.

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`~numpy.ndarray` to apply the modality LUT or rescale
        operation to.
    ds : dataset.Dataset
        A dataset containing a :dcm:`Modality LUT Module
        <part03/sect_C.11.html#sect_C.11.1>`.

    Returns
    -------
    numpy.ndarray
        An array with applied modality LUT or rescale operation. If
        (0028,3000) *Modality LUT Sequence* is present then returns an array
        of ``np.uint8`` or ``np.uint16``, depending on the 3rd value of
        (0028,3002) *LUT Descriptor*. If (0028,1052) *Rescale Intercept* and
        (0028,1053) *Rescale Slope* are present then returns an array of
        ``np.float64``. If neither are present then `arr` will be returned
        unchanged.

    Notes
    -----
    When *Rescale Slope* and *Rescale Intercept* are used, the output range
    is from (min. pixel value * Rescale Slope + Rescale Intercept) to
    (max. pixel value * Rescale Slope + Rescale Intercept), where min. and
    max. pixel value are determined from (0028,0101) *Bits Stored* and
    (0028,0103) *Pixel Representation*.

    References
    ----------
    * DICOM Standard, Part 3, :dcm:`Annex C.11.1
      <part03/sect_C.11.html#sect_C.11.1>`
    * DICOM Standard, Part 4, :dcm:`Annex N.2.1.1
      <part04/sect_N.2.html#sect_N.2.1.1>`
    """
    if ds.get("ModalityLUTSequence"):
        item = cast(list["Dataset"], ds.ModalityLUTSequence)[0]
        nr_entries = cast(list[int], item.LUTDescriptor)[0] or 2**16
        first_map = cast(list[int], item.LUTDescriptor)[1]
        nominal_depth = cast(list[int], item.LUTDescriptor)[2]

        dtype = f"uint{nominal_depth}"

        # Ambiguous VR, US or OW
        unc_data: Iterable[int]
        if item["LUTData"].VR == VR.OW:
            if hasattr(ds, "file_meta"):
                is_little_endian = ds.file_meta._tsyntax_encoding[1]
            else:
                is_little_endian = ds.original_encoding[1]

            if is_little_endian is None:
                raise AttributeError(
                    "Unable to determine the endianness of the dataset, please set "
                    "an appropriate Transfer Syntax UID in "
                    f"'{type(ds).__name__}.file_meta'"
                )

            endianness = "><"[is_little_endian]
            unpack_fmt = f"{endianness}{nr_entries}H"
            unc_data = unpack(unpack_fmt, cast(bytes, item.LUTData))
        else:
            unc_data = cast(list[int], item.LUTData)

        lut_data: np.ndarray = np.asarray(unc_data, dtype=dtype)

        # IVs < `first_map` get set to first LUT entry (i.e. index 0)
        clipped_iv = np.zeros(arr.shape, dtype=arr.dtype)
        # IVs >= `first_map` are mapped by the Modality LUT
        # `first_map` may be negative, positive or 0
        mapped_pixels = arr >= first_map
        clipped_iv[mapped_pixels] = arr[mapped_pixels] - first_map
        # IVs > number of entries get set to last entry
        np.clip(clipped_iv, 0, nr_entries - 1, out=clipped_iv)

        return lut_data[clipped_iv]
    elif "RescaleSlope" in ds and "RescaleIntercept" in ds:
        arr = arr.astype(np.float64) * cast(float, ds.RescaleSlope)
        arr += cast(float, ds.RescaleIntercept)

    return arr


apply_rescale = apply_modality_lut


def apply_voi_lut(
    arr: "np.ndarray", ds: "Dataset", index: int = 0, prefer_lut: bool = True
) -> "np.ndarray":
    """Apply a VOI lookup table or windowing operation to `arr`.

    .. versionchanged:: 2.1

        Added the `prefer_lut` keyword parameter

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`~numpy.ndarray` to apply the VOI LUT or windowing operation
        to.
    ds : dataset.Dataset
        A dataset containing a :dcm:`VOI LUT Module<part03/sect_C.11.2.html>`.
        If (0028,3010) *VOI LUT Sequence* is present then returns an array
        of ``np.uint8`` or ``np.uint16``, depending on the 3rd value of
        (0028,3002) *LUT Descriptor*. If (0028,1050) *Window Center* and
        (0028,1051) *Window Width* are present then returns an array of
        ``np.float64``. If neither are present then `arr` will be returned
        unchanged.
    index : int, optional
        When the VOI LUT Module contains multiple alternative views, this is
        the index of the view to return (default ``0``).
    prefer_lut : bool
        When the VOI LUT Module contains both *Window Width*/*Window Center*
        and *VOI LUT Sequence*, if ``True`` (default) then apply the VOI LUT,
        otherwise apply the windowing operation.

    Returns
    -------
    numpy.ndarray
        An array with applied VOI LUT or windowing operation.

    Notes
    -----
    When the dataset requires a modality LUT or rescale operation as part of
    the Modality LUT module then that must be applied before any windowing
    operation.

    See Also
    --------
    :func:`~pydicom.pixels.processing.apply_modality_lut`
    :func:`~pydicom.pixels.processing.apply_voi`
    :func:`~pydicom.pixels.processing.apply_windowing`

    References
    ----------
    * DICOM Standard, Part 3, :dcm:`Annex C.11.2
      <part03/sect_C.11.html#sect_C.11.2>`
    * DICOM Standard, Part 3, :dcm:`Annex C.8.11.3.1.5
      <part03/sect_C.8.11.3.html#sect_C.8.11.3.1.5>`
    * DICOM Standard, Part 4, :dcm:`Annex N.2.1.1
      <part04/sect_N.2.html#sect_N.2.1.1>`
    """
    valid_voi = False
    if ds.get("VOILUTSequence"):
        ds.VOILUTSequence = cast(list["Dataset"], ds.VOILUTSequence)
        valid_voi = None not in [
            ds.VOILUTSequence[0].get("LUTDescriptor", None),
            ds.VOILUTSequence[0].get("LUTData", None),
        ]
    valid_windowing = None not in [
        ds.get("WindowCenter", None),
        ds.get("WindowWidth", None),
    ]

    if valid_voi and valid_windowing:
        if prefer_lut:
            return apply_voi(arr, ds, index)

        return apply_windowing(arr, ds, index)

    if valid_voi:
        return apply_voi(arr, ds, index)

    if valid_windowing:
        return apply_windowing(arr, ds, index)

    return arr


def apply_voi(arr: "np.ndarray", ds: "Dataset", index: int = 0) -> "np.ndarray":
    """Apply a VOI lookup table to `arr`.

    .. versionadded:: 2.1

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`~numpy.ndarray` to apply the VOI LUT to.
    ds : dataset.Dataset
        A dataset containing a :dcm:`VOI LUT Module<part03/sect_C.11.2.html>`.
        If (0028,3010) *VOI LUT Sequence* is present then returns an array
        of ``np.uint8`` or ``np.uint16``, depending on the 3rd value of
        (0028,3002) *LUT Descriptor*, otherwise `arr` will be returned
        unchanged.
    index : int, optional
        When the VOI LUT Module contains multiple alternative views, this is
        the index of the view to return (default ``0``).

    Returns
    -------
    numpy.ndarray
        An array with applied VOI LUT.

    See Also
    --------
    :func:`~pydicom.pixels.processing.apply_modality_lut`
    :func:`~pydicom.pixels.processing.apply_windowing`

    References
    ----------
    * DICOM Standard, Part 3, :dcm:`Annex C.11.2
      <part03/sect_C.11.html#sect_C.11.2>`
    * DICOM Standard, Part 3, :dcm:`Annex C.8.11.3.1.5
      <part03/sect_C.8.11.3.html#sect_C.8.11.3.1.5>`
    * DICOM Standard, Part 4, :dcm:`Annex N.2.1.1
      <part04/sect_N.2.html#sect_N.2.1.1>`
    """
    if not ds.get("VOILUTSequence"):
        return arr

    if not np.issubdtype(arr.dtype, np.integer):
        warn_and_log(
            "Applying a VOI LUT on a float input array may give incorrect results"
        )

    # VOI LUT Sequence contains one or more items
    item = cast(list["Dataset"], ds.VOILUTSequence)[index]
    lut_descriptor = cast(list[int], item.LUTDescriptor)
    nr_entries = lut_descriptor[0] or 2**16
    first_map = lut_descriptor[1]

    # PS3.3 C.8.11.3.1.5: may be 8, 10-16
    nominal_depth = lut_descriptor[2]
    if nominal_depth in list(range(10, 17)):
        dtype = "uint16"
    elif nominal_depth == 8:
        dtype = "uint8"
    else:
        raise NotImplementedError(
            f"'{nominal_depth}' bits per LUT entry is not supported"
        )

    # Ambiguous VR, US or OW
    unc_data: Iterable[int]
    if item["LUTData"].VR == VR.OW:
        if hasattr(ds, "file_meta"):
            is_little_endian = ds.file_meta._tsyntax_encoding[1]
        else:
            is_little_endian = ds.original_encoding[1]

        if is_little_endian is None:
            raise AttributeError(
                "Unable to determine the endianness of the dataset, please set "
                "an appropriate Transfer Syntax UID in "
                f"'{type(ds).__name__}.file_meta'"
            )

        unpack_fmt = f"{'><'[is_little_endian]}{nr_entries}H"
        unc_data = unpack_from(unpack_fmt, cast(bytes, item.LUTData))
    else:
        unc_data = cast(list[int], item.LUTData)

    lut_data: np.ndarray = np.asarray(unc_data, dtype=dtype)

    # IVs < `first_map` get set to first LUT entry (i.e. index 0)
    clipped_iv = np.zeros(arr.shape, dtype=dtype)
    # IVs >= `first_map` are mapped by the VOI LUT
    # `first_map` may be negative, positive or 0
    mapped_pixels = arr >= first_map
    clipped_iv[mapped_pixels] = arr[mapped_pixels] - first_map
    # IVs > number of entries get set to last entry
    np.clip(clipped_iv, 0, nr_entries - 1, out=clipped_iv)

    return cast("np.ndarray", lut_data[clipped_iv])


def apply_windowing(arr: "np.ndarray", ds: "Dataset", index: int = 0) -> "np.ndarray":
    """Apply a windowing operation to `arr`.

    .. versionadded:: 2.1

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`~numpy.ndarray` to apply the windowing operation to.
    ds : dataset.Dataset
        A dataset containing a :dcm:`VOI LUT Module<part03/sect_C.11.2.html>`.
        If (0028,1050) *Window Center* and (0028,1051) *Window Width* are
        present then returns an array of ``np.float64``, otherwise `arr` will
        be returned unchanged.
    index : int, optional
        When the VOI LUT Module contains multiple alternative views, this is
        the index of the view to return (default ``0``).

    Returns
    -------
    numpy.ndarray
        An array with applied windowing operation.

    Notes
    -----
    When the dataset requires a modality LUT or rescale operation as part of
    the Modality LUT module then that must be applied before any windowing
    operation.

    See Also
    --------
    :func:`~pydicom.pixels.processing.apply_modality_lut`
    :func:`~pydicom.pixels.processing.apply_voi`

    References
    ----------
    * DICOM Standard, Part 3, :dcm:`Annex C.11.2
      <part03/sect_C.11.html#sect_C.11.2>`
    * DICOM Standard, Part 3, :dcm:`Annex C.8.11.3.1.5
      <part03/sect_C.8.11.3.html#sect_C.8.11.3.1.5>`
    * DICOM Standard, Part 4, :dcm:`Annex N.2.1.1
      <part04/sect_N.2.html#sect_N.2.1.1>`
    """
    if "WindowWidth" not in ds and "WindowCenter" not in ds:
        return arr

    if ds.PhotometricInterpretation not in ["MONOCHROME1", "MONOCHROME2"]:
        raise ValueError(
            "When performing a windowing operation only 'MONOCHROME1' and "
            "'MONOCHROME2' are allowed for (0028,0004) Photometric "
            "Interpretation"
        )

    # May be LINEAR (default), LINEAR_EXACT, SIGMOID or not present, VM 1
    voi_func = cast(str, getattr(ds, "VOILUTFunction", "LINEAR")).upper()
    # VR DS, VM 1-n
    elem = ds["WindowCenter"]
    center = cast(list[float], elem.value)[index] if elem.VM > 1 else elem.value
    center = cast(float, center)
    elem = ds["WindowWidth"]
    width = cast(list[float], elem.value)[index] if elem.VM > 1 else elem.value
    width = cast(float, width)

    # The output range depends on whether or not a modality LUT or rescale
    #   operation has been applied
    ds.BitsStored = cast(int, ds.BitsStored)
    y_min: float
    y_max: float
    if ds.get("ModalityLUTSequence"):
        # Unsigned - see PS3.3 C.11.1.1.1
        y_min = 0
        item = cast(list["Dataset"], ds.ModalityLUTSequence)[0]
        bit_depth = cast(list[int], item.LUTDescriptor)[2]
        y_max = 2**bit_depth - 1
    elif ds.PixelRepresentation == 0:
        # Unsigned
        y_min = 0
        y_max = 2**ds.BitsStored - 1
    else:
        # Signed
        y_min = -(2 ** (ds.BitsStored - 1))
        y_max = 2 ** (ds.BitsStored - 1) - 1

    slope = ds.get("RescaleSlope", None)
    intercept = ds.get("RescaleIntercept", None)
    if slope is not None and intercept is not None:
        ds.RescaleSlope = cast(float, ds.RescaleSlope)
        ds.RescaleIntercept = cast(float, ds.RescaleIntercept)
        # Otherwise its the actual data range
        y_min = y_min * ds.RescaleSlope + ds.RescaleIntercept
        y_max = y_max * ds.RescaleSlope + ds.RescaleIntercept

    y_range = y_max - y_min
    arr = arr.astype("float64")

    if voi_func in ["LINEAR", "LINEAR_EXACT"]:
        # PS3.3 C.11.2.1.2.1 and C.11.2.1.3.2
        if voi_func == "LINEAR":
            if width < 1:
                raise ValueError(
                    "The (0028,1051) Window Width must be greater than or "
                    "equal to 1 for a 'LINEAR' windowing operation"
                )
            center -= 0.5
            width -= 1
        elif width <= 0:
            raise ValueError(
                "The (0028,1051) Window Width must be greater than 0 "
                "for a 'LINEAR_EXACT' windowing operation"
            )

        below = arr <= (center - width / 2)
        above = arr > (center + width / 2)
        between = np.logical_and(~below, ~above)

        arr[below] = y_min
        arr[above] = y_max
        if between.any():
            arr[between] = ((arr[between] - center) / width + 0.5) * y_range + y_min
    elif voi_func == "SIGMOID":
        # PS3.3 C.11.2.1.3.1
        if width <= 0:
            raise ValueError(
                "The (0028,1051) Window Width must be greater than 0 "
                "for a 'SIGMOID' windowing operation"
            )

        arr = y_range / (1 + np.exp(-4 * (arr - center) / width)) + y_min
    else:
        raise ValueError(f"Unsupported (0028,1056) VOI LUT Function value '{voi_func}'")

    return arr


def convert_color_space(
    arr: "np.ndarray", current: str, desired: str, per_frame: bool = False
) -> "np.ndarray":
    """Convert the image(s) in `arr` from one color space to another.

    .. versionchanged:: 2.2

        Added `per_frame` keyword parameter.

    Parameters
    ----------
    arr : numpy.ndarray
        The image(s) as :class:`numpy.ndarray` with :attr:`~numpy.ndarray.shape`
        (frames, rows, columns, 3) or (rows, columns, 3) and a 'uint8'
        :class:`~numpy.dtype` (unsigned 8-bit).
    current : str
        The current color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of ``'RGB'``, ``'YBR_FULL'``,
        ``'YBR_FULL_422'``.
    desired : str
        The desired color space, should be a valid value for (0028,0004)
        *Photometric Interpretation*. One of ``'RGB'``, ``'YBR_FULL'``,
        ``'YBR_FULL_422'``.
    per_frame : bool, optional
        If ``True`` and the input array contains multiple frames then process
        each frame individually and update `arr` in-place to reduce memory
        usage. Default ``False``.

    Returns
    -------
    numpy.ndarray
        The image(s) converted to the desired color space. If `per_frame` is
        ``False`` (the default) then a new :class:`~numpy.ndarray` will be
        returned, otherwise `arr` will be updated in-place.

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1.2<part03/sect_C.7.6.3.html#sect_C.7.6.3.1.2>`
    * ISO/IEC 10918-5:2012 (`ITU T.871
      <https://www.ijg.org/files/T-REC-T.871-201105-I!!PDF-E.pdf>`_),
      Section 7
    """
    if arr.dtype != np.dtype("u1"):
        raise ValueError(
            f"Invalid ndarray.dtype '{arr.dtype}' for color space conversion, "
            "must be 'uint8' or an equivalent"
        )

    def _no_change(arr: "np.ndarray") -> "np.ndarray":
        return arr

    _converters = {
        "YBR_FULL_422": {
            "YBR_FULL_422": _no_change,
            "YBR_FULL": _no_change,
            "RGB": _convert_YBR_FULL_to_RGB,
        },
        "YBR_FULL": {
            "YBR_FULL": _no_change,
            "YBR_FULL_422": _no_change,
            "RGB": _convert_YBR_FULL_to_RGB,
        },
        "RGB": {
            "RGB": _no_change,
            "YBR_FULL": _convert_RGB_to_YBR_FULL,
            "YBR_FULL_422": _convert_RGB_to_YBR_FULL,
        },
    }
    try:
        converter = _converters[current][desired]
    except KeyError:
        raise NotImplementedError(
            f"Conversion from {current} to {desired} is not supported."
        )

    if len(arr.shape) == 4 and per_frame:
        for idx, frame in enumerate(arr):
            arr[idx] = converter(frame)

        return arr

    return converter(arr)


def _convert_RGB_to_YBR_FULL(arr: "np.ndarray") -> "np.ndarray":
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
        [
            [+0.299, -0.299 / 1.772, +0.701 / 1.402],
            [+0.587, -0.587 / 1.772, -0.587 / 1.402],
            [+0.114, +0.886 / 1.772, -0.114 / 1.402],
        ],
        dtype=np.float32,
    )

    arr = np.matmul(arr, rgb_to_ybr, dtype=np.float32)
    arr += [0.5, 128.5, 128.5]
    # Round(x) -> floor of (arr + 0.5) : 0.5 added in previous step
    np.floor(arr, out=arr)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    np.clip(arr, 0, 255, out=arr)

    return arr.astype(orig_dtype)


def _convert_YBR_FULL_to_RGB(arr: "np.ndarray") -> "np.ndarray":
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
        [
            [1.000, 1.000, 1.000],
            [0.000, -0.114 * 1.772 / 0.587, 1.772],
            [1.402, -0.299 * 1.402 / 0.587, 0.000],
        ],
        dtype=np.float32,
    )

    arr = arr.astype(np.float32)
    arr -= [0, 128, 128]

    # Round(x) -> floor of (arr + 0.5)
    np.matmul(arr, ybr_to_rgb, out=arr)
    arr += 0.5
    np.floor(arr, out=arr)
    # Max(0, arr) -> 0 if 0 >= arr, arr otherwise
    # Min(arr, 255) -> arr if arr <= 255, 255 otherwise
    np.clip(arr, 0, 255, out=arr)

    return arr.astype(orig_dtype)


def _expand_segmented_lut(
    data: tuple[int, ...],
    fmt: str,
    nr_segments: int | None = None,
    last_value: int | None = None,
) -> list[int]:
    """Return a list containing the expanded lookup table data.

    Parameters
    ----------
    data : tuple of int
        The decoded segmented palette lookup table data. May be padded by a
        trailing null.
    fmt : str
        The format of the data, should contain `'B'` for 8-bit, `'H'` for
        16-bit, `'<'` for little endian and `'>'` for big endian.
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
    indirect_ii = [3, 2, 1, 0] if "<" in fmt else [2, 3, 0, 1]

    lut: list[int] = []
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
            lut.extend(data[offset : offset + length])
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
                vals = np.around(np.linspace(y0 + step, y1, length))
                lut.extend([int(vv) for vv in vals])
        elif opcode == 2:
            # C.7.9.2.3: Indirect segment
            if not lut:
                raise ValueError(
                    "Error expanding a segmented palette color lookup table: "
                    "the first segment cannot be an indirect segment"
                )

            if "B" in fmt:
                # 8-bit segment entries
                ii = [data[offset + vv] for vv in indirect_ii]
                byte_offset = (ii[0] << 8 | ii[1]) << 16 | (ii[2] << 8 | ii[3])
                offset += 4
            else:
                # 16-bit segment entries
                byte_offset = data[offset + 1] << 16 | data[offset]
                offset += 2

            lut.extend(_expand_segmented_lut(data[byte_offset:], fmt, length, lut[-1]))
        else:
            raise ValueError(
                "Error expanding a segmented palette lookup table: "
                f"unknown segment type '{opcode}'"
            )

        segments_read += 1
        if segments_read == nr_segments:
            return lut

    return lut
