# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Pixel data decoding."""

from collections.abc import Callable, Iterator, Iterable
from importlib import import_module
import logging
from sys import byteorder
from typing import Any, TypedDict

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import config
from pydicom.dataset import Dataset
from pydicom.encaps import get_frame, generate_frames
from pydicom.misc import warn_and_log
from pydicom.pixels.enums import PhotometricInterpretation as PI
from pydicom.pixel_data_handlers.util import convert_color_space
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    RLELossless,
    UID,
)


LOGGER = logging.getLogger(__name__)


Buffer = bytes | bytearray | memoryview


class DecodeOptions(TypedDict, total=False):
    """Options accepted by DecodeRunner and decoding plugins"""

    ## Pixel data description options
    # Required
    bits_allocated: int
    bits_stored: int
    columns: int
    number_of_frames: int
    photometric_interpretation: str
    pixel_keyword: str
    rows: int
    samples_per_pixel: int
    transfer_syntax_uid: UID

    # Conditionally required
    # Required if `pixel_keyword` is "PixelData"
    pixel_representation: int
    # Required if native transfer syntax and samples_per_pixel > 1
    planar_configuration: int

    # Optional
    # The Extended Offset Table values - used with encapsulated transfer syntaxes
    extended_offsets: tuple[bytes, bytes] | tuple[list[int], list[int]]
    # The VR used for the pixel data - may be used with Explicit VR Big Endian
    pixel_vr: str

    ## Native transfer syntax decoding options
    # Return/yield a view of the original buffer where possible
    view_only: bool
    # (ndarray only) Force byte swapping on 8-bit values encoded as OW
    be_swap_ow: bool

    ## RLE decoding options
    # pydicom plugin
    # Segment ordering ">" for big endian (default) or "<" for little endian
    rle_segment_order: str

    ## Processing options (ndarray only)
    as_rgb: bool  # Make best effort to return RGB output
    force_rgb: bool  # Force YBR to RGB conversion
    force_ybr: bool  # Force RGB to YBR conversion


DecodeFunction = Callable[[bytes, DecodeOptions], bytes | bytearray]


class DecodeRunner:
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
        self._src: Buffer
        self._src_type: str
        self._opts: DecodeOptions = {
            "transfer_syntax_uid": tsyntax,
            "as_rgb": True,
        }
        self._decoders: dict[str, DecodeFunction] = {}
        self._previous: tuple[str, DecodeFunction]

        if self.transfer_syntax.is_encapsulated:
            self.set_option("pixel_keyword", "PixelData")
        else:
            self.set_option("view_only", False)

    @property
    def bits_allocated(self) -> int:
        """Return the expected number of bits allocated used by the data."""
        if (value := self._opts.get("bits_allocated", None)) is not None:
            return value

        raise AttributeError("No value for 'bits_allocated' has been set")

    @property
    def bits_stored(self) -> int:
        """Return the expected number of bits stored used by the data."""
        if (value := self._opts.get("bits_stored", None)) is not None:
            return value

        raise AttributeError("No value for 'bits_stored' has been set")

    @property
    def columns(self) -> int:
        """Return the expected number of columns in the data."""
        if (value := self._opts.get("columns", None)) is not None:
            return value

        raise AttributeError("No value for 'columns' has been set")

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
                frame = func(src, self.options)

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

    def del_option(self, name: str) -> None:
        """Delete option `name` from the runner."""
        if name in ("transfer_syntax_uid", "pixel_keyword"):
            raise ValueError(f"Deleting '{name}' is not allowed")

        self._opts.pop(name, None)  # type: ignore[misc]

    @property
    def extended_offsets(
        self,
    ) -> tuple[list[int], list[int]] | tuple[bytes, bytes] | None:
        """Return the extended offsets table and lengths

        Returns
        -------
        tuple[list[int], list[int]] | tuple[bytes, bytes] | None
            Returns the extended offsets and lengths as either lists of int
            or their equivalent encoded values, or ``None`` if no extended
            offsets have been set.
        """
        return self._opts.get("extended_offsets", None)

    def frame_length(self, unit: str = "bytes") -> int:
        """Return the expected length (in number of bytes or pixels) of each
        frame of pixel data.

        Parameters
        ----------
        unit: str, optional
            If ``"bytes"`` then returns the expected length of the pixel data
            in whole bytes and NOT including an odd length trailing NULL
            padding byte. If ``"pixels"`` then returns the expected length of
            the pixel data in terms of the total number of pixels (default
            ``"bytes"``).

        Returns
        -------
        int
            The expected length of a single frame of pixel data in either
            whole bytes or pixels, excluding the NULL trailing padding byte
            for odd length data.
        """
        length = self.rows * self.columns * self.samples_per_pixel

        if unit == "pixels":
            return length

        # Correct for the number of bytes per pixel
        if self.bits_allocated == 1:
            # Determine the nearest whole number of bytes needed to contain
            #   1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits, which
            #   are packed into 12.5 -> 13 bytes
            length = length // 8 + (length % 8 > 0)
        else:
            length *= self.bits_allocated // 8

        # DICOM Standard, Part 4, Annex C.7.6.3.1.2 - native only
        if (
            self.photometric_interpretation == PI.YBR_FULL_422
            and not self.transfer_syntax.is_encapsulated
        ):
            length = length // 3 * 2

        return length

    def get_option(self, name: str, default: Any = None) -> Any:
        """Return the value of the option `name`."""
        return self._opts.get(name, default)

    def iter_decode(self) -> Iterator[bytes | bytearray]:
        """Yield decoded frames from the encoded pixel data."""
        # For encapsulated data `self.src` should not be memoryview as doing so
        #   will create a duplicate object in memory by `generate_frames`
        # May yield more frames than `number_of_frames` for JPEG!
        encoded_frames = generate_frames(
            self.src,
            number_of_frames=self.number_of_frames,
            extended_offsets=self.extended_offsets,
        )
        for index, src in enumerate(encoded_frames):
            # Try the previously successful decoder first (if available)
            name, func = getattr(self, "_previous", (None, None))
            if func:
                try:
                    yield func(src, self.options)
                    continue
                except Exception:
                    LOGGER.warning(
                        f"The decoding plugin '{name}' failed to decode the "
                        f"frame at index {index}"
                    )

            # Otherwise try all decoders
            yield self._decode_frame(src)

    @property
    def number_of_frames(self) -> int:
        """Return the expected number of frames in the data."""
        if (value := self._opts.get("number_of_frames", None)) is not None:
            return value

        raise AttributeError("No value for 'number_of_frames' has been set")

    @property
    def options(self) -> DecodeOptions:
        """Return a reference to the runner's decoding options dict."""
        return self._opts

    @property
    def photometric_interpretation(self) -> str:
        """Return the expected photometric interpretation of the data."""
        if (value := self._opts.get("photometric_interpretation", None)) is not None:
            return value

        raise AttributeError("No value for 'photometric_interpretation' has been set")

    @property
    def pixel_dtype(self) -> "np.dtype":
        """Return a :class:`numpy.dtype` suitable for containing the decoded
        pixel data.
        """
        if not HAVE_NP:
            raise ImportError("NumPy is required for 'DecodeRunner.pixel_dtype'")

        dtype: "np.dtype"
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
        if self.transfer_syntax.is_little_endian != (byteorder == "little"):
            # 'S' swap from current to opposite
            dtype = dtype.newbyteorder("S")

        return dtype

    @property
    def pixel_keyword(self) -> str:
        """Return the expected pixel keyword of the data.

        Returns
        -------
        str
            One of ``"PixelData"``, ``"FloatPixelData"``, ``"DoubleFloatPixelData"``
        """
        if (value := self._opts.get("pixel_keyword", None)) is not None:
            return value

        raise AttributeError("No value for 'pixel_keyword' has been set")

    @property
    def pixel_representation(self) -> int:
        """Return the expected pixel representation of the data."""
        if (value := self._opts.get("pixel_representation", None)) is not None:
            return value

        raise AttributeError("No value for 'pixel_representation' has been set")

    @property
    def planar_configuration(self) -> int:
        """Return the expected planar configuration of the data."""
        # Only required when number of samples is more than 1
        # Uncompressed may be either 0 or 1
        if (value := self._opts.get("planar_configuration", None)) is not None:
            return value

        # Planar configuration is not relevant for compressed syntaxes
        if self.transfer_syntax.is_compressed:
            return 0

        raise AttributeError("No value for 'planar_configuration' has been set")

    def process(self, arr: "np.ndarray") -> "np.ndarray":
        """Return `arr` after applying zero or more processing operations.

        Returns
        -------
        numpy.ndarray
            The array with the applied processing.
        """
        # Color space conversions
        # If force_ybr then always do conversion (ignore as_rgb)
        force_ybr = self.get_option("force_ybr", False)
        force_rgb = self.get_option("force_rgb", False)
        if force_ybr and force_rgb:
            raise ValueError("'force_ybr' and 'force_rgb' cannot both be True")

        to_rgb = (
            "YBR" in self.photometric_interpretation
            and self.get_option("as_rgb", False)
        ) or force_rgb

        if not arr.flags.writeable and (to_rgb or force_ybr):
            if self.get_option("view_only", False):
                LOGGER.warning(
                    "Unable to return an ndarray that's a view on the original "
                    "buffer if applying a color space conversion"
                )

            arr = arr.copy()

        if force_ybr:
            arr = convert_color_space(arr, PI.RGB, PI.YBR_FULL)
            self.set_option("photometric_interpretation", PI.YBR_FULL)
        elif to_rgb:
            arr = convert_color_space(arr, PI.YBR_FULL, PI.RGB)
            self.set_option("photometric_interpretation", PI.RGB)

        return arr

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

            * (rows, columns) for single frame, single plane data
            * (rows, columns, planes) for single frame, multi-plane data
            * (frames, rows, columns) for multi-frame, single plane data
            * (frames, rows, columns, planes) for multi-frame, multi-plane data
        """
        number_of_frames = self.number_of_frames
        samples_per_pixel = self.samples_per_pixel
        rows = self.rows
        columns = self.columns

        if not as_frame and number_of_frames > 1:
            # Multi-frame, single plane
            if samples_per_pixel == 1:
                return arr.reshape(number_of_frames, rows, columns)

            # Multi-frame, multiple planes, planar configuration 0
            if self.planar_configuration == 0:
                return arr.reshape(number_of_frames, rows, columns, samples_per_pixel)

            # Multi-frame, multiple planes, planar configuration 1
            arr = arr.reshape(number_of_frames, samples_per_pixel, rows, columns)
            return arr.transpose(0, 2, 3, 1)

        # Single frame, single plane
        if samples_per_pixel == 1:
            return arr.reshape(rows, columns)

        # Single frame, multiple planes, planar configuration 0
        if self.planar_configuration == 0:
            return arr.reshape(rows, columns, samples_per_pixel)

        # Single frame, multiple planes, planar configuration 1
        arr = arr.reshape(samples_per_pixel, rows, columns)
        return arr.transpose(1, 2, 0)

    @property
    def rows(self) -> int:
        """Return the expected number of rows in the data."""
        if (value := self._opts.get("rows", None)) is not None:
            return value

        raise AttributeError("No value for 'rows' has been set")

    @property
    def samples_per_pixel(self) -> int:
        """Return the expected number of samples per pixel in the data."""
        if (value := self._opts.get("samples_per_pixel", None)) is not None:
            return value

        raise AttributeError("No value for 'samples_per_pixel' has been set")

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

    def set_source(self, src: Buffer | Dataset) -> None:
        """Set the pixel data to be decoded.

        Parameters
        ----------
        src : bytes | bytearray | memoryview | pydicom.dataset.Dataset
            If a buffer-like then the encoded pixel data, otherwise the
            :class:`~pydicom.dataset.Dataset` containing the pixel data and
            associated group ``0x0028`` elements.
        """
        if isinstance(src, Dataset):
            self._set_options_ds(src)
            self._src = src[self.pixel_keyword].value
        else:
            self._src = src

    def set_option(self, name: str, value: Any) -> None:
        """Set a decoding option.

        Parameters
        ----------
        name : str
            The name of the option to be set.
        value : Any
            The value of the option.
        """
        if name == "number_of_frames":
            value = int(value) if isinstance(value, str) else value
            if value in (None, 0):
                value = 1
        elif name == "photometric_interpretation":
            if value == "PALETTE COLOR":
                value = PI.PALETTE_COLOR
            try:
                value = PI[value]
            except KeyError:
                pass

        self._opts[name] = value  # type: ignore[literal-required]

    def set_options(self, **kwargs: DecodeOptions) -> None:
        """Set decoding options.

        Parameters
        ----------
        kwargs : dict[str, Any]
            A dictionary containing the options as ``{name: value}``, where
            `name` is the name of the option and `value` is it's value.
        """
        for name, value in kwargs.items():
            self.set_option(name, value)

    def _set_options_ds(self, ds: "Dataset") -> None:
        """Set decoding options using a dataset.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to use.
        """
        file_meta = getattr(ds, "file_meta", {})
        if tsyntax := file_meta.get("TransferSyntaxUID", None):
            if tsyntax != self.transfer_syntax:
                raise ValueError(
                    f"The dataset's transfer syntax '{tsyntax.name}' doesn't "
                    "match the pixel data decoder"
                )

        self.set_option("bits_allocated", ds.BitsAllocated)  # US
        self.set_option("bits_stored", ds.BitsStored)  # US
        self.set_option("columns", ds.Columns)  # US
        self.set_option("number_of_frames", ds.get("NumberOfFrames", 1))  # IS
        self.set_option(
            "photometric_interpretation", ds.PhotometricInterpretation
        )  # CS
        self.set_option("rows", ds.Rows)  # US
        self.set_option("samples_per_pixel", ds.SamplesPerPixel)  # US

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

        if px_keyword[0] == "PixelData":
            self.set_option("pixel_representation", ds.PixelRepresentation)
        else:
            self.del_option("pixel_representation")

        if self.samples_per_pixel > 1:
            self.set_option("planar_configuration", ds.PlanarConfiguration)  # US
        else:
            self.del_option("planar_configuration")

        # Encapsulation - Extended Offset Table
        if "ExtendedOffsetTable" in ds and "ExtendedOffsetTableLengths" in ds:
            self.set_option(
                "extended_offsets",
                (ds.ExtendedOffsetTable, ds.ExtendedOffsetTableLengths),
            )
        else:
            self.del_option("extended_offsets")

    @property
    def src(self) -> Buffer:
        """Return the buffer containing the encoded pixel data."""
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

    def test_for(self, test: str) -> bool:
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

        raise ValueError(f"Unknown test '{test}'")

    @property
    def transfer_syntax(self) -> UID:
        """Return the expected transfer syntax corresponding to the data."""
        return self._opts["transfer_syntax_uid"]

    def validate_buffer(self) -> None:
        """Validate the supplied buffer data."""
        # Check that the actual length of the pixel data is as expected
        expected = self.frame_length(unit="bytes") * self.number_of_frames
        actual = len(self._src)

        if self.transfer_syntax.is_encapsulated:
            if actual >= expected:
                warn_and_log(
                    "The number of bytes of compressed pixel data matches the "
                    "expected number for uncompressed data - check you have "
                    "set the correct transfer syntax"
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
                        "indicates the set photometric interpretation "
                        "'YBR_FULL_422' is incorrect"
                    )

            # PS 3.5, Section 8.1.1
            warn_and_log(
                f"The pixel data is {actual} bytes long, which indicates it "
                f"contains {actual - expected} bytes of excess padding to "
                "be removed"
            )

    def validate_options(self) -> None:
        """Validate the supplied options to ensure they meet minimum requirements."""
        # Minimum required
        required_keys = [
            "bits_allocated",
            "bits_stored",
            "columns",
            "number_of_frames",
            "photometric_interpretation",
            "pixel_keyword",
            "rows",
            "samples_per_pixel",
        ]
        missing = [k for k in required_keys if k not in self._opts]
        if missing:
            raise AttributeError(f"Missing expected options: {', '.join(missing)}")

        if not 1 <= self.bits_allocated <= 64:
            raise ValueError(
                f"A bits allocated value of '{self.bits_allocated}' is invalid, "
                "it must be in the range (1, 64)"
            )

        if self.bits_allocated != 1 and self.bits_allocated % 8:
            raise ValueError(
                f"A bits allocated value of '{self.bits_allocated}' is invalid, "
                "it must be 1 or a multiple of 8"
            )

        if not 1 <= self.bits_stored <= self.bits_allocated <= 64:
            raise ValueError(
                f"A bits stored value of '{self.bits_stored}' is invalid, it "
                "must be in the range (1, 64) and no greater than the bits "
                f"allocated value of {self.bits_allocated}"
            )

        if not 0 < self.columns <= 2**16 - 1:
            raise ValueError(
                f"A columns value of '{self.columns}' is invalid, it must be in "
                "the range (1, 65535)"
            )

        if self.number_of_frames < 1:
            raise ValueError(
                f"A number of frames value of '{self.number_of_frames}' is "
                "invalid, it must be greater than or equal to 1"
            )

        try:
            PI[self.photometric_interpretation]
        except KeyError:
            if self.photometric_interpretation != "PALETTE COLOR":
                raise ValueError(
                    f"Unknown photometric interpretation '{self.photometric_interpretation}'"
                )

        if self.pixel_keyword not in (
            "PixelData",
            "FloatPixelData",
            "DoubleFloatPixelData",
        ):
            raise ValueError(f"Unknown pixel data keyword '{self.pixel_keyword}'")

        if self.pixel_keyword == "PixelData":
            if self.get_option("pixel_representation") is None:
                raise AttributeError("Missing expected option: pixel_representation")

            if self.pixel_representation not in (0, 1):
                raise ValueError(
                    f"A pixel representation value of '{self.pixel_representation}' "
                    "is invalid, it must be 0 or 1"
                )

        if not 0 < self.rows <= 2**16 - 1:
            raise ValueError(
                f"A rows value of '{self.rows}' is invalid, it must be in the "
                "range (1, 65535)"
            )

        if self.samples_per_pixel not in (1, 3):
            raise ValueError(
                f"A samples per pixel value of '{self.samples_per_pixel}' is "
                "invalid, it must be 1 or 3"
            )

        if self.samples_per_pixel == 3:
            if self.get_option("planar_configuration") is None:
                raise AttributeError("Missing expected option: planar_configuration")

            if self.planar_configuration not in (0, 1):
                raise ValueError(
                    f"A planar configuration value of '{self.planar_configuration}' "
                    "is invalid, it must be 0 or 1"
                )

        if self.extended_offsets:
            if len(self.extended_offsets[0]) != len(self.extended_offsets[1]):
                raise ValueError(
                    "There must be an equal number of extended offsets and offset lengths"
                )


class Decoder:
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
        # The *Transfer Syntax UID* of the encoded data
        self._uid = uid
        # Available decoding plugins
        self._available: dict[str, Callable] = {}
        # Unavailable decoding plugins - missing dependencies or other reason
        self._unavailable: dict[str, tuple[str, ...]] = {}

    def add_plugin(self, label: str, import_path: tuple[str, str]) -> None:
        """Add a decoding plugin to the decoder.

        The requirements for decoding plugins are available
        :doc:`here</guides/decoding/decoder_plugins>`.

        .. warning::

            This method is not thread-safe.

        Parameters
        ----------
        label : str
            The label to use for the plugin, should be unique for the decoder.
        import_path : tuple[str, str]
            The module import path and the decoding function's name (e.g.
            ``('pydicom.pixels.decoders.pylibjpeg', 'decode_pixel_data')``).

        Raises
        ------
        ModuleNotFoundError
            If the module import path is incorrect or unavailable.
        AttributeError
            If the plugin's decoding function, ``is_available()`` or
            ``DECODER_DEPENDENCIES`` aren't found in the module.
        ValueError
            If the plugin doesn't support the decoder's UID.
        """
        if label in self._available or label in self._unavailable:
            raise ValueError(f"'{self.name}' already has a plugin named '{label}'")

        module = import_module(import_path[0])

        # `is_available(UID)` is required for plugins
        if module.is_available(self.UID):
            self._available[label] = getattr(module, import_path[1])
        else:
            # `DECODER_DEPENDENCIES[UID]` is required for plugins
            msg = module.DECODER_DEPENDENCIES.get(
                self.UID,
                f"Plugin '{label}' does not support '{self.UID.name}'",
            )
            self._unavailable[label] = msg

    def as_array(
        self,
        src: Buffer | Dataset,
        *,
        index: int | None = None,
        validate: bool = True,
        raw: bool = False,
        decoding_plugin: str = "",
        **kwargs: DecodeOptions,
    ) -> "np.ndarray":
        """Return decoded pixel data as :class:`~numpy.ndarray`.

        .. warning::

            This method requires `NumPy <https://numpy.org/>`_

        **Processing**

        The following processing operations on the raw pixel data are always
        performed:

        * Natively encoded bit-packed pixel data for a :ref:`bits allocated
          <glossary_bits_allocated>` of ``1`` will be unpacked.
        * Natively encoded pixel data with a :ref:`photometric interpretation
          <glossary_photometric_interpretation>` of ``"YBR_FULL_422"`` will
          have it's sub-sampling removed.
        * The output array will be reshaped to the specified dimensions.

        If ``raw = False`` (the default) then the following processing operation
        will also be performed:

        * Pixel data with a :ref:`photometric interpretation
          <glossary_photometric_interpretation>` of ``"YBR_FULL"`` or
          ``"YBR_FULL_422"`` will be converted to ``"RGB"``.

        Parameters
        ----------
        src : buffer-like | :class:`~pydicom.dataset.Dataset`
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
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
            The following keyword parameters are required when `src` is not
            a :class:`~pydicom.dataset.Dataset`, or may be used to override the
            corresponding element values when `src` is a
            :class:`~pydicom.dataset.Dataset`:

            * `rows`: :class:`int` - the number of :ref:`rows<glossary_rows>`
              of pixels in `src`, maximum 65535.
            * `columns`: :class:`int` - the number of :ref:`columns
              <glossary_columns>` of pixels in `src`, maximum 65535.
            * `number_of_frames`: :class:`int` - the :ref:`number of frames
              <glossary_number_of_frames>` in `src`, minimum 1.
            * `samples_per_pixel`: :class:`int` - the number of :ref:`samples
              per pixel<glossary_samples_per_pixel>` in `src`, should be 1 or 3.
            * `bits_allocated`: :class:`int` - the number of :ref:`bits used
              to contain<glossary_bits_allocated>` each pixel, should be 1
              or a multiple of 8.
            * `bits_stored`: :class:`int` - the number of :ref:`bits actually
              used<glossary_bits_stored>` per pixel. For example, `src` might
              have 16-bits allocated (range 0 to 65535) but only contain 12-bit
              pixel values (range 0 to 4095).
            * `photometric_interpretation`: :class:`str` - the :ref:`color
              space<glossary_photometric_interpretation>` of the *encoded*
              pixel data, such as ``"YBR_FULL"``.

            The following keyword parameters are conditionally required:

            * `planar_configuration`: :class:`int` - required for native
              (uncompressed) transfer syntaxes when `samples_per_pixel` > 1,
              this is whether the pixel data is :ref:`color-by-plane or
              color-by-pixel<glossary_planar_configuration>`. ``0``
              for color-by-pixel, ``1`` for color-by-plane.
            * `pixel_keyword`: :class:`str` - required for native
              (uncompressed) transfer syntaxes, one of ``"PixelData"``,
              ``"FloatPixelData"``, ``"DoubleFloatPixelData"``.
            * `pixel_representation`: :class:`int` - required when
              `pixel_keyword` is ``"PixelData"``, this is the :ref:`type of pixel
              values<glossary_pixel_representation>`, ``0`` for unsigned integers,
              ``1`` for signed.

            The following options may be used with any transfer syntax:

            * `as_rgb`: :class:`bool` - if ``True`` (default) then convert pixel
              data with a YCbCr :ref:`photometric interpretation
              <glossary_photometric_interpretation>` such as ``"YBR_FULL_422"``
              to RGB.
            * `force_rgb`: :class:`bool` - if ``True`` then force a YCbCr to RGB
              color space conversion on the array (default ``False``).
            * `force_ybr`: :class:`bool` - if ``True`` then force an RGB to YCbCr
              color space conversion on the array (default ``False``).

            The following options may be used with native (uncompressed)
            transfer syntaxes:

            * `view_only`: :class:`bool` - if ``True`` then make a best effort
              attempt to return an :class:`~numpy.ndarray` that's a `view
              <https://numpy.org/doc/stable/user/basics.copies.html#view>`_
              on the original buffer (default ``False``).

            Options for the decoding plugin(s) may also be supplied. See the
            :doc:`decoding plugin options </guides/decoding/decoder_plugin_options>`
            for more information.

        Returns
        -------
        numpy.ndarray
            The decoded and reshaped pixel data, with shape:

            * (rows, columns) for single frame, single plane data
            * (rows, columns, planes) for single frame, multi-plane data
            * (frames, rows, columns) for multi-frame, single plane data
            * (frames, rows, columns, planes) for multi-frame, multi-plane data

            A writeable :class:`~numpy.ndarray` is returned by default. For
            native transfer syntaxes with ``view_only=True`` a read-only
            :class:`~numpy.ndarray` will be returned if `src` is immutable.
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
        runner.set_decoders(self._validate_decoders(decoding_plugin))

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate_options()
            runner.validate_buffer()

        if self.is_native:
            func = self._as_array_native
            as_writeable = not runner.get_option("view_only", False)
        else:
            func = self._as_array_encapsulated
            as_writeable = True

        arr = runner.reshape(
            func(runner, index),
            as_frame=False if index is None else True,
        )

        if raw:
            return arr.copy() if not arr.flags.writeable and as_writeable else arr

        # Processing may give us a new writeable array anyway, so do
        #   it first to avoid an unnecessary ndarray.copy()
        arr = runner.process(arr)

        return arr.copy() if not arr.flags.writeable and as_writeable else arr

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
        dtype = runner.pixel_dtype

        # Return the specified frame only
        if index is not None:
            return np.frombuffer(runner.decode(index=index), dtype=dtype)

        # Return all frames
        # Preallocate container array for the frames
        bytes_per_frame = runner.frame_length(unit="bytes")
        pixels_per_frame = runner.frame_length(unit="pixels")
        arr = np.empty(pixels_per_frame * runner.number_of_frames, dtype=dtype)
        frame_generator = runner.iter_decode()
        for idx in range(runner.number_of_frames):
            frame = next(frame_generator)
            start = idx * pixels_per_frame
            arr[start : start + pixels_per_frame] = np.frombuffer(frame, dtype=dtype)

        # Check to see if we have any more frames available
        #   Should only apply to JPEG transfer syntaxes
        excess = []
        for frame in frame_generator:
            if len(frame) == bytes_per_frame:
                excess.append(np.frombuffer(frame, dtype))
                runner.set_option("number_of_frames", runner.number_of_frames + 1)

        if excess:
            warn_and_log(
                "More frames have been found in the encapsulated pixel data "
                "than expected from the supplied number of frames"
            )
            arr = np.concatenate([arr, *excess])

        return arr

    @staticmethod
    def _as_array_native(runner: DecodeRunner, index: int | None) -> "np.ndarray":
        """Return natively encoded pixel data as :class:`~numpy.ndarray`.

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
        dtype = runner.pixel_dtype

        with memoryview(runner.src) as src:
            if runner.test_for("be_swap_ow"):
                # Big endian 8-bit data may be encoded as OW
                # For example a 1 x 1 x 3 image will (presumably) be:
                #   b"\x02\x01\0x00\x03" instead of b"\x01\x02\x03\x00"
                # Note that the padding byte is displaced, so we need to
                #  swap the bytes pairwise.
                # This will also affect the start and end of individual frames

                if runner.get_option("view_only", False):
                    LOGGER.warning(
                        "Unable to return an ndarray that's a view on the "
                        "original buffer for 8-bit pixel data encoded as OW with "
                        "'Explicit VR Big Endian'"
                    )

                # ndarray.byteswap() creates a new memory object
                if index is not None:
                    # Return specified frame only
                    start_offset = index * length_bytes
                    if (end_offset := start_offset + length_bytes) > len(src):
                        raise ValueError(
                            f"There is insufficient pixel data to contain {index + 1} frames"
                        )

                    if length_bytes % 2 == 0:
                        # Even length frame: start and end correct
                        frame = src[start_offset:end_offset]
                        arr = np.frombuffer(frame, dtype="u2").byteswap()
                        arr = arr.view(dtype)
                    elif index % 2 == 0:
                        # Odd length frame, even index: start correct, end incorrect
                        frame = src[start_offset : end_offset + 1]
                        arr = np.frombuffer(frame, dtype="u2").byteswap()
                        arr = arr.view(dtype)[:-1]
                    else:
                        # Odd length frame, odd index: start incorrect, end correct
                        frame = src[start_offset - 1 : end_offset]
                        arr = np.frombuffer(frame, dtype="u2").byteswap()
                        arr = arr.view(dtype)[1:]
                else:
                    # Return all frames
                    length_bytes *= runner.number_of_frames
                    arr = np.frombuffer(src, dtype="u2").byteswap()
                    arr = arr.view(dtype)[:length_bytes]
            else:
                if index is not None:
                    start_offset = index * length_bytes
                    if (end_offset := start_offset + length_bytes) > len(src):
                        raise ValueError(
                            f"There is insufficient pixel data to contain {index + 1} frames"
                        )

                    arr = np.frombuffer(src[start_offset:end_offset], dtype=dtype)
                else:
                    length_bytes *= runner.number_of_frames
                    arr = np.frombuffer(src[:length_bytes], dtype=dtype)

        # Unpack bit-packed data (if required)
        if runner.bits_allocated == 1:
            if runner.get_option("view_only", False):
                LOGGER.warning(
                    "Unable to return an ndarray that's a view on the "
                    "original buffer for bit-packed pixel data"
                )

            length_pixels = runner.frame_length(unit="pixels")
            if index is None:
                length_pixels *= runner.number_of_frames

            return np.unpackbits(arr, bitorder="little", count=length_pixels)

        # Expand YBR_FULL_422 (if required)
        if runner.photometric_interpretation == PI.YBR_FULL_422:
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

        return arr

    def as_buffer(
        self,
        src: Buffer | Dataset,
        *,
        index: int | None = None,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> Buffer:
        """Return the raw decoded pixel data as a buffer-like.

        Parameters
        ----------
        src : buffer-like | :class:`~pydicom.dataset.Dataset`
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
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
            The following keyword parameters are required when `src` is not
            a :class:`~pydicom.dataset.Dataset`, or may be used to override the
            corresponding element values when `src` is a
            :class:`~pydicom.dataset.Dataset`:

            * `rows`: :class:`int` - the number of :ref:`rows<glossary_rows>`
              of pixels in `src`, maximum 65535.
            * `columns`: :class:`int` - the number of :ref:`columns
              <glossary_columns>` of pixels in `src`, maximum 65535.
            * `number_of_frames`: :class:`int` - the :ref:`number of frames
              <glossary_number_of_frames>` in `src`, minimum 1.
            * `samples_per_pixel`: :class:`int` - the number of :ref:`samples
              per pixel<glossary_samples_per_pixel>` in `src`, should be 1 or 3.
            * `bits_allocated`: :class:`int` - the number of :ref:`bits used
              to contain<glossary_bits_allocated>` each pixel, should be a 1
              or a multiple of 8.
            * `bits_stored`: :class:`int` - the number of :ref:`bits actually
              used<glossary_bits_stored>` per pixel. For example, `src` might
              have 16-bits allocated (range 0 to 65535) but only contain 12-bit
              pixel values (range 0 to 4095).
            * `photometric_interpretation`: :class:`str` - the :ref:`color
              space<glossary_photometric_interpretation>` of the *encoded*
              pixel data, such as ``"YBR_FULL"``.

            The following keyword parameters are conditionally required:

            * `planar_configuration`: :class:`int` - required for native
              (uncompressed) transfer syntaxes when `samples_per_pixel` > 1,
              this is whether the pixel data is :ref:`color-by-plane or
              color-by-pixel<glossary_planar_configuration>`. ``0``
              for color-by-pixel, ``1`` for color-by-plane.
            * `pixel_keyword`: :class:`str` - required for native
              (uncompressed) transfer syntaxes, one of ``"PixelData"``,
              ``"FloatPixelData"``, ``"DoubleFloatPixelData"``.
            * `pixel_representation`: :class:`int` - required when
              `pixel_keyword` is ``"PixelData"``, this is the :ref:`type of pixel
              values<glossary_pixel_representation>`, ``0`` for unsigned integers,
              ``1`` for signed.

            The following options may be used with native (uncompressed)
            transfer syntaxes:

            * `view_only`: :class:`bool` - if ``True`` then return a
              :class:`memoryview` on the original buffer (default ``False``).

            Options for the decoding plugin(s) may also be supplied. See the
            :doc:`decoding plugin options </guides/decoding/decoder_plugin_options>`
            for more information.

        Returns
        -------
        buffer-like
            The decoded pixel data.

            * For natively encoded pixel data the same type in `src` will be
              returned, however if `view_only` is ``True`` then a
              :class:`memoryview` on the original buffer will be returned instead.
            * Encapsulated pixel data will be returned as :class:`bytearray`.

            8-bit pixel data encoded as **OW** using Explicit VR Big Endian will
            be returned as-is and may need byte-swapping. To facilitate this
            an extra byte before the expected start (for an odd `index`) or after
            the expected end (for an even `index`) is returned if the frame contains
            an odd number of pixels.
        """
        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(self._validate_decoders(decoding_plugin))

        if validate:
            runner.validate_options()
            runner.validate_buffer()

        if self.is_native:
            return self._as_buffer_native(runner, index)

        return self._as_buffer_encapsulated(runner, index)

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
        """
        if runner.get_option("view_only", False):
            src: Buffer = memoryview(runner.src)
        else:
            src = runner.src

        expected_length = runner.frame_length(unit="bytes")
        if runner.test_for("be_swap_ow"):
            # Big endian 8-bit data encoded as OW
            if index is not None:
                # Return specified frame only
                start_offset = index * expected_length
                if (end_offset := start_offset + expected_length) > len(src):
                    raise ValueError(
                        f"There is insufficient pixel data to contain {index + 1} frames"
                    )

                if expected_length % 2 == 0:
                    # Even length frame: start and end correct
                    return src[start_offset:end_offset]

                if index % 2 == 0:
                    # Odd length frame, even index: start correct, end incorrect
                    return src[start_offset : end_offset + 1]

                # Odd length frame, odd index: start incorrect, end correct
                return src[start_offset - 1 : end_offset]

            # Return all frames
            return src

        if index is not None:
            start_offset = index * expected_length
            if (end_offset := start_offset + expected_length) > len(src):
                raise ValueError(
                    f"There is insufficient pixel data to contain {index + 1} frames"
                )

            return src[start_offset:end_offset]

        expected_length *= runner.number_of_frames
        return src[:expected_length]

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
        length_bytes = runner.frame_length(unit="bytes")

        # Return the specified frame only
        if index is not None:
            frame = runner.decode(index=index)
            if (actual := len(frame)) != length_bytes:
                raise ValueError(
                    "Unexpected number of bytes in the decoded frame with index "
                    f"{index} ({actual} bytes actual vs {length_bytes} expected)"
                )

            return frame

        # Return all frames
        # Preallocate buffer for the frames
        buffer = bytearray(length_bytes * runner.number_of_frames)
        frame_generator = runner.iter_decode()
        for index in range(runner.number_of_frames):
            frame = next(frame_generator)
            start = index * length_bytes
            if (actual := len(frame)) != length_bytes:
                raise ValueError(
                    "Unexpected number of bytes in the decoded frame with index "
                    f"{index} ({actual} bytes actual vs {length_bytes} expected)"
                )

            buffer[start : start + length_bytes] = frame

        # Check to see if we have any more frames available
        #   Should only apply to JPEG transfer syntaxes
        excess = bytearray()
        for frame in frame_generator:
            if len(frame) == length_bytes:
                excess.extend(frame)
                runner.set_option("number_of_frames", runner.number_of_frames + 1)

        if excess:
            warn_and_log(
                "More frames have been found in the encapsulated pixel data "
                "than expected from the supplied number of frames"
            )
            buffer.extend(excess)

        return buffer

    def iter_array(
        self,
        src: Buffer | Dataset,
        *,
        indices: Iterable[int] | None = None,
        raw: bool = False,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> Iterator["np.ndarray"]:
        """Yield pixel data frames as :class:`~numpy.ndarray`.

        .. warning::

            This method requires `NumPy <https://numpy.org/>`_

        **Processing**

        The following processing operations on the raw pixel data are always
        performed:

        * Natively encoded bit-packed pixel data for a :ref:`bits allocated
          <glossary_bits_allocated>` of ``1`` will be unpacked.
        * Natively encoded pixel data with a :ref:`photometric interpretation
          <glossary_photometric_interpretation>` of ``"YBR_FULL_422"`` will
          have it's sub-sampling removed.
        * The output array will be reshaped to the specified dimensions.

        If ``raw = False`` (the default) then the following processing operation
        will also be performed:

        * Pixel data with a :ref:`photometric interpretation
          <glossary_photometric_interpretation>` of ``"YBR_FULL"`` or
          ``"YBR_FULL_422"`` will be converted to ``"RGB"``.

        Parameters
        ----------
        src : buffer-like | :class:`~pydicom.dataset.Dataset`
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
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
            The following keyword parameters are required when `src` is not
            a :class:`~pydicom.dataset.Dataset`, or may be used to override the
            corresponding element values when `src` is a
            :class:`~pydicom.dataset.Dataset`:

            * `rows`: :class:`int` - the number of :ref:`rows<glossary_rows>`
              of pixels in `src`, maximum 65535.
            * `columns`: :class:`int` - the number of :ref:`columns
              <glossary_columns>` of pixels in `src`, maximum 65535.
            * `number_of_frames`: :class:`int` - the :ref:`number of frames
              <glossary_number_of_frames>` in `src`, minimum 1.
            * `samples_per_pixel`: :class:`int` - the number of :ref:`samples
              per pixel<glossary_samples_per_pixel>` in `src`, should be 1 or 3.
            * `bits_allocated`: :class:`int` - the number of :ref:`bits used
              to contain<glossary_bits_allocated>` each pixel, should be a 1
              or a multiple of 8.
            * `bits_stored`: :class:`int` - the number of :ref:`bits actually
              used<glossary_bits_stored>` per pixel. For example, `src` might
              have 16-bits allocated (range 0 to 65535) but only contain 12-bit
              pixel values (range 0 to 4095).
            * `photometric_interpretation`: :class:`str` - the :ref:`color
              space<glossary_photometric_interpretation>` of the *encoded*
              pixel data, such as ``"YBR_FULL"``.

            The following keyword parameters are conditionally required:

            * `planar_configuration`: :class:`int` - required for native
              (uncompressed) transfer syntaxes when `samples_per_pixel` > 1,
              this is whether the pixel data is :ref:`color-by-plane or
              color-by-pixel<glossary_planar_configuration>`. ``0``
              for color-by-pixel, ``1`` for color-by-plane.
            * `pixel_keyword`: :class:`str` - required for native
              (uncompressed) transfer syntaxes, one of ``"PixelData"``,
              ``"FloatPixelData"``, ``"DoubleFloatPixelData"``.
            * `pixel_representation`: :class:`int` - required when
              `pixel_keyword` is ``"PixelData"``, this is the :ref:`type of pixel
              values<glossary_pixel_representation>`, ``0`` for unsigned integers,
              ``1`` for signed.

            The following options may be used with any transfer syntax:

            * `as_rgb`: :class:`bool` - if ``True`` (default) then convert pixel
              data with a YCbCr :ref:`photometric interpretation
              <glossary_photometric_interpretation>` such as ``"YBR_FULL_422"``
              to RGB.
            * `force_rgb`: :class:`bool` - if ``True`` then force a YCbCr to RGB
              color space conversion on the array (default ``False``).
            * `force_ybr`: :class:`bool` - if ``True`` then force an RGB to YCbCr
              color space conversion on the array (default ``False``).

            The following options may be used with native (uncompressed)
            transfer syntaxes:

            * `view_only`: :class:`bool` - if ``True`` then make a best effort
              attempt to yield an :class:`~numpy.ndarray` that's a `view
              <https://numpy.org/doc/stable/user/basics.copies.html#view>`_
              on the original buffer (default ``False``).

            Options for the decoding plugin(s) may also be supplied. See the
            :doc:`decoding plugin options </guides/decoding/decoder_plugin_options>`
            for more information.

        Yields
        ------
        numpy.ndarray
            The decoded and reshaped pixel data, with shape:

            * (rows, columns) for single frame, single plane data
            * (rows, columns, planes) for single frame, multi-plane data

            A writeable :class:`~numpy.ndarray` is returned by default. For
            native transfer syntaxes with ``view_only=True`` a read-only
            :class:`~numpy.ndarray` will be yielded if `src` is immutable.
        """
        if not HAVE_NP:
            raise ImportError(
                "NumPy is required when converting pixel data to an ndarray"
            )

        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(self._validate_decoders(decoding_plugin))

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate_options()
            runner.validate_buffer()

        if self.is_native:
            func = self._as_array_native
            as_writeable = not runner.get_option("view_only", False)
        else:
            func = self._as_array_encapsulated
            as_writeable = True

        if self.is_encapsulated and not indices:
            for frame in runner.iter_decode():
                arr = np.frombuffer(frame, dtype=runner.pixel_dtype)
                arr = runner.reshape(arr, as_frame=True)
                if raw:
                    yield arr if arr.flags.writeable else arr.copy()
                    continue

                arr = runner.process(arr)

                yield arr if arr.flags.writeable else arr.copy()

            return

        indices = indices if indices else range(runner.number_of_frames)
        for index in indices:
            arr = runner.reshape(func(runner, index), as_frame=True)
            if raw:
                yield arr.copy() if not arr.flags.writeable and as_writeable else arr
                continue

            # Processing may give us a new writeable array anyway, so do
            #   it first to avoid an unnecessary ndarray.copy()
            arr = runner.process(arr)

            yield arr.copy() if not arr.flags.writeable and as_writeable else arr

    def iter_buffer(
        self,
        src: Buffer | Dataset,
        *,
        indices: Iterable[int] | None = None,
        validate: bool = True,
        decoding_plugin: str = "",
        **kwargs: Any,
    ) -> Iterator[Buffer]:
        """Yield raw decoded pixel data frames as a buffer-like.

        Parameters
        ----------
        src : buffer-like | :class:`~pydicom.dataset.Dataset`
            Single or multi-frame pixel data as one of the following:

            * :class:`~pydicom.dataset.Dataset`: a dataset containing
              the pixel data to be decoded and the corresponding
              *Image Pixel* module elements.
            * :class:`bytes` | :class:`bytearray` | :class:`memoryview`: the
              encoded (and possibly encapsulated) pixel data to be decoded.
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
            The following keyword parameters are required when `src` is not
            a :class:`~pydicom.dataset.Dataset`, or may be used to override the
            corresponding element values when `src` is a
            :class:`~pydicom.dataset.Dataset`:

            * `rows`: :class:`int` - the number of :ref:`rows<glossary_rows>`
              of pixels in `src`, maximum 65535.
            * `columns`: :class:`int` - the number of :ref:`columns
              <glossary_columns>` of pixels in `src`, maximum 65535.
            * `number_of_frames`: :class:`int` - the :ref:`number of frames
              <glossary_number_of_frames>` in `src`, minimum 1.
            * `samples_per_pixel`: :class:`int` - the number of :ref:`samples
              per pixel<glossary_samples_per_pixel>` in `src`, should be 1 or 3.
            * `bits_allocated`: :class:`int` - the number of :ref:`bits used
              to contain<glossary_bits_allocated>` each pixel, should be a 1
              or a multiple of 8.
            * `bits_stored`: :class:`int` - the number of :ref:`bits actually
              used<glossary_bits_stored>` per pixel. For example, `src` might
              have 16-bits allocated (range 0 to 65535) but only contain 12-bit
              pixel values (range 0 to 4095).
            * `photometric_interpretation`: :class:`str` - the :ref:`color
              space<glossary_photometric_interpretation>` of the *encoded*
              pixel data, such as ``"YBR_FULL"``.

            The following keyword parameters are conditionally required:

            * `planar_configuration`: :class:`int` - required for native
              (uncompressed) transfer syntaxes when `samples_per_pixel` > 1,
              this is whether the pixel data is :ref:`color-by-plane or
              color-by-pixel<glossary_planar_configuration>`. ``0``
              for color-by-pixel, ``1`` for color-by-plane.
            * `pixel_keyword`: :class:`str` - required for native
              (uncompressed) transfer syntaxes, one of ``"PixelData"``,
              ``"FloatPixelData"``, ``"DoubleFloatPixelData"``.
            * `pixel_representation`: :class:`int` - required when
              `pixel_keyword` is ``"PixelData"``, this is the :ref:`type of pixel
              values<glossary_pixel_representation>`, ``0`` for unsigned integers,
              ``1`` for signed.

            The following options may be used with native (uncompressed)
            transfer syntaxes:

            * `view_only`: :class:`bool` - if ``True`` then yield a
              :class:`memoryview` on the original buffer (default ``False``).

            Options for the decoding plugin(s) may also be supplied. See the
            :doc:`decoding plugin options </guides/decoding/decoder_plugin_options>`
            for more information.

        Yields
        -------
        buffer-like
            The decoded pixel data.

            * For natively encoded pixel data the same type in `src` will be
              yielded, however if `view_only` is ``True`` then a
              :class:`memoryview` on the original buffer will be yielded instead.
            * Encapsulated pixel data will be yielded as :class:`bytearray`.

            8-bit pixel data encoded as **OW** using Explicit VR Big Endian will
            be yielded as-is and may need byte-swapping. To facilitate this
            an extra byte before the expected start (for an odd `index`) or after
            the expected end (for an even `index`) is yielded if the frame contains
            an odd number of pixels.
        """
        runner = DecodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_decoders(self._validate_decoders(decoding_plugin))

        if validate:
            runner.validate_options()
            runner.validate_buffer()

        if self.is_encapsulated and not indices:
            yield from runner.iter_decode()
            return

        if self.is_native:
            func = self._as_buffer_native
        else:
            func = self._as_buffer_encapsulated

        indices = indices if indices else range(runner.number_of_frames)
        for index in indices:
            yield func(runner, index)

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the decoder has plugins available that can be
        used to decode data, ``False`` otherwise.
        """
        # Decoders for public non-compressed syntaxes are always available
        if self.is_native:
            return True

        return bool(self._available)

    @property
    def is_encapsulated(self) -> bool:
        """Return ``True`` if the decoder is for an encapsulated transfer
        syntax, ``False`` otherwise.
        """
        return self.UID.is_encapsulated

    @property
    def is_native(self) -> bool:
        """Return ``True`` if the decoder is for an native transfer
        syntax, ``False`` otherwise.
        """
        return not self.is_encapsulated

    @property
    def missing_dependencies(self) -> list[str]:
        """Return nice strings for plugins with missing dependencies as
        list[str].
        """
        s = []
        for label, deps in self._unavailable.items():
            if not deps:
                # A plugin might have no dependencies and be unavailable for
                #   other reasons
                s.append(f"{label} - plugin indicating it is unavailable")
            elif len(deps) > 1:
                s.append(f"{label} - requires {', '.join(deps[:-1])} and {deps[-1]}")
            else:
                s.append(f"{label} - requires {deps[0]}")

        return s

    @property
    def name(self) -> str:
        """Return the name of the decoder as :class:`str`."""
        return f"{self.UID.keyword}Decoder"

    def remove_plugin(self, label: str) -> None:
        """Remove a plugin from the decoder.

        .. warning::

            This method is not thread-safe.

        Parameters
        ----------
        label : str
            The label of the plugin to remove.
        """
        if label in self._available:
            del self._available[label]
        elif label in self._unavailable:
            del self._unavailable[label]
        else:
            raise ValueError(f"Unable to remove '{label}', no such plugin'")

    @property
    def UID(self) -> UID:
        """Return the decoder's corresponding *Transfer Syntax UID* as a
        :class:`~pydicom.uid.UID`.
        """
        return self._uid

    def _validate_decoders(self, plugin: str = "") -> dict[str, DecodeFunction]:
        """Return available decoders.

        Parameters
        ----------
        plugin : str, optional
            If not used (default) then return all available plugins, otherwise
            only return the plugin with a matching name (if it's available).

        Returns
        -------
        dict[str, DecodeFunction]
            A dict of available {plugin name: decode function} that can be used
            to decode the corresponding encoded pixel data.
        """
        if plugin:
            if plugin in self._available:
                return {plugin: self._available[plugin]}

            if deps := self._unavailable.get(plugin, None):
                missing = deps[0]
                if len(deps) > 1:
                    missing = f"{', '.join(deps[:-1])} and {deps[-1]}"

                raise RuntimeError(
                    f"Unable to decode with the '{plugin}' decoding plugin "
                    f"because it's missing dependencies - requires {missing}"
                )

            raise ValueError(
                f"No decoding plugin named '{plugin}' has been added to "
                f"the '{self.name}'"
            )

        if not self.UID.is_encapsulated:
            return {}

        if self._available:
            return self._available.copy()

        missing = "\n".join([f"\t{s}" for s in self.missing_dependencies])
        raise RuntimeError(
            f"Unable to decode because the decoding plugins are all missing "
            f"dependencies:\n{missing}"
        )


# Decoder names should be f"{UID.keyword}Decoder"
# Uncompressed transfer syntaxes need no plugins
ImplicitVRLittleEndianDecoder = Decoder(ImplicitVRLittleEndian)
ExplicitVRLittleEndianDecoder = Decoder(ExplicitVRLittleEndian)
ExplicitVRBigEndianDecoder = Decoder(ExplicitVRBigEndian)
DeflatedExplicitVRLittleEndianDecoder = Decoder(DeflatedExplicitVRLittleEndian)

RLELosslessDecoder = Decoder(RLELossless)
RLELosslessDecoder.add_plugin(
    "pydicom", ("pydicom.pixels.decoders.rle", "_decode_frame")
)


# Available pixel data decoders
_PIXEL_DATA_DECODERS = {
    # UID: (decoder, 'versionadded')
    ImplicitVRLittleEndian: (ImplicitVRLittleEndianDecoder, "3.0"),
    ExplicitVRLittleEndian: (ExplicitVRLittleEndianDecoder, "3.0"),
    DeflatedExplicitVRLittleEndian: (DeflatedExplicitVRLittleEndianDecoder, "3.0"),
    ExplicitVRBigEndian: (ExplicitVRBigEndianDecoder, "3.0"),
    RLELossless: (RLELosslessDecoder, "3.0"),
}


def _build_decoder_docstrings() -> None:
    """Override the default Decoder docstring."""
    plugin_doc_links = {
        "gdcm": ":ref:`gdcm <decoder_plugin_gdcm>`",
        "jpeg_ls": ":ref:`jpeg_ls <decoder_plugin_jpegls>`",
        "pillow": ":ref:`pillow <decoder_plugin_pillow>`",
        "pydicom": ":ref:`pydicom <decoder_plugin_pydicom>`",
        "pylibjpeg": ":ref:`pylibjpeg <decoder_plugin_pylibjpeg>`",
    }

    for dec, versionadded in _PIXEL_DATA_DECODERS.values():
        uid = dec.UID
        available = dec._available.keys()
        unavailable = dec._unavailable.keys()
        plugins = list(available) + list(unavailable)

        plugins = [plugin_doc_links[name] for name in sorted(plugins)]

        s = [f"A *Pixel Data* decoder for *{uid.name}* - ``{uid}``"]
        s.append("")
        s.append(f".. versionadded:: {versionadded}")
        s.append("")
        s.append(f"Decoding plugins: {', '.join(plugins)}")
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

    +-------------------------------------------------------------------+---------+
    | Transfer Syntax                                                   | Version |
    +--------------------------------------+----------------------------+ added   +
    | Name                                 | UID                        |         |
    +======================================+============================+=========+
    | *Implicit VR Little Endian*          | 1.2.840.10008.1.2          | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Explicit VR Little Endian*          | 1.2.840.10008.1.2.1        | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Deflated Explicit VR Little Endian* | 1.2.840.10008.1.2.1.2.1.99 | 3.0     |
    +--------------------------------------+----------------------------+---------+
    | *Explicit VR Big Endian*             | 1.2.840.10008.1.2.2        | 3.0     |
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
