# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Pixel data decoding."""

from collections.abc import Callable, Iterator, Iterable
import logging
from io import BufferedIOBase
from math import ceil, floor
import sys
from typing import Any, BinaryIO, cast, TYPE_CHECKING

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import config
from pydicom.encaps import get_frame, generate_frames
from pydicom.misc import warn_and_log
from pydicom.pixels.common import (
    Buffer,
    RunnerBase,
    RunnerOptions,
    CoderBase,
    PhotometricInterpretation as PI,
)
from pydicom.pixels.processing import convert_color_space
from pydicom.pixels.utils import (
    _get_jpg_parameters,
    get_j2k_parameters,
)
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
    RLELossless,
    UID,
    JPEG2000TransferSyntaxes,
    JPEGLSTransferSyntaxes,
    JPEGTransferSyntaxes,
)

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


LOGGER = logging.getLogger(__name__)


DecodeFunction = Callable[[bytes, "DecodeRunner"], bytes | bytearray]
ProcessingFunction = Callable[
    ["np.ndarray", "DecodeRunner", dict[str, str | int]], "np.ndarray"
]


class DecodeOptions(RunnerOptions, total=False):
    """Options accepted by DecodeRunner and decoding plugins"""

    # The VR used for the pixel data - may be used with Explicit VR Big Endian
    pixel_vr: str
    # Allow returning/yielding excess frames when found
    allow_excess_frames: bool
    # (ndarray only) When *Bits Stored* != *Bits Allocated* perform bit shift
    #   operations to avoid using the unused bits
    correct_unused_bits: bool

    ## Native transfer syntax decoding options
    # Return/yield a view of the original buffer where possible
    view_only: bool
    # (ndarray only) Force byte swapping on 8-bit values encoded as OW
    be_swap_ow: bool

    ## RLE decoding options
    # Segment ordering ">" for big endian (default) or "<" for little endian
    rle_segment_order: str  # pydicom plugin
    byteorder: str  # pylibjpeg + -rle plugin

    ## JPEG-LS decoding options
    # Use the JPEG-LS metadata to return an ndarray matched to the expected pixel
    # representation, otherwise return the decoded data as-is (ndarray only)
    apply_jls_sign_correction: bool

    ## JPEG2000/HTJ2K decoding options
    # Use the JPEG 2000 metadata to return an ndarray matched to the expected pixel
    # representation, otherwise return the decoded data as-is (ndarray only)
    apply_j2k_sign_correction: bool

    ## Processing options (ndarray only)
    as_rgb: bool  # Make best effort to return RGB output
    force_rgb: bool  # Force YBR to RGB conversion
    force_ybr: bool  # Force RGB to YBR conversion


def _process_color_space(
    arr: "np.ndarray", runner: "DecodeRunner", changes: dict[str, str | int]
) -> "np.ndarray":
    """Convert `arr` to a given color space, typically RGB."""
    # If force_ybr then always do conversion (ignore as_rgb)
    force_ybr = runner.get_option("force_ybr", False)
    force_rgb = runner.get_option("force_rgb", False)
    if force_ybr and force_rgb:
        raise ValueError("'force_ybr' and 'force_rgb' cannot both be True")

    to_rgb = (
        runner.photometric_interpretation in (PI.YBR_FULL, PI.YBR_FULL_422)
        and runner.get_option("as_rgb", False)
    ) or force_rgb

    if not arr.flags.writeable and (to_rgb or force_ybr):
        if runner.get_option("view_only", False):
            LOGGER.warning(
                "Unable to return an ndarray that's a view on the original "
                "buffer if applying a color space conversion"
            )

        arr = arr.copy()

    # Converting to/from YBR_FULL and YBR_FULL_422 uses the same transformation
    if force_ybr:
        arr = convert_color_space(arr, PI.RGB, PI.YBR_FULL)
        changes["photometric_interpretation"] = PI.YBR_FULL
    elif to_rgb:
        arr = convert_color_space(arr, PI.YBR_FULL, PI.RGB)
        changes["photometric_interpretation"] = PI.RGB

    return arr


def _correct_unused_bits(
    arr: "np.ndarray", runner: "DecodeRunner", log_warning: bool = True
) -> "np.ndarray":
    """Perform a bit-shift correction on `arr` to avoid using any unused bits"""
    # If *Bits Stored* < *Bits Allocated* then we (technically) always
    #   need to shift because the values of the unused bits cannot be assumed
    #   - PS3.5, Section 8.1.1
    # e.g. For Bits Stored 5, Pixel Representation 1 we may have a signed value:
    #   0001 1001, however the 3 MSb should be ignored so bit shifting
    #   (with a signed integer dtype) will give 0001 1001 -> 1100 1000 -> 1111 1001
    # In practice this isn't usually necessary as most application will fill
    #   the unused bits with values that produce the correct interpretation
    if (
        log_warning
        and runner.get_option("view_only", False)
        and not runner.transfer_syntax.is_encapsulated
        and not arr.flags.writeable
    ):
        LOGGER.warning(
            "Unable to return an ndarray that's a view on the original buffer when "
            "(0028,0101) 'Bits Stored' doesn't equal (0028,0100) 'Bits Allocated' "
            "and 'correct_unused_bits=True'. In most cases you can pass "
            "'correct_unused_bits=False' instead to get a view if the uncorrected "
            "array is equivalent to the corrected one."
        )

    if not arr.flags.writeable:
        arr = arr.copy()

    bit_shift = runner.bits_allocated - runner.bits_stored
    np.left_shift(arr, bit_shift, out=arr)
    np.right_shift(arr, bit_shift, out=arr)

    return arr


def _apply_sign_correction(arr: "np.ndarray", runner: "DecodeRunner") -> "np.ndarray":
    """Convert `arr` to match the signedness required by the 'pixel_representation'."""
    # JPEG 2000 Example:
    # Dataset: Pixel Representation 1, Bits Stored 13, Bits Allocated 16
    # J2K codestream: precision 13, signedness 0 (i.e. unsigned)
    #
    # For the raw 13-bit signed integer (value -2000):
    #        1 1000 0011 0000
    #
    # If the 13-bit signed integer is incorrectly encoded as an unsigned integer,
    # then after decoding the 16-bit signed value will be:
    #     0001 1000 0011 0000  (value 6192)
    # If it were encoded correctly as a signed integer it would instead be:
    #     1111 1000 0011 0000  (value -2000)
    #
    # To correct for this, we need to bit shift the incorrectly interpreted
    # 16-bit signed integer left by 3 bits:
    #     1100 0001 1000 0000  (value -16000)
    # And then right shift back 3 bits to get the final value:
    #     1111 1000 0011 0000  (value -2000)
    #
    # And similarly, when the Pixel Representation is 0 and J2K is signed, then
    # after decoding the 16-bit unsigned value will be:
    #     1111 1000 0011 0000  (value 63536)
    # If it were encoded correctly as an unsigned integer it would instead be:
    #     0001 1000 0011 0000  (value 6192)
    # Which can be fixed in the same way as for signed integers.
    if runner.transfer_syntax in JPEG2000TransferSyntaxes:
        j2k_signed = runner.get_option("j2k_is_signed", runner.pixel_representation)
        precision = runner.get_option("j2k_precision", runner.bits_stored)
        bit_shift = 8 * arr.dtype.itemsize - precision
        if bit_shift and j2k_signed != runner.pixel_representation:
            np.left_shift(arr, bit_shift, out=arr)
            np.right_shift(arr, bit_shift, out=arr)
    elif runner.transfer_syntax in JPEGLSTransferSyntaxes:
        # JPEG-LS has no way to track signedness, so signed integers are
        #   always decoded as unsigned
        precision = runner.get_option("jls_precision", runner.bits_stored)
        bit_shift = 8 * arr.dtype.itemsize - precision
        if bit_shift:
            np.left_shift(arr, bit_shift, out=arr)
            np.right_shift(arr, bit_shift, out=arr)

    return arr


# Allow customization of the image processors
PROCESSORS: list[ProcessingFunction] = [_process_color_space]


class DecodeRunner(RunnerBase):
    """Class for managing the pixel data decoding process.

    .. versionadded:: 3.0

    This class is not intended to be used directly. For decoding pixel data
    use the :class:`~pydicom.pixels.decoders.base.Decoder` instance
    corresponding to the transfer syntax of the pixel data.
    """

    def __init__(self, tsyntax: UID) -> None:
        """Create a new runner for decoding data encoded as `tsyntax`.

        Parameters
        ----------
        tsyntax : pydicom.uid.UID
            The transfer syntax UID corresponding to the pixel data to be
            decoded.
        """
        self._src: Buffer | BinaryIO
        self._src_type: str
        self._opts: DecodeOptions = {
            "transfer_syntax_uid": tsyntax,
            "as_rgb": True,
            "allow_excess_frames": True,
        }
        self._undeletable = ("transfer_syntax_uid", "pixel_keyword")
        self._decoders: dict[str, DecodeFunction] = {}
        self._previous: tuple[str, DecodeFunction]

        if self.transfer_syntax.is_encapsulated:
            self.set_option("pixel_keyword", "PixelData")
        else:
            self.set_option("view_only", False)

        if self.transfer_syntax in JPEG2000TransferSyntaxes:
            self.set_option("apply_j2k_sign_correction", True)
        elif self.transfer_syntax in JPEGLSTransferSyntaxes:
            self.set_option("apply_jls_sign_correction", True)
        else:
            self.set_option("correct_unused_bits", True)

    def _conform_jpg_colorspace(self, info: dict[str, Any]) -> None:
        """Conform the photometric interpretation to the JPEG/JPEG-LS codestream.

        Parameters
        ----------
        info : dict[str, Any]
            A dictionary containing JPEG/JPEG-LS codestream metadata.
        """
        if self.samples_per_pixel != 3:
            return

        pi = self.photometric_interpretation

        # Check the component IDs for RGB or rgb (in ASCII)
        has_rgb_ids = info.get("component_ids", None) in ([82, 71, 66], [114, 103, 98])
        if has_rgb_ids and pi != PI.RGB:
            self.set_option("photometric_interpretation", PI.RGB)
            warn_and_log(
                f"The (0028,0004) 'Photometric Interpretation' value is '{pi}' "
                "however the encoded image's codestream uses component IDs that "
                "indicate it should be 'RGB'"
            )
            return

        # A JFIF APP marker means the decoded image should be YBR colour space
        #   https://www.w3.org/Graphics/JPEG/jfif.pdf
        cs = (
            PI.YBR_FULL_422 if self.transfer_syntax == JPEGBaseline8Bit else PI.YBR_FULL
        )
        for marker in info.get("app", {}).values():
            if marker.startswith(b"JFIF") and "YBR" not in pi:
                self.set_option("photometric_interpretation", cs)
                warn_and_log(
                    "The (0028,0004) 'Photometric Interpretation' value is "
                    f"'{pi}' however the encoded image's codestream contains a "
                    f"JFIF APP marker which indicates it should be '{cs}'"
                )
                return

    def decode(self, index: int) -> bytes | bytearray:
        """Decode the frame of pixel data at `index`.

        Parameters
        ----------
        index : int
            The index of the frame to be decoded.

        Returns
        -------
        bytes | bytearray
            The decoded frame of pixel data.
        """
        # For encapsulated data `self.src` should not be memoryview to avoid
        #   creating a duplicate object in memory by the encapsulation functions
        src = get_frame(
            self.src,
            index,
            number_of_frames=self.number_of_frames,
            extended_offsets=self.extended_offsets,
        )
        self._get_frame_info(src)

        return self._decode_frame(src)

    def _decode_frame(self, src: bytes) -> bytes | bytearray:
        """Return a decoded frame of pixel data.

        Parameters
        ----------
        src : bytes
            An encoded frame of pixel data to be passed to the decoding plugins.

        Returns
        -------
        bytes | bytearray
            The decoded frame.
        """

        # If self._previous is not set then this is the first frame being decoded
        # If self._previous is set, then the previously successful decoder
        #   has failed while decoding a frame and we are trying the other decoders
        failure_messages = []
        for name, func in self._decoders.items():
            try:
                # Attempt to decode the frame
                frame = func(src, self)

                # Decode success, if we were previously successful then
                #   warn about the change to the new decoder
                if hasattr(self, "_previous") and self._previous[1] != func:
                    warn_and_log(
                        f"The decoding plugin has changed from '{self._previous[0]}' "
                        f"to '{name}' during the decoding process - you may get "
                        f"inconsistent inter-frame results, consider passing "
                        f"'decoding_plugin=\"{name}\"' instead"
                    )

                self._previous = (name, func)
                return frame
            except Exception as exc:
                LOGGER.exception(exc)
                failure_messages.append(f"{name}: {exc}")

        messages = "\n  ".join(failure_messages)
        raise RuntimeError(
            "Unable to decode as exceptions were raised by all available "
            f"plugins:\n  {messages}"
        )

    def get_data(self, src: Buffer | BinaryIO, offset: int, length: int) -> bytes:
        """Return `length` bytes from `src`, starting at `offset`.

        Parameters
        ----------
        src : buffer-like | file-like
            The source of the data to be returned. If a file-like then the file
            position after reading will returned to the original offset.
        offset : int
            The starting offset of the data in `src`.
        length : int
            The number of bytes to try to return.

        Returns
        -------
        bytes
            The data from `src`, may return fewer bytes if the end of `src` is
            reached before ``offset + length``.
        """
        if self.is_dataset or self.is_buffer:
            src = cast(Buffer, src)
            return src[offset : offset + length]

        src = cast(BinaryIO, src)
        file_offset = src.tell()
        src.seek(offset)
        buffer = src.read(length)
        src.seek(file_offset)
        return buffer

    def _get_frame_info(self, src: bytes) -> None:
        """Parse a frame's codestream for JPEG-related parameters."""
        if self.transfer_syntax in JPEG2000TransferSyntaxes:
            j2k_info = get_j2k_parameters(src)
            self.set_option(
                "j2k_is_signed", j2k_info.get("is_signed", self.pixel_representation)
            )
            self.set_option(
                "j2k_precision", j2k_info.get("precision", self.bits_stored)
            )
        elif self.transfer_syntax in JPEGLSTransferSyntaxes:
            jls_info = _get_jpg_parameters(src)
            self.set_option(
                "jls_precision", jls_info.get("precision", self.bits_stored)
            )
            self._conform_jpg_colorspace(jls_info)
        elif self.transfer_syntax in JPEGTransferSyntaxes:
            jpg_info = _get_jpg_parameters(src)
            self._conform_jpg_colorspace(jpg_info)

    def iter_decode(self) -> Iterator[bytes | bytearray]:
        """Yield decoded frames from the encoded pixel data."""
        if self.is_binary:
            file_offset = cast(BinaryIO, self.src).tell()

        # For encapsulated data `self.src` should not be memoryview as doing so
        #   will create a duplicate object in memory by `generate_frames`
        # May yield more frames than `number_of_frames` for JPEG!
        encoded_frames = generate_frames(
            self.src,
            number_of_frames=self.number_of_frames,
            extended_offsets=self.extended_offsets,
        )
        for index, src in enumerate(encoded_frames):
            self._get_frame_info(src)

            # Try the previously successful decoder first (if available)
            name, func = getattr(self, "_previous", (None, None))
            if func:
                try:
                    yield func(src, self)
                    continue
                except Exception:
                    LOGGER.warning(
                        f"The decoding plugin '{name}' failed to decode the "
                        f"frame at index {index}"
                    )

            # Otherwise try all decoders
            yield self._decode_frame(src)

        if self.is_binary:
            cast(BinaryIO, self.src).seek(file_offset)

    @property
    def pixel_dtype(self) -> "np.dtype":
        """Return a :class:`numpy.dtype` suitable for containing the decoded
        pixel data.
        """
        if not HAVE_NP:
            raise ImportError("NumPy is required for 'DecodeRunner.pixel_dtype'")

        dtype: np.dtype
        pixel_keyword = self.pixel_keyword
        if pixel_keyword == "FloatPixelData":
            dtype = np.dtype("float32")
        elif pixel_keyword == "DoubleFloatPixelData":
            dtype = np.dtype("float64")
        else:
            # (0028,0103) Pixel Representation, US, 1
            #   0x0000 - unsigned int
            #   0x0001 - 2's complement (signed int)
            dtype_str = "ui"[self.pixel_representation]

            # (0028,0100) Bits Allocated, US, 1
            #   PS3.5 8.1.1: Bits Allocated is either 1 or a multiple of 8
            if self.bits_allocated == 1:
                dtype_str = "u1"
            elif self.bits_allocated > 0 and self.bits_allocated % 8 == 0:
                dtype_str += f"{self.bits_allocated // 8}"

            # Check to see if the dtype is valid for numpy
            try:
                dtype = np.dtype(dtype_str)
            except TypeError:
                raise NotImplementedError(
                    f"The data type '{dtype_str}' needed to contain the pixel "
                    "data is not supported by NumPy"
                )

        # Correct for endianness of the system vs endianness of the dataset
        if self.transfer_syntax.is_little_endian != (sys.byteorder == "little"):
            # 'S' swap from current to opposite
            dtype = dtype.newbyteorder("S")

        return dtype

    def pixel_properties(self, as_frame: bool = False) -> dict[str, str | int]:
        """Return a dict containing the :dcm:`Image Pixel
        <part03/sect_C.7.6.3.html>` module related properties.

        Parameters
        ----------
        as_frame : bool, optional
            If ``True`` then don't include properties that aren't appropriate
            for a single frame. Default ``False``.

        Returns
        -------
        dict[str, str | int]
            A dict containing the values for:

            * `bits_allocated`
            * `bits_stored`
            * `columns`
            * `photometric_interpretation`
            * `samples_per_pixel`
            * `rows`
            * `number_of_frames`
            * `planar_configuration` (if `samples_per_pixel` > 1)
            * `pixel_representation` (if the pixel keyword is ``"PixelData"``)

            The returned values depend on whether or not this method is
            called before or after decoding the pixel data, as the decoding
            plugins and image processing functions may update the values as
            needed to reflect the corresponding decoded data. For example, if
            the pixel data is converted from the YCbCr to RGB color space then
            the `photometric_interpretation` value will be changed to match
            after the data has been decoded.
        """
        d = {
            "bits_allocated": self.bits_allocated,
            "columns": self.columns,
            "number_of_frames": self.number_of_frames if not as_frame else 1,
            "photometric_interpretation": str(self.photometric_interpretation),
            "rows": self.rows,
            "samples_per_pixel": self.samples_per_pixel,
        }

        if self.samples_per_pixel > 1:
            d["planar_configuration"] = self.planar_configuration

        if self.pixel_keyword == "PixelData":
            d["bits_stored"] = self.bits_stored
            d["pixel_representation"] = self.pixel_representation

        return cast(dict[str, str | int], d)

    def process(self, arr: "np.ndarray") -> tuple["np.ndarray", dict[str, str | int]]:
        """Return `arr` after applying zero or more processing operations.

        Returns
        -------
        numpy.ndarray
            The array with the applied processing.
        dict[str, int | str]
            A :class:`dict` containing any required changes to the image pixel
            properties due to the processing.
        """
        changes: dict[str, str | int] = {}
        for func in PROCESSORS:
            arr = func(arr, self, changes)

        return arr, changes

    def reshape(self, arr: "np.ndarray", as_frame: bool = False) -> "np.ndarray":
        """Return a reshaped :class:`~numpy.ndarray` `arr`.

        Parameters
        ----------
        arr : np.ndarray
            The 1D array to be reshaped.
        as_frame : bool, optional
            If ``True`` then treat `arr` as only containing a single frame's
            worth of pixel data, otherwise treat `arr` as containing the full
            amount of pixel data (default).

        Returns
        -------
        np.ndarray
            A view of the input `arr` reshaped to:

            * (rows, columns) for single frame, single sample data
            * (rows, columns, samples) for single frame, multi-sample data
            * (frames, rows, columns) for multi-frame, single sample data
            * (frames, rows, columns, samples) for multi-frame, multi-sample data
        """
        number_of_frames = self.number_of_frames
        samples_per_pixel = self.samples_per_pixel
        rows = self.rows
        columns = self.columns

        if not as_frame and number_of_frames > 1:
            # Multi-frame, single sample
            if samples_per_pixel == 1:
                return arr.reshape(number_of_frames, rows, columns)

            # Multi-frame, multiple samples, planar configuration 0
            if self.planar_configuration == 0:
                return arr.reshape(number_of_frames, rows, columns, samples_per_pixel)

            # Multi-frame, multiple samples, planar configuration 1
            arr = arr.reshape(number_of_frames, samples_per_pixel, rows, columns)
            return arr.transpose(0, 2, 3, 1)

        # Single frame, single sample
        if samples_per_pixel == 1:
            return arr.reshape(rows, columns)

        # Single frame, multiple samples, planar configuration 0
        if self.planar_configuration == 0:
            return arr.reshape(rows, columns, samples_per_pixel)

        # Single frame, multiple samples, planar configuration 1
        arr = arr.reshape(samples_per_pixel, rows, columns)
        return arr.transpose(1, 2, 0)

    def set_decoders(self, decoders: dict[str, DecodeFunction]) -> None:
        """Set the decoders use for decoding compressed pixel data.

        Parameters
        ----------
        decoders : dict[str, DecodeFunction]
            A dict of {name: decoder function}.
        """
        self._decoders = decoders
        if hasattr(self, "_previous"):
            del self._previous

    def _set_options_ds(self, ds: "Dataset") -> None:
        """Set options using a dataset.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to use.
        """
        super()._set_options_ds(ds)

        file_meta = getattr(ds, "file_meta", {})
        if tsyntax := file_meta.get("TransferSyntaxUID", None):
            if tsyntax != self.transfer_syntax:
                raise ValueError(
                    f"The dataset's transfer syntax '{tsyntax.name}' doesn't "
                    "match the pixel data decoder"
                )

        keywords = ["PixelData", "FloatPixelData", "DoubleFloatPixelData"]
        px_keyword = [kw for kw in keywords if kw in ds]
        if not px_keyword:
            raise AttributeError(
                "The dataset has no 'Pixel Data', 'Float Pixel Data' or 'Double "
                "Float Pixel Data' element, no pixel data to decode"
            )

        if len(px_keyword) != 1:
            raise AttributeError(
                "One and only one of 'Pixel Data', 'Float Pixel Data' or "
                "'Double Float Pixel Data' may be present in the dataset"
            )

        self.set_option("pixel_keyword", px_keyword[0])
        self.set_option("pixel_vr", ds[px_keyword[0]].VR)

    def set_source(self, src: "Buffer | Dataset | BinaryIO") -> None:
        """Set the pixel data to be decoded.

        Parameters
        ----------
        src : bytes | bytearray | memoryview | pydicom.dataset.Dataset
            If a buffer-like then the encoded pixel data, otherwise the
            :class:`~pydicom.dataset.Dataset` containing the pixel data and
            associated group ``0x0028`` elements.
        """
        from pydicom.dataset import Dataset

        if isinstance(src, Dataset):
            self._set_options_ds(src)
            self._src = src[self.pixel_keyword].value
            if isinstance(self._src, BufferedIOBase):
                self._src_type = "BinaryIO"
            else:
                self._src_type = "Dataset"
        elif hasattr(src, "read"):
            self._src = src
            self._src_type = "BinaryIO"
        else:
            self._src = src
            self._src_type = "Buffer"

    @property
    def src(self) -> Buffer | BinaryIO:
        """Return the buffer-like or file-like containing the encoded pixel data."""
        return self._src

    def __str__(self) -> str:
        """Return nice string output for the runner."""
        s = [f"DecodeRunner for '{self.transfer_syntax.name}'"]
        s.append("Options")
        s.extend([f"  {name}: {value}" for name, value in self.options.items()])
        if self._decoders:
            s.append("Decoders")
            s.extend([f"  {name}" for name in self._decoders])

        return "\n".join(s)

    def _test_for(self, test: str) -> bool:
        """Return the result of `test` as :class:`bool`."""
        if test == "be_swap_ow":
            if self.get_option("be_swap_ow"):
                return True

            return (
                not self.transfer_syntax.is_little_endian
                and self.bits_allocated // 8 == 1
                and self.pixel_keyword == "PixelData"
                and self.get_option("pixel_vr") == "OW"
            )

        if test == "sign_correction":
            use_j2k_correction = (
                self.transfer_syntax in JPEG2000TransferSyntaxes
                and self.photometric_interpretation in (PI.MONOCHROME1, PI.MONOCHROME2)
                and self.get_option("apply_j2k_sign_correction", False)
            )
            use_jls_correction = (
                self.transfer_syntax in JPEGLSTransferSyntaxes
                and self.pixel_representation == 1
                and self.get_option("apply_jls_sign_correction", False)
            )

            return use_j2k_correction or use_jls_correction

        if test == "shift_correction":
            return (
                self.get_option("correct_unused_bits", False)
                and self.pixel_keyword == "PixelData"
                and self.bits_allocated > self.bits_stored
            )

        raise ValueError(f"Unknown test '{test}'")

    def validate(self) -> None:
        """Validate the decoding options and source buffer (if any)."""
        self._validate_options()
        if self.is_dataset or self.is_buffer:
            self._validate_buffer()

    def _validate_buffer(self) -> None:
        """Validate the supplied buffer data."""
        # Check that the actual length of the pixel data is as expected
        frame_length = self.frame_length(unit="bytes")
        expected = ceil(frame_length * self.number_of_frames)
        actual = len(cast(Buffer, self._src))

        if self.transfer_syntax.is_encapsulated:
            if actual in (expected, expected + expected % 2):
                warn_and_log(
                    "The number of bytes of compressed pixel data matches the "
                    "expected number for uncompressed data - check that the "
                    "transfer syntax has been set correctly"
                )

            return

        # Correct for the trailing NULL byte padding for odd length data
        padded = expected + expected % 2
        if actual < padded:
            if actual != expected:
                raise ValueError(
                    f"The number of bytes of pixel data is less than expected "
                    f"({actual} vs {padded} bytes) - the dataset may be "
                    "corrupted, have an invalid group 0028 element value, or "
                    "the transfer syntax may be incorrect"
                )
        elif actual > padded:
            if self.photometric_interpretation == PI.YBR_FULL_422:
                # PS 3.3, Annex C.7.6.3
                ybr_length = expected // 2 * 3
                if actual >= ybr_length + ybr_length % 2:
                    raise ValueError(
                        "The number of bytes of pixel data is a third larger "
                        f"than expected ({actual} vs {expected} bytes) which "
                        "indicates the set (0028,0004) 'Photometric Interpretation' "
                        "value of 'YBR_FULL_422' is incorrect and may need to be "
                        "changed to either 'RGB' or 'YBR_FULL'"
                    )

            # Determine if there's sufficient padding to contain extra frames
            elif self.get_option("allow_excess_frames", False):
                whole_frames = actual // frame_length
                if whole_frames > self.number_of_frames:
                    warn_and_log(
                        "The number of bytes of pixel data is sufficient to contain "
                        f"{whole_frames} frames which is larger than the given "
                        f"(0028,0008) 'Number of Frames' value of {self.number_of_frames}. "
                        "The returned data will include these extra frames and if it's "
                        "correct then you should update 'Number of Frames' accordingly, "
                        "otherwise pass 'allow_excess_frames=False' to return only "
                        f"the first {self.number_of_frames} frames."
                    )
                    self.set_option("number_of_frames", whole_frames)
                    return

            # PS 3.5, Section 8.1.1
            warn_and_log(
                f"The pixel data is {actual} bytes long, which indicates it "
                f"contains {actual - expected} bytes of excess padding to "
                "be removed"
            )

    def _validate_options(self) -> None:
        """Validate the supplied options to ensure they meet minimum requirements."""
        super()._validate_options()

        # The Extended Offset Table is optional
        if self.extended_offsets and len(self.extended_offsets[0]) != len(
            self.extended_offsets[1]
        ):
            warn_and_log(
                "The number of items in (7FE0,0001) 'Extended Offset Table' and "
                "(7FE0,0002) 'Extended Offset Table Lengths' don't match - the "
                "extended offset table will be ignored"
            )
            self.del_option("extended_offsets")


class Decoder(CoderBase):
    """Factory class for pixel data decoders.

    Every available ``Decoder`` instance in *pydicom* corresponds directly
    to a single DICOM *Transfer Syntax UID*, and provides a  mechanism for
    decoding encoded source data using one or more :doc:`decoding plugins
    </guides/decoding/decoder_plugins>`.

    .. versionadded:: 3.0
    """

    def __init__(self, uid: UID) -> None:
        """Create a new data decoder.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The *Transfer Syntax UID* that the decoder supports.
        """
        super().__init__(uid, decoder=True)

    def as_array(
        self,
        src: "Dataset | Buffer | BinaryIO",
        *,
        index: int | None = None,
        validate: bool = True,
        raw: bool = False,
        decoding_plugin: str = "",
        **kwargs: DecodeOptions,
    ) -> tuple["np.ndarray", dict[str, str | int]]:
        """Return decoded pixel data as :class:`~numpy.ndarray`.

        .. warning::

            This method requires `NumPy <https://numpy.org/>`_ and may require
            the installation of additional packages to perform the actual pixel
            data decoding. See the :doc:`pixel data decompression documentation
            </guides/user/image_data_handlers>` for more information.

        **Processing**

        The following processing operations on the raw pixel data are always
        performed:

        * Natively encoded bit-packed pixel data for a :ref:`bits allocated
          <bits_allocated>` of ``1`` will be unpacked.
        * Natively encoded pixel data with a :ref:`photometric interpretation
          <photometric_interpretation>` of ``"YBR_FULL_422"`` will
          have it's sub-sampling removed.
        * The output array will be reshaped to the specified dimensions.
        * JPEG-LS or JPEG 2000 encoded data whose signedness doesn't match the
          expected :ref:`pixel representation<pixel_representation>` will be
          converted to match.

        If ``raw = False`` (the default) then the following processing operation
        will also be performed:

        * Pixel data with a :ref:`photometric interpretation
          <photometric_interpretation>` of ``"YBR_FULL"`` or
          ``"YBR_FULL_422"`` will be converted to RGB.

        Parameters
        ----------
        src : :class:`~pydicom.dataset.Dataset` | buffer-like | file-like
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
            * :class:`~typing.BinaryIO`: a file-like positioned at the start of
              the pixel data element's value. The position will be returned
              to the starting offset prior to returning the array.

            When `src` is not a :class:`~pydicom.dataset.Dataset` then a number
            of keyword parameters are also required. Please see the
            :doc:`decoding options documentation</guides/decoding/decoder_options>`
            for more information.
        index : int | None, optional
            If ``None`` (default) then return an array containing all the
            frames in the pixel data, otherwise return one containing only
            the frame from the specified `index`, which starts at 0 for the
            first frame.
        raw : bool, optional
            If ``True`` then return the decoded pixel data after only
            minimal processing (see the processing section above). If ``False``
            (default) then additional processing may be applied to convert the
            pixel data to it's most commonly used form (such as converting from
            YCbCr to RGB). To return the raw pixel data with no processing
            whatsoever, use the :meth:`~pydicom.pixels.decoders.base.Decoder.as_buffer`
            method.
        validate : bool, optional
            If ``True`` (default) then validate the supplied decoding options
            and encoded pixel data prior to decoding, otherwise if ``False``
            no validation will be performed.
        decoding_plugin : str, optional
            The name of the decoding plugin to use when decoding compressed
            pixel data. If no `decoding_plugin` is specified (default) then all
            available plugins will be tried and the result from the first successful
            one returned. For information on the available plugins for each
            decoder see the :doc:`API documentation</reference/pixels.decoders>`.
        **kwargs
            Optional keyword parameters for controlling decoding are also
            available, please see the :doc:`decoding options documentation
            </guides/decoding/decoder_options>` for more information.

        Returns
        -------
        numpy.ndarray
            One or more frames of decoded pixel data shaped as:

            * (rows, columns) for single frame, single sample data
            * (rows, columns, samples) for single frame, multi-sample data
            * (frames, rows, columns) for multi-frame, single sample data
            * (frames, rows, columns, samples) for multi-frame, multi-sample data

            The :class:`~numpy.dtype` for the array will have an
            :attr:`~numpy.dtype.itemsize` sufficient to contain pixels of at
            least :ref:`bits allocated<bits_allocated>`.

            A writeable :class:`~numpy.ndarray` is returned by default. For
            native transfer syntaxes with ``view_only=True``, a read-only
            :class:`~numpy.ndarray` will be returned if `src` is immutable.
        dict[str, str | int]
            The :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module element
            values resulting from the decoding process that describe the array.
            See :meth:`DecodeRunner.pixel_properties()
            <pydicom.pixels.decoders.base.DecodeRunner.pixel_properties>` for the
            possible contents.
        """
        if not HAVE_NP:
            raise ImportError(
                "NumPy is required when converting pixel data to an ndarray"
            )

        if index is not None and index < 0:
            raise ValueError("'index' must be greater than or equal to 0")

        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(
            cast(
                dict[str, "DecodeFunction"],
                self._validate_plugins(decoding_plugin),
            ),
        )

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate()

        if self.is_native:
            func = self._as_array_native
            as_writeable = not runner.get_option("view_only", False)
        else:
            func = self._as_array_encapsulated
            as_writeable = True

        as_frame = index is not None
        arr = runner.reshape(func(runner, index), as_frame=as_frame)

        if runner._test_for("sign_correction"):
            arr = _apply_sign_correction(arr, runner)
        elif runner._test_for("shift_correction"):
            arr = _correct_unused_bits(arr, runner)

        overrides: dict[str, str | int] = {}
        if not raw:
            # Processing may give us a new writeable array anyway, so do
            #   it first to avoid an unnecessary ndarray.copy()
            arr, overrides = runner.process(arr)

        arr = arr.copy() if not arr.flags.writeable and as_writeable else arr

        # Multi-sample arrays are always returned *Planar Configuration* 0
        if runner.samples_per_pixel > 1:
            overrides["planar_configuration"] = 0

        pixel_properties = runner.pixel_properties(as_frame=as_frame)
        pixel_properties.update(overrides)

        return arr, pixel_properties

    @staticmethod
    def _as_array_encapsulated(runner: DecodeRunner, index: int | None) -> "np.ndarray":
        """Return compressed and encapsulated pixel data as :class:`~numpy.ndarray`.

        Parameters
        ----------
        runner : pydicom.pixels.decoders.base.DecodeRunner
            The runner with the encoded data and decoding options.
        index : int | None
            The index of the frame to be returned, or ``None`` if all frames
            are to be returned

        Returns
        -------
        numpy.ndarray
            A 1D array containing the pixel data.
        """
        # The initial preallocated array uses an itemsize based off the dataset's
        #   bits allocated value, however each decoded frame may use a smaller
        #   itemsize (such as bits allocated 16 and JPEG with precision 8 only
        #   returning 8-bit data rather than 16-bit)
        # We account for this by interpreting each frame using that decoded size,
        #   inserting it into the preallocated array, then resetting at the end
        #   so the returned image pixel dict matches the array
        original_bits_allocated = runner.bits_allocated
        pixels_per_frame = cast(int, runner.frame_length(unit="pixels"))
        number_of_frames = 1 if index is not None else runner.number_of_frames

        # Preallocate output array
        arr = np.empty(pixels_per_frame * number_of_frames, dtype=runner.pixel_dtype)

        # Return the specified frame only
        if index is not None:
            # The decoding plugin may alter runner.bits_allocated to give a
            #   different dtype itemsize
            arr[:] = np.frombuffer(runner.decode(index=index), dtype=runner.pixel_dtype)
            runner.set_option("bits_allocated", original_bits_allocated)

            return arr

        # Return all frames
        frame_generator = runner.iter_decode()
        for idx in range(runner.number_of_frames):
            frame = next(frame_generator)
            start = idx * pixels_per_frame
            arr[start : start + pixels_per_frame] = np.frombuffer(
                frame, dtype=runner.pixel_dtype
            )

        # Check to see if we have any more frames available
        #   Should only apply to JPEG transfer syntaxes
        if runner.get_option("allow_excess_frames", False):
            excess = []
            original_nr_frames = runner.number_of_frames
            for frame in frame_generator:
                if len(frame) == runner.frame_length(unit="bytes"):
                    excess.append(np.frombuffer(frame, runner.pixel_dtype))
                    runner.set_option("number_of_frames", runner.number_of_frames + 1)

            if excess:
                warn_and_log(
                    f"{len(excess) + original_nr_frames} frames have been found in "
                    "the encapsulated pixel data, which is larger than the given "
                    f"(0028,0008) 'Number of Frames' value of {original_nr_frames}. "
                    "The returned data will include these extra frames and if it's "
                    "correct then you should update 'Number of Frames' accordingly, "
                    "otherwise pass 'allow_excess_frames=False' to return only the "
                    f"first {original_nr_frames} frames."
                )
                arr = np.concatenate([arr, *excess])

        runner.set_option("bits_allocated", original_bits_allocated)

        return arr

    @staticmethod
    def _as_array_native(runner: DecodeRunner, index: int | None) -> "np.ndarray":
        """Return natively encoded pixel data from a buffer-like as
        :class:`~numpy.ndarray`.

        Parameters
        ----------
        runner : pydicom.pixels.decoders.base.DecodeRunner
            The runner with the encoded data and decoding options.
        index : int | None
            The index of the frame to be returned, or ``None`` if all frames
            are to be returned

        Returns
        -------
        numpy.ndarray
            A 1D array containing the pixel data.
        """
        length_bytes = runner.frame_length(unit="bytes")
        length_pixels = int(runner.frame_length(unit="pixels"))
        dtype = runner.pixel_dtype

        src: memoryview | BinaryIO
        if runner.is_dataset or runner.is_buffer:
            src = memoryview(cast(Buffer, runner.src))
            file_offset = 0
            length_source: int | float = len(src)
        else:
            src = cast(BinaryIO, runner.src)
            # Should be the start of the pixel data element's value
            file_offset = src.tell()
            length_source = length_bytes * runner.number_of_frames

        if runner._test_for("be_swap_ow"):
            # Big endian 8-bit data may be encoded as OW
            # For example a 1 x 1 x 3 image will (presumably) be:
            #   b"\x02\x01\x00\x03" instead of b"\x01\x02\x03\x00"
            # Note that the padding byte is displaced, so we need to
            #  swap the bytes pairwise.
            # This will also affect the start and end of individual frames
            if runner.get_option("view_only", False):
                LOGGER.warning(
                    "Unable to return an ndarray that's a view on the "
                    "original buffer for 8-bit pixel data encoded as OW with "
                    "'Explicit VR Big Endian'"
                )

            # Since we are using 8 bit images, frames will always be an integer
            # number of bytes
            length_bytes = cast(int, length_bytes)
            length_source = cast(int, length_source)

            # ndarray.byteswap() creates a new memory object
            if index is not None:
                # Return specified frame only
                start_offset = file_offset + index * length_bytes
                if (start_offset + length_bytes) > file_offset + length_source:
                    raise ValueError(
                        f"There is insufficient pixel data to contain {index + 1} frames"
                    )

                if length_bytes % 2 == 0:
                    # Even length frame: start and end correct
                    frame = runner.get_data(src, start_offset, length_bytes)
                    arr = np.frombuffer(frame, dtype="u2").byteswap()
                    arr = arr.view(dtype)
                else:
                    # Odd length frame
                    # Even index: start correct, end incorrect
                    #   src[start:start + length + 1] -> ... -> arr[:-1]
                    # Odd index: start incorrect, end correct
                    #   src[start - 1:start + length + 1] -> ... -> arr[1:]
                    odd_index = index % 2
                    frame = runner.get_data(
                        src, start_offset - odd_index, length_bytes + 1
                    )
                    arr = np.frombuffer(frame, dtype="u2").byteswap()
                    arr = arr.view(dtype)[odd_index : None if odd_index else -1]
            else:
                # Return all frames
                length_bytes *= runner.number_of_frames
                buffer = runner.get_data(
                    src, file_offset, length_bytes + length_bytes % 2
                )
                arr = np.frombuffer(buffer, dtype="u2").byteswap()
                arr = arr.view(dtype)[:length_bytes]
        else:
            if index is not None:
                start_offset = floor(file_offset + index * length_bytes)
                if (start_offset + length_bytes) > file_offset + length_source:
                    raise ValueError(
                        f"There is insufficient pixel data to contain {index + 1} frames"
                    )

                frame = runner.get_data(src, start_offset, ceil(length_bytes))
                arr = np.frombuffer(frame, dtype=dtype)
            else:
                length_bytes *= runner.number_of_frames

                buffer = runner.get_data(src, file_offset, ceil(length_bytes))
                arr = np.frombuffer(buffer, dtype=dtype)

        # Unpack bit-packed data (if required)
        if runner.bits_allocated == 1:
            if runner.get_option("view_only", False):
                LOGGER.warning(
                    "Unable to return an ndarray that's a view on the "
                    "original buffer for bit-packed pixel data"
                )

            # Number of bits to remove from the start after unpacking in
            bit_offset_start = 0

            if index is None:
                length_pixels *= runner.number_of_frames
            else:
                bit_offset_start = (index * length_pixels) % 8

            unpacked = np.unpackbits(
                arr, bitorder="little", count=ceil(length_bytes) * 8
            )

            # May need to remove bits from the beginning or end if frame
            # boundaries are not byte-aligned
            unpacked = unpacked[bit_offset_start : bit_offset_start + length_pixels]

            return unpacked

        if runner.photometric_interpretation != PI.YBR_FULL_422:
            return arr

        # Expand YBR_FULL_422 (if required)
        if runner.get_option("view_only", False):
            LOGGER.warning(
                "Unable to return an ndarray that's a view on the original "
                "buffer for uncompressed pixel data with a photometric "
                "interpretation of 'YBR_FULL_422'"
            )

        # PS3.3 C.7.6.3.1.2: YBR_FULL_422 data needs to be resampled
        # Y1 Y2 B1 R1 -> Y1 B1 R1 Y2 B1 R1
        out = np.empty(arr.shape[0] // 2 * 3, dtype=dtype)
        out[::6] = arr[::4]  # Y1
        out[3::6] = arr[1::4]  # Y2
        out[1::6], out[4::6] = arr[2::4], arr[2::4]  # B
        out[2::6], out[5::6] = arr[3::4], arr[3::4]  # R

        runner.set_option("photometric_interpretation", PI.YBR_FULL)

        return out

    def as_buffer(
        self,
        src: "Dataset | Buffer | BinaryIO",
        *,
        index: int | None = None,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> tuple[Buffer, dict[str, str | int]]:
        """Return the raw decoded pixel data as a buffer-like.

        .. warning::

            This method should only be used by advanced users who understand the
            intricacies of converting raw decoded DICOM pixel data to a usable
            form. It may also require the installation of additional packages
            to perform the actual pixel data decoding (see the :doc:`pixel data
            decompression documentation</guides/user/image_data_handlers>` for more
            information).

        Parameters
        ----------
        src : :class:`~pydicom.dataset.Dataset` | buffer-like | file-like
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
            * :class:`~typing.BinaryIO`: a file-like positioned at the start of the
              pixel data element's value. The position will be returned
              to the starting offset prior to returning the buffer.

            When `src` is not a :class:`~pydicom.dataset.Dataset` then a number
            of keyword parameters are also required. Please see the
            :doc:`decoding options documentation</guides/decoding/decoder_options>`
            for more information.
        index : int | None, optional
            If ``None`` (default) then return a buffer-like containing all the
            frames in the pixel data, otherwise return one containing only
            the frame from the specified `index`, which starts at 0 for the
            first frame.
        validate : bool, optional
            If ``True`` (default) then validate the supplied decoding options
            and encoded pixel data prior to decoding, otherwise if ``False``
            no validation will be performed.
        decoding_plugin : str, optional
            The name of the decoding plugin to use when decoding compressed
            pixel data. If no `decoding_plugin` is specified (default) then all
            available plugins will be tried and the result from the first successful
            one returned. For information on the available plugins for each
            decoder see the :doc:`API documentation</reference/pixels.decoders>`.
        **kwargs
            Optional keyword parameters for controlling decoding are also
            available, please see the :doc:`decoding options documentation
            </guides/decoding/decoder_options>` for more information.

        Returns
        -------
        bytes | bytearray | memoryview
            One or more frames of raw decoded pixel data.

            For natively encoded pixel data when `src` is a buffer-like the
            same type in `src` will be returned, except if `view_only` is
            ``True`` in which case a :class:`memoryview` on the original
            buffer will be returned instead. If `src` is a file-like then
            :class:`bytes` will always be returned.

            8-bit pixel data encoded as **OW** using *Explicit VR Big Endian* will
            be returned as-is and may need byte-swapping. To facilitate this
            an extra byte before the expected start (for an odd `index`) or after
            the expected end (for an even `index`) is returned if the frame contains
            an odd number of pixels.
        dict[str, str | int]
            The :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module element
            values resulting from the decoding process that describe the
            decoded pixel data. See :meth:`DecodeRunner.pixel_properties()
            <pydicom.pixels.decoders.base.DecodeRunner.pixel_properties>` for the
            possible contents.
        """
        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(
            cast(
                dict[str, "DecodeFunction"],
                self._validate_plugins(decoding_plugin),
            ),
        )

        if validate:
            runner.validate()

        if self.is_native:
            buffer = self._as_buffer_native(runner, index)
        else:
            buffer = self._as_buffer_encapsulated(runner, index)

        return buffer, runner.pixel_properties(as_frame=index is not None)

    @staticmethod
    def _as_buffer_encapsulated(
        runner: DecodeRunner, index: int | None
    ) -> bytes | bytearray:
        """ "Return the raw decoded pixel data as a buffer-like.

        Parameters
        ----------
        runner : pydicom.pixels.decoders.base.DecodeRunner
            The runner with the encoded data and decoding options.
        index : int | None
            The index of the frame to be returned, or ``None`` if all frames
            are to be returned

        Returns
        -------
        bytes | bytearray
            A buffer-like containing the decoded pixel data.
        """

        # Return the specified frame only
        if index is not None:
            frame = runner.decode(index=index)
            length_bytes = runner.frame_length(unit="bytes")
            if (actual := len(frame)) != length_bytes:
                raise ValueError(
                    "Unexpected number of bytes in the decoded frame with index "
                    f"{index} ({actual} bytes actual vs {length_bytes} expected)"
                )

            return frame

        # Return all frames
        frames = []
        bits_allocated = []
        frame_generator = runner.iter_decode()
        for idx in range(runner.number_of_frames):
            frame = next(frame_generator)
            bits_allocated.append(runner.bits_allocated)
            length_bytes = runner.frame_length(unit="bytes")
            if (actual := len(frame)) != length_bytes:
                raise ValueError(
                    "Unexpected number of bytes in the decoded frame with index "
                    f"{idx} ({actual} bytes actual vs {length_bytes} expected)"
                )

            frames.append(frame)

        # Check to see if we have any more frames available
        #   Should only apply to JPEG transfer syntaxes
        if runner.get_option("allow_excess_frames", False):
            excess = []
            original_nr_frames = runner.number_of_frames
            for frame in frame_generator:
                if len(frame) == runner.frame_length(unit="bytes"):
                    excess.append(frame)
                    runner.set_option("number_of_frames", runner.number_of_frames + 1)
                    bits_allocated.append(runner.bits_allocated)

            if excess:
                warn_and_log(
                    f"{len(excess) + len(frames)} frames have been found in the "
                    "encapsulated pixel data, which is larger than the given "
                    f"(0028,0008) 'Number of Frames' value of {original_nr_frames}. "
                    "The returned data will include these extra frames and if it's "
                    "correct then you should update 'Number of Frames' accordingly, "
                    "otherwise pass 'allow_excess_frames=False' to return only the "
                    f"first {original_nr_frames} frames."
                )
                frames.extend(excess)

        # Each frame may have been encoded using a different precision. On
        #   decoding this may result in different container sizes per frame
        #   (such as 7-bit and 12-bit precisions being decoded as 8-bit and
        #   16-bit respectively, even if *Bits Stored* is 12). In that case we
        #   pad to match the largest container size.
        if len(set(bits_allocated)) != 1:
            target = max(bits_allocated)
            target_step = target // 8
            for idx, (actual, frame) in enumerate(zip(bits_allocated, frames)):
                if actual != target:
                    LOGGER.debug(f"Padding frame {idx} from {actual} to {target}-bit")
                    actual_step = actual // 8
                    # Preallocate the new buffer and copy from original to new
                    out = bytearray(len(frame) // actual_step * target_step)
                    for offset in range(actual_step):
                        out[offset::target_step] = frame[offset::actual_step]

                    frames[idx] = out

            runner.set_option("bits_allocated", target)

        return b"".join(b for b in frames)

    @staticmethod
    def _as_buffer_native(runner: DecodeRunner, index: int | None) -> Buffer:
        """ "Return the raw encoded pixel data as a buffer-like.

        Parameters
        ----------
        runner : pydicom.pixels.decoders.base.DecodeRunner
            The runner with the encoded data and decoding options.
        index : int | None
            The index of the frame to be returned, or ``None`` if all frames
            are to be returned

        Returns
        -------
        bytes | bytearray | memoryview
            A buffer-like containing the decoded pixel data. Will return the
            same type as in the buffer containing the pixel data unless
            `view_only` is ``True`` in which case a :class:`memoryview` of the
            original buffer will be returned instead.

        Notes
        -----
        For certain images, those with BitsAllocated=1, multiple frames and
        number of pixels per frame that is not a multiple of 8, it is not
        possible to isolate a buffer to a single frame because frame boundaries
        may occur within the middle a byte. If a single frame is requested (via
        ``index``) for these cases, the buffer returned will consist of the
        smallest set of bytes required to entirely contain the requested frame.
        However, the first and last byte may also contain information on pixel
        values in neighboring frames.
        """
        length_bytes = runner.frame_length(unit="bytes")

        src: Buffer | BinaryIO
        if runner.is_dataset or runner.is_buffer:
            if runner.get_option("view_only", False):
                src = memoryview(cast(Buffer, runner.src))
            else:
                src = cast(Buffer, runner.src)

            file_offset = 0
            length_source: int | float = len(src)
        else:
            src = cast(BinaryIO, runner.src)
            file_offset = src.tell()
            length_source = length_bytes * runner.number_of_frames

        if runner._test_for("be_swap_ow"):

            # Since we are using 8 bit images, frames will always be an integer
            # number of bytes
            length_bytes = cast(int, length_bytes)
            length_source = cast(int, length_source)

            # Big endian 8-bit data encoded as OW
            if index is not None:
                # Return specified frame only
                start_offset = file_offset + index * length_bytes
                if start_offset + length_bytes > file_offset + length_source:
                    raise ValueError(
                        f"There is insufficient pixel data to contain {index + 1} frames"
                    )

                if length_bytes % 2 == 0:
                    # Even length frame: start and end correct
                    return runner.get_data(src, start_offset, length_bytes)

                # Odd length frame
                # Even index: start correct, end incorrect
                #   -> src[start:start + length + 1]
                # Odd index: start incorrect, end correct
                #   -> src[start - 1:start + length + 1]
                return runner.get_data(src, start_offset - index % 2, length_bytes + 1)

            # Return all frames
            length_bytes *= runner.number_of_frames
            return runner.get_data(src, file_offset, length_bytes + length_bytes % 2)

        if index is not None:
            # Return specified frame only
            start_offset = floor(file_offset + index * length_bytes)
            if start_offset + length_bytes > file_offset + length_source:
                raise ValueError(
                    f"There is insufficient pixel data to contain {index + 1} frames"
                )

            return runner.get_data(src, start_offset, ceil(length_bytes))

        # Return all frames
        length_bytes *= runner.number_of_frames
        return runner.get_data(src, file_offset, ceil(length_bytes))

    def iter_array(
        self,
        src: "Dataset | Buffer | BinaryIO",
        *,
        indices: Iterable[int] | None = None,
        raw: bool = False,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> Iterator[tuple["np.ndarray", dict[str, str | int]]]:
        """Yield pixel data frames as :class:`~numpy.ndarray`.

        .. warning::

            This method requires `NumPy <https://numpy.org/>`_ and may require
            the installation of additional packages to perform the actual pixel
            data decoding. See the :doc:`pixel data decompression documentation
            </guides/user/image_data_handlers>` for more information.

        **Processing**

        The following processing operations on the raw pixel data are always
        performed:

        * Natively encoded bit-packed pixel data for a :ref:`bits allocated
          <bits_allocated>` of ``1`` will be unpacked.
        * Natively encoded pixel data with a :ref:`photometric interpretation
          <photometric_interpretation>` of ``"YBR_FULL_422"`` will
          have it's sub-sampling removed.
        * The output array will be reshaped to the specified dimensions.
        * JPEG-LS or JPEG 2000 encoded data whose signedness doesn't match the
          expected :ref:`pixel representation<pixel_representation>` will be
          converted to match.

        If ``raw = False`` (the default) then the following processing operation
        will also be performed:

        * Pixel data with a :ref:`photometric interpretation
          <photometric_interpretation>` of ``"YBR_FULL"`` or
          ``"YBR_FULL_422"`` will be converted to ``"RGB"``.

        Parameters
        ----------
        src : :class:`~pydicom.dataset.Dataset` | buffer-like | file-like
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
            * :class:`~typing.BinaryIO`: a file-like positioned at the start of the
              pixel data element's value. The position will be returned
              to the starting offset only after all frames have been yielded.

            When `src` is not a :class:`~pydicom.dataset.Dataset` then a number
            of keyword parameters are also required. Please see the
            :doc:`decoding options documentation</guides/decoding/decoder_options>`
            for more information.
        indices : Iterable[int] | None, optional
            If ``None`` (default) then iterate through the entire pixel data,
            otherwise only iterate through the frames specified by `indices`.
        raw : bool, optional
            If ``True`` then yield the decoded pixel data after only
            minimal processing (see the processing section above). If ``False``
            (default) then additional processing may be applied to convert the
            pixel data to it's most commonly used form (such as converting from
            YCbCr to RGB). To yield frames of pixel data with no processing
            whatsoever, use the :meth:`~pydicom.pixels.decoders.base.Decoder.iter_buffer`
            method.
        validate : bool, optional
            If ``True`` (default) then validate the supplied decoding options
            and encoded pixel data prior to decoding, otherwise if ``False``
            no validation will be performed.
        decoding_plugin : str, optional
            The name of the decoding plugin to use when decoding compressed
            pixel data. If no `decoding_plugin` is specified (default) then all
            available plugins will be tried and the result from the first successful
            one yielded. For information on the available plugins for each
            decoder see the :doc:`API documentation</reference/pixels.decoders>`.
        **kwargs
            Optional keyword parameters for controlling decoding are also
            available, please see the :doc:`decoding options documentation
            </guides/decoding/decoder_options>` for more information.

        Yields
        ------
        numpy.ndarray
            A single frame of decoded and reshaped pixel data, with shape:

            * (rows, columns) for single sample data
            * (rows, columns, samples) for multi-sample data

            The :class:`~numpy.dtype` for the array will have an
            :attr:`~numpy.dtype.itemsize` sufficient to contain pixels of at
            least :ref:`bits allocated<bits_allocated>`.

            A writeable :class:`~numpy.ndarray` is returned by default. For
            native transfer syntaxes with ``view_only=True`` a read-only
            :class:`~numpy.ndarray` will be yielded if `src` is immutable.
        dict[str, str | int]
            The :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module element
            values resulting from the decoding process that describe the array.
            See :meth:`DecodeRunner.pixel_properties()
            <pydicom.pixels.decoders.base.DecodeRunner.pixel_properties>` for the
            possible contents.
        """
        if not HAVE_NP:
            raise ImportError(
                "NumPy is required when converting pixel data to an ndarray"
            )

        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(
            cast(
                dict[str, "DecodeFunction"],
                self._validate_plugins(decoding_plugin),
            ),
        )

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate()

        if self.is_native:
            func = self._as_array_native
            as_writeable = not runner.get_option("view_only", False)
        else:
            func = self._as_array_encapsulated
            as_writeable = True

        log_warning = True
        if self.is_encapsulated and not indices:
            for frame in runner.iter_decode():
                arr = np.frombuffer(frame, dtype=runner.pixel_dtype)
                arr = runner.reshape(arr, as_frame=True)
                if runner._test_for("sign_correction"):
                    arr = _apply_sign_correction(arr, runner)
                elif runner._test_for("shift_correction"):
                    arr = _correct_unused_bits(arr, runner, log_warning=log_warning)
                    log_warning = False

                overrides: dict[str, str | int] = {}
                if not raw:
                    # Processing may give us a new writeable array anyway, so do
                    #   it first to avoid an unnecessary ndarray.copy()
                    arr, overrides = runner.process(arr)

                arr = arr if arr.flags.writeable else arr.copy()

                # Multi-sample arrays are always returned *Planar Configuration* 0
                if runner.samples_per_pixel > 1:
                    overrides["planar_configuration"] = 0

                pixel_properties = runner.pixel_properties(as_frame=True)
                pixel_properties.update(overrides)

                yield arr, pixel_properties

            return

        indices = indices if indices else range(runner.number_of_frames)
        for index in indices:
            arr = runner.reshape(func(runner, index), as_frame=True)
            if runner._test_for("sign_correction"):
                arr = _apply_sign_correction(arr, runner)
            elif runner._test_for("shift_correction"):
                arr = _correct_unused_bits(arr, runner, log_warning=log_warning)
                log_warning = False

            overrides = {}
            if not raw:
                arr, overrides = runner.process(arr)

            arr = arr.copy() if not arr.flags.writeable and as_writeable else arr

            if runner.samples_per_pixel > 1:
                overrides["planar_configuration"] = 0

            pixel_properties = runner.pixel_properties(as_frame=True)
            pixel_properties.update(overrides)

            yield arr, pixel_properties

    def iter_buffer(
        self,
        src: "Dataset | Buffer | BinaryIO",
        *,
        indices: Iterable[int] | None = None,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> Iterator[tuple[Buffer, dict[str, str | int]]]:
        """Yield raw decoded pixel data frames as a buffer-like.

        .. warning::

            This method should only be used by advanced users who understand the
            intricacies of converting raw decoded DICOM pixel data to a usable
            form. It may also require the installation of additional packages to
            perform the actual pixel data decoding (see the :doc:`pixel data
            decompression documentation</guides/user/image_data_handlers>` for more
            information).

        Parameters
        ----------
        src : :class:`~pydicom.dataset.Dataset` | buffer-like | file-like
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
            * :class:`~typing.BinaryIO`: a file-like positioned at the start of the
              pixel data element's value. The position will be returned
              to the starting offset only after all frames have been yielded.

            When `src` is not a :class:`~pydicom.dataset.Dataset` then a number
            of keyword parameters are also required. Please see the
            :doc:`decoding options documentation</guides/decoding/decoder_options>`
            for more information.
        indices : Iterable[int] | None, optional
            If ``None`` (default) then iterate through the entire pixel data,
            otherwise only iterate through the frames specified by `indices`.
        validate : bool, optional
            If ``True`` (default) then validate the supplied decoding options
            and encoded pixel data prior to decoding, otherwise if ``False``
            no validation will be performed.
        decoding_plugin : str, optional
            The name of the decoding plugin to use when decoding compressed
            pixel data. If no `decoding_plugin` is specified (default) then all
            available plugins will be tried and the result from the first successful
            one yielded. For information on the available plugins for each
            decoder see the :doc:`API documentation</reference/pixels.decoders>`.
        **kwargs
            Optional keyword parameters for controlling decoding are also
            available, please see the :doc:`decoding options documentation
            </guides/decoding/decoder_options>` for more information.

        Yields
        -------
        bytes | bytearray | memoryview
            A single frame of decoded pixel data.

            * For natively encoded pixel data when `src` is a buffer-like the
              same type in `src` will be yielded, except if `view_only` is
              ``True`` in which case a :class:`memoryview` on the original
              buffer will be yielded instead. If `src` is a file-like then
              :class:`bytes` will always be yielded.
            * Encapsulated pixel data will be yielded as :class:`bytearray`.

            8-bit pixel data encoded as **OW** using *Explicit VR Big Endian* will
            be yielded as-is and may need byte-swapping. To facilitate this
            an extra byte before the expected start (for an odd `index`) or after
            the expected end (for an even `index`) is yielded if the frame contains
            an odd number of pixels.
        dict[str, str | int]
            The :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module element
            values resulting from the decoding process that describe the
            decoded frame of pixel data. See :meth:`DecodeRunner.pixel_properties()
            <pydicom.pixels.decoders.base.DecodeRunner.pixel_properties>` for the
            possible contents.
        """
        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(
            cast(
                dict[str, "DecodeFunction"],
                self._validate_plugins(decoding_plugin),
            ),
        )

        if validate:
            runner.validate()

        if self.is_encapsulated and not indices:
            for buffer in runner.iter_decode():
                yield buffer, runner.pixel_properties(as_frame=True)

            return

        if self.is_native:
            func = self._as_buffer_native
        else:
            func = self._as_buffer_encapsulated

        indices = indices if indices else range(runner.number_of_frames)
        for index in indices:
            yield func(runner, index), runner.pixel_properties(as_frame=True)


# Decoder names should be f"{UID.keyword}Decoder"
# Uncompressed transfer syntaxes need no plugins
ImplicitVRLittleEndianDecoder = Decoder(ImplicitVRLittleEndian)
ExplicitVRLittleEndianDecoder = Decoder(ExplicitVRLittleEndian)
ExplicitVRBigEndianDecoder = Decoder(ExplicitVRBigEndian)
DeflatedExplicitVRLittleEndianDecoder = Decoder(DeflatedExplicitVRLittleEndian)

# Compressed transfer syntaxes
JPEGBaseline8BitDecoder = Decoder(JPEGBaseline8Bit)
JPEGBaseline8BitDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pillow", ("pydicom.pixels.decoders.pillow", "_decode_frame")),
    ]
)

JPEGExtended12BitDecoder = Decoder(JPEGExtended12Bit)
JPEGExtended12BitDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pillow", ("pydicom.pixels.decoders.pillow", "_decode_frame")),
    ]
)

JPEGLosslessDecoder = Decoder(JPEGLossless)
JPEGLosslessDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
    ]
)

JPEGLosslessSV1Decoder = Decoder(JPEGLosslessSV1)
JPEGLosslessSV1Decoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
    ]
)

JPEGLSLosslessDecoder = Decoder(JPEGLSLossless)
JPEGLSLosslessDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pyjpegls", ("pydicom.pixels.decoders.pyjpegls", "_decode_frame")),
    ]
)

JPEGLSNearLosslessDecoder = Decoder(JPEGLSNearLossless)
JPEGLSNearLosslessDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pyjpegls", ("pydicom.pixels.decoders.pyjpegls", "_decode_frame")),
    ]
)

JPEG2000LosslessDecoder = Decoder(JPEG2000Lossless)
JPEG2000LosslessDecoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pillow", ("pydicom.pixels.decoders.pillow", "_decode_frame")),
    ]
)

JPEG2000Decoder = Decoder(JPEG2000)
JPEG2000Decoder.add_plugins(
    [
        ("gdcm", ("pydicom.pixels.decoders.gdcm", "_decode_frame")),
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pillow", ("pydicom.pixels.decoders.pillow", "_decode_frame")),
    ]
)

HTJ2KLosslessDecoder = Decoder(HTJ2KLossless)
HTJ2KLosslessDecoder.add_plugin(
    "pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")
)

HTJ2KLosslessRPCLDecoder = Decoder(HTJ2KLosslessRPCL)
HTJ2KLosslessRPCLDecoder.add_plugin(
    "pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")
)

HTJ2KDecoder = Decoder(HTJ2K)
HTJ2KDecoder.add_plugin(
    "pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")
)

RLELosslessDecoder = Decoder(RLELossless)
RLELosslessDecoder.add_plugins(
    [
        ("pylibjpeg", ("pydicom.pixels.decoders.pylibjpeg", "_decode_frame")),
        ("pydicom", ("pydicom.pixels.decoders.rle", "_decode_frame")),
    ]
)


# Available pixel data decoders
_PIXEL_DATA_DECODERS = {
    # UID: (decoder, 'versionadded')
    ImplicitVRLittleEndian: (ImplicitVRLittleEndianDecoder, "3.0"),
    ExplicitVRLittleEndian: (ExplicitVRLittleEndianDecoder, "3.0"),
    DeflatedExplicitVRLittleEndian: (DeflatedExplicitVRLittleEndianDecoder, "3.0"),
    ExplicitVRBigEndian: (ExplicitVRBigEndianDecoder, "3.0"),
    JPEGBaseline8Bit: (JPEGBaseline8BitDecoder, "3.0"),
    JPEGExtended12Bit: (JPEGExtended12BitDecoder, "3.0"),
    JPEGLossless: (JPEGLosslessDecoder, "3.0"),
    JPEGLosslessSV1: (JPEGLosslessSV1Decoder, "3.0"),
    JPEGLSLossless: (JPEGLSLosslessDecoder, "3.0"),
    JPEGLSNearLossless: (JPEGLSNearLosslessDecoder, "3.0"),
    JPEG2000Lossless: (JPEG2000LosslessDecoder, "3.0"),
    JPEG2000: (JPEG2000Decoder, "3.0"),
    HTJ2KLossless: (HTJ2KLosslessDecoder, "3.0"),
    HTJ2KLosslessRPCL: (HTJ2KLosslessRPCLDecoder, "3.0"),
    HTJ2K: (HTJ2KDecoder, "3.0"),
    RLELossless: (RLELosslessDecoder, "3.0"),
}


def _build_decoder_docstrings() -> None:
    """Override the default Decoder docstring."""
    for dec, versionadded in _PIXEL_DATA_DECODERS.values():
        uid = dec.UID
        available = dec._available.keys()
        unavailable = dec._unavailable.keys()

        plugins = list(available) + list(unavailable)

        s = [f"A pixel data decoder for *{uid.name}* - ``{uid}``"]
        s.append("")
        s.append(f".. versionadded:: {versionadded}")
        s.append("")
        if plugins:
            s.append(f"Available decoding plugins: {', '.join(sorted(plugins))}.")
            s.append("")
        s.append(
            "Plugin-specific options are given in the :doc:`decoder  "
            "options documentation</guides/decoding/decoder_options>`."
        )
        s.append("")
        s.append(
            "See the :class:`~pydicom.pixels.decoders.base.Decoder` "
            "reference for instance methods and attributes."
        )
        dec.__doc__ = "\n".join(s)


_build_decoder_docstrings()


def get_decoder(uid: str) -> Decoder:
    """Return the pixel data decoder corresponding to `uid`.

    .. versionadded:: 3.0

    +-----------------------------------------------------------------------------+
    | Supported Transfer Syntaxes                                                 |
    +--------------------------------------+----------------------------+---------+
    | Name                                 | UID                        | Version |
    |                                      |                            | added   |
    +======================================+============================+=========+
    | *Implicit VR Little Endian*          | 1.2.840.10008.1.2          | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Explicit VR Little Endian*          | 1.2.840.10008.1.2.1        | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Deflated Explicit VR Little Endian* | 1.2.840.10008.1.2.1.2.1.99 | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Explicit VR Big Endian*             | 1.2.840.10008.1.2.2        | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG Baseline 8-bit*                | 1.2.840.10008.1.2.4.50     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG Extended 12-bit*               | 1.2.840.10008.1.2.4.51     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG Lossless P14*                  | 1.2.840.10008.1.2.4.57     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG Lossless SV1*                  | 1.2.840.10008.1.2.4.70     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG-LS Lossless*                   | 1.2.840.10008.1.2.4.80     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG-LS Near Lossless*              | 1.2.840.10008.1.2.4.81     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG2000 Lossless*                  | 1.2.840.10008.1.2.4.90     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *JPEG2000*                           | 1.2.840.10008.1.2.4.91     | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *HTJ2K Lossless*                     | 1.2.840.10008.1.2.4.201    | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *HTJ2K Lossless RPCL*                | 1.2.840.10008.1.2.4.202    | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *HTJ2K*                              | 1.2.840.10008.1.2.4.203    | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *RLE Lossless*                       | 1.2.840.10008.1.2.5        | 3.0     |
    +--------------------------------------+----------------------------+---------+
    """
    uid = UID(uid)
    try:
        return _PIXEL_DATA_DECODERS[uid][0]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data decoders have been implemented for '{uid.name}'"
        )
