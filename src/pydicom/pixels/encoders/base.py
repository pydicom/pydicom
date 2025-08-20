# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Pixel data encoding."""

from collections.abc import Callable, Iterator, Iterable
import logging
import math
import sys
from typing import Any, cast, TYPE_CHECKING

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import config
from pydicom.pixels.common import Buffer, RunnerBase, CoderBase, RunnerOptions
from pydicom.uid import (
    UID,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
    JPEGLSTransferSyntaxes,
    DeflatedImageFrameCompression,
)

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


LOGGER = logging.getLogger(__name__)


EncodeFunction = Callable[[bytes, "EncodeRunner"], bytes | bytearray]

# JPEG-LS with pyjpegls and JPEG2000 with pylibjpeg-openjpeg both default
#   to removing the high bits, so we only need to handle
#   RLE Lossless and Deflated Image ourselves
_SHIFT_HIGH_BITS = [RLELossless, DeflatedImageFrameCompression]


class EncodeOptions(RunnerOptions, total=False):
    """Options accepted by EncodeRunner and encoding plugins"""

    # The byte order used by the raw pixel data sent to the encoder
    #   ">" for big endian, "<" for little endian (default)
    byteorder: str

    ## Transfer Syntax specific options
    # JPEG-LS Near Lossless
    # The maximum allowable error in *unsigned* pixel intensity
    jls_error: int

    # JPEG 2000
    # Either j2k_cr or j2k_psnr is required
    # The compression ratio for each quality layer, should be in decreasing order
    j2k_cr: list[float]
    # The peak signal-to-noise ratio for each layer, should be in increasing order
    j2k_psnr: list[float]

    # RLE Lossless
    # Fix GDCM encoding errors on big endian systems
    rle_fix_gdcm_big_endian: bool


class EncodeRunner(RunnerBase):
    """Class for managing the pixel data encoding process.

    .. versionadded:: 3.0

    This class is not intended to be used directly. For encoding pixel data
    use the :class:`~pydicom.pixels.encoders.base.Encoder` instance
    corresponding to the transfer syntax of the pixel data.
    """

    def __init__(self, tsyntax: UID) -> None:
        """Create a new runner for encoding data as `tsyntax`.

        Parameters
        ----------
        tsyntax : pydicom.uid.UID
            The transfer syntax UID corresponding to the pixel data to be
            encoded.
        """
        self._src: Buffer | np.ndarray
        self._src_type: str
        self._opts: EncodeOptions = {
            "transfer_syntax_uid": tsyntax,
            "byteorder": "<",
            "pixel_keyword": "PixelData",
            "include_high_bits": None,
        }
        self._undeletable = ("transfer_syntax_uid", "pixel_keyword", "byteorder")
        self._encoders: dict[str, EncodeFunction] = {}

    def encode(self, index: int | None) -> bytes:
        """Return an encoded frame of pixel data as :class:`bytes`.

        Parameters
        ----------
        index : int | None
            If `index` is ``None`` then the pixel data only contains one frame,
            otherwise `index` is the frame number to be encoded.

        Returns
        ------
        bytes
            The encoded pixel data frame.
        """
        failure_messages = []
        for name, func in self._encoders.items():
            try:
                return func(self.get_frame(index), self)
            except Exception as exc:
                LOGGER.exception(exc)
                failure_messages.append(f"{name}: {exc}")

        messages = "\n  ".join(failure_messages)
        raise RuntimeError(
            "Unable to encode as exceptions were raised by all available "
            f"plugins:\n  {messages}"
        )

    def get_frame(self, index: int | None) -> bytes:
        """Return a frame's worth of uncompressed pixel data as :class:`bytes`.

        Parameters
        ----------
        index : int | None
            If the pixel data only has one from then use ``None``, otherwise
            `index` is the index of the frame to be returned.
        """
        if self.is_array:
            return self._get_frame_array(index)

        frame = self._get_frame_buffer(index)
        return bytes(frame) if not isinstance(frame, bytes) else frame

    def _get_frame_array(self, index: int | None) -> bytes:
        """Return a frame's worth of uncompressed pixel data from an ndarray."""
        # Grab the frame so that subsequent array manipulations minimize
        #   the memory usage
        arr = cast(np.ndarray, self.src[index] if index is not None else self.src)

        # The ndarray containing the pixel data may use a larger container
        #   than is strictly needed: e.g. 32 bits allocated with 7 bits stored.
        #   However the encoders expect data to be sized appropriately
        #   for the sample precision, so we may need to downscale
        if self.bits_stored <= 8:
            itemsize = 1
        elif 8 < self.bits_stored <= 16:
            itemsize = 2
        elif 16 < self.bits_stored <= 32:
            itemsize = 4
        elif 32 < self.bits_stored <= 64:
            itemsize = 8

        if arr.dtype.itemsize != itemsize:
            # Creates a view of the original array, may be read-only
            arr = arr.astype(f"<{arr.dtype.kind}{itemsize}")

        include_high_bits = self.get_option("include_high_bits", None)
        if self.bits_stored == itemsize * 8:
            # No unused high bits to worry about
            pass
        elif self.transfer_syntax in _SHIFT_HIGH_BITS and include_high_bits is False:
            # Remove any data from the high bits
            #   For unsigned integers replace the high bits with 0s
            #   For signed integers replace the high bits with 1s
            shift = itemsize * 8 - self.bits_stored
            # Copy `arr` to avoid modifying the original
            arr = np.left_shift(arr, shift)
            np.right_shift(arr, shift, out=arr)
        elif include_high_bits is True:
            # Include the data in the high bits when encoding
            self.set_option("bits_stored", itemsize * 8)

        # JPEG-LS allows different ordering of the input image data via the
        #   interleave mode (ILV) parameter. ILV 0 matches a planar configuration
        #   of 1 and requires shape (samples, rows, columns). ILV 1 and 2 match
        #   planar configuration 0 so no further action is needed
        if (
            self.transfer_syntax in JPEGLSTransferSyntaxes
            and self.samples_per_pixel == 3
            and self.planar_configuration == 1
        ):
            arr = arr.transpose(2, 0, 1)

        return cast(bytes, arr.tobytes())

    def _get_frame_buffer(self, index: int | None) -> bytes | bytearray:
        """Return a frame's worth of uncompressed pixel data from buffer-like."""
        # The encoded pixel data may use a larger container than is strictly
        #   needed: e.g. 32 bits allocated with 7 bits stored
        # However the encoders typically expect data to be sized appropriately
        # for the sample precision, so we need to downscale to:
        #    0 < precision <=  8: an 8-bit container (char)
        #    8 < precision <= 16: a 16-bit container (short)
        #   16 < precision <= 32: a 32-bit container (int/long)
        #   32 < precision <= 64: a 64-bit container (long long)
        bytes_per_frame = cast(int, self.frame_length(unit="bytes"))
        start = 0 if index is None else index * bytes_per_frame
        src = cast(bytes, self.src[start : start + bytes_per_frame])

        # Resize the data to fit the appropriate container
        expected_length = cast(int, self.frame_length(unit="pixels"))
        bytes_per_pixel = len(src) // expected_length
        print(bytes_per_pixel, self.bits_stored)

        include_high_bits = self.get_option("include_high_bits", None)

        # It's faster to use numpy if its available?
        if HAVE_NP:
            # Take the first `itemsize` bytes out of every `bytes_per_pixel` bytes
            arr = np.frombuffer(src, dtype="u1")
            if self.bits_stored <= 8:
                itemsize = 1
                arr = arr[::bytes_per_pixel] if bytes_per_pixel != 1 else arr

            if 8 < self.bits_stored <= 16:
                itemsize = 2
                if bytes_per_pixel != 2:
                    arr = arr.reshape(arr.size // bytes_per_pixel, bytes_per_pixel)
                    arr = arr[..., :itemsize].ravel()

            if 16 < self.bits_stored <= 32:
                itemsize = 4
                if bytes_per_pixel != 4:
                    arr = arr.reshape(arr.size // bytes_per_pixel, bytes_per_pixel)
                    arr = arr[..., :itemsize].ravel()

            if 32 < self.bits_stored <= 64:
                itemsize = 8
                if bytes_per_pixel != 8:
                    arr = arr.reshape(arr.size // bytes_per_pixel, bytes_per_pixel)
                    arr = arr[..., :itemsize].ravel()

            # How to handle data in the unused high bits above `bits_stored`
            if self.bits_stored == itemsize * 8:
                # No unused high bits to worry about
                pass
            elif include_high_bits is False and self.transfer_syntax in _SHIFT_HIGH_BITS:
                # Remove any data from the high bits
                #   For unsigned integers replace the high bits with 0s
                #   For signed integers replace the high bits with 1s
                kind = "u" if self.pixel_representation == 0 else "i"
                arr = arr.astype(f"<{kind}{itemsize}", copy=not arr.flags.writeable)
                shift = itemsize * 8 - self.bits_stored
                np.left_shift(arr, shift, out=arr)
                np.right_shift(arr, shift, out=arr)
            elif include_high_bits is True:
                # Include the data in the high bits
                print(itemsize)
                self.set_option("bits_stored", itemsize * 8)

            return arr.tobytes()

        # How to handle data in the unused high bits above `bits_stored`
        if self.bits_stored == bytes_per_pixel * 8:
            pass
        elif include_high_bits is True:
            # Include the data in the high bits
            self.set_option("bits_stored", bytes_per_pixel * 8)
        elif include_high_bits is False:
            raise ValueError("NumPy is required if 'include_high_bits' is False")

        # 1 byte/px actual
        if self.bits_stored <= 8:
            # If not 1 byte/px then must be 2, 3, 4, 5, 6, 7 or 8
            #   but only the first byte is relevant
            return src if bytes_per_pixel == 1 else src[::bytes_per_pixel]

        # 2 bytes/px actual
        if 8 < self.bits_stored <= 16:
            if bytes_per_pixel == 2:
                return src

            # If not 2 bytes/px then must be 3, 4, 5, 6, 7 or 8
            #   but only the first 2 bytes are relevant
            out = bytearray(expected_length * 2)
            out[::2] = src[::bytes_per_pixel]
            out[1::2] = src[1::bytes_per_pixel]
            return out

        # 3 or 4 bytes/px actual
        if 16 < self.bits_stored <= 32:
            if bytes_per_pixel == 4:
                return src

            # If not 4 bytes/px then must be 3, 5, 6, 7 or 8
            #   but only the first 3 or 4 bytes are relevant
            out = bytearray(expected_length * 4)
            out[::4] = src[::bytes_per_pixel]
            out[1::4] = src[1::bytes_per_pixel]
            out[2::4] = src[2::bytes_per_pixel]
            if bytes_per_pixel > 3:
                out[3::4] = src[3::bytes_per_pixel]

            return out

        # 32 < bits_stored <= 64 (maximum allowed)
        # 5, 6, 7 or 8 bytes/px actual
        if bytes_per_pixel == 8:
            return src

        # If not 8 bytes/px then must be 5, 6 or 7
        out = bytearray(expected_length * 8)
        out[::8] = src[::bytes_per_pixel]
        out[1::8] = src[1::bytes_per_pixel]
        out[2::8] = src[2::bytes_per_pixel]
        out[3::8] = src[3::bytes_per_pixel]
        out[4::8] = src[4::bytes_per_pixel]
        if bytes_per_pixel == 5:
            return out

        out[5::8] = src[5::bytes_per_pixel]
        if bytes_per_pixel == 6:
            return out

        # 7 bytes/px
        out[6::8] = src[6::bytes_per_pixel]
        return out

    def set_encoders(self, encoders: dict[str, EncodeFunction]) -> None:
        """Set the encoders use for encoding compressed pixel data.

        Parameters
        ----------
        encoders : dict[str, EncodeFunction]
            A dict of {name: encoder function}.
        """
        self._encoders = encoders

    def set_source(self, src: "np.ndarray | Dataset | Buffer") -> None:
        """Set the pixel data to be encoded.

        Parameters
        ----------
        src : bytes | bytearray | memoryview | pydicom.dataset.Dataset | numpy.ndarray

            * If a buffer-like then the encoded pixel data
            * If a :class:`~pydicom.dataset.Dataset` then a dataset containing
              the pixel data and associated group ``0x0028`` elements.
            * If a :class:`numpy.ndarray` then an array containing the image data.
        """
        from pydicom.dataset import Dataset

        if isinstance(src, Dataset):
            self._set_options_ds(src)
            self._src = src.PixelData
            self._src_type = "Dataset"
        elif isinstance(src, (bytes | bytearray | memoryview)):
            self._src = src
            self._src_type = "Buffer"
        elif isinstance(src, np.ndarray):
            # Ensure the array is in the required byte order (little-endian)
            sys_endianness = "<" if sys.byteorder == "little" else ">"
            # `byteorder` may be
            #   '|': none available, such as for 8 bit -> ignore
            #   '=': native system endianness -> change to '<' or '>'
            #   '<' or '>': little or big
            byteorder = src.dtype.byteorder
            byteorder = sys_endianness if byteorder == "=" else byteorder
            if byteorder == ">":
                src = src.astype(src.dtype.newbyteorder("<"))

            self._src = src
            self._src_type = "Array"
        else:
            raise TypeError(
                "'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
                f"not '{src.__class__.__name__}'"
            )

    @property
    def src(self) -> "Buffer | np.ndarray":
        """Return the buffer-like or :class:`numpy.ndarray` containing the pixel data."""
        return self._src

    def __str__(self) -> str:
        """Return nice string output for the runner."""
        s = [f"EncodeRunner for '{self.transfer_syntax.name}'"]
        s.append("Options")
        s.extend([f"  {name}: {value}" for name, value in self.options.items()])
        if self._encoders:
            s.append("Encoders")
            s.extend([f"  {name}" for name in self._encoders])

        return "\n".join(s)

    def _test_for(self, test: str) -> bool:
        """Return the result of `test` as :class:`bool`."""
        if test == "gdcm_be_system":
            return sys.byteorder == "big" and self.get_option(
                "rle_fix_gdcm_big_endian", True
            )

        raise ValueError(f"Unknown test '{test}'")

    def validate(self) -> None:
        """Validate the encoding options and source pixel data."""
        self._validate_options()
        if self.is_dataset or self.is_buffer:
            self._validate_buffer()
        else:
            self._validate_array()

        # UID specific validation based on Section 8 of Part 5
        self._validate_encoding_profile()

    def _validate_array(self) -> None:
        """Check that the ndarray matches the supplied options."""
        arr = cast(np.ndarray, self.src)
        shape = arr.shape
        dtype = arr.dtype

        if len(shape) not in (2, 3, 4):
            raise ValueError(f"Unable to encode {len(shape)}D ndarrays")

        # `arr` may be (for planar configuration 0):
        #   (rows, columns)
        #   (rows, columns, planes)
        #   (frames, rows, columns)
        #   (frames, rows, columns, planes)
        expected = [
            self.number_of_frames,
            self.rows,
            self.columns,
            self.samples_per_pixel,
        ]
        expected = expected[1:] if expected[0] == 1 else expected
        expected = expected[:-1] if expected[-1] in (None, 1) else expected

        if shape != tuple(expected):
            raise ValueError(
                f"Mismatch between the expected ndarray shape {tuple(expected)} "
                f"and the actual shape {shape}"
            )

        # Check dtype is int or uint
        ui = [
            np.issubdtype(dtype, np.unsignedinteger),
            np.issubdtype(dtype, np.signedinteger),
        ]
        if not any(ui):
            raise ValueError(
                f"The ndarray's dtype '{dtype}' is not supported, must be a "
                "signed or unsigned integer type"
            )

        # Check dtype is consistent with the *Pixel Representation*
        is_signed = self.pixel_representation == 1
        if not ui[is_signed]:
            s = ["unsigned", "signed"][is_signed]
            raise ValueError(
                f"The ndarray's dtype '{dtype}' is not consistent with a (0028,0103) "
                f"'Pixel Representation' of '{self.pixel_representation}' ({s} integers)"
            )

        # Check the dtype's itemsize is at least as large as *Bits Allocated*
        if dtype.itemsize < math.ceil(self.bits_allocated / 8):
            raise ValueError(
                f"The ndarray's dtype '{dtype}' is not consistent with a (0028,0100) "
                f"'Bits Allocated' value of '{self.bits_allocated}'"
            )

        include_high_bits = self.get_option("include_high_bits", None)

        # Check the pixel data values are consistent with *Bits Stored*
        bits_stored = self.bits_stored
        if include_high_bits is None and bits_stored != arr.itemsize * 8:
            amax, amin = arr.max(), arr.min()
            if is_signed:
                minimum = -(2 ** (bits_stored - 1))
                maximum = 2 ** (bits_stored - 1) - 1
            else:
                minimum, maximum = 0, 2**bits_stored - 1

            if amax > maximum or amin < minimum:
                raise ValueError(
                    "The ndarray contains values that are outside the allowable "
                    f"range of ({minimum}, {maximum}) for a (0028,0101) 'Bits "
                    f"Stored' value of '{bits_stored}', which may indicate "
                    "the presence of overlays in the unused bits. To include the "
                    "data in these unused bits pass 'include_high_bits=True' or to "
                    "exclude it pass 'include_high_bits=False'."
                )

        if self.transfer_syntax == JPEGLSNearLossless and is_signed:
            # JPEG-LS doesn't track signedness, so with lossy encoding of
            #   signed data it's possible to flip from a negative to a positive
            #   value (or vice versa) due to the introduced error.
            # The only way to avoid this is to limit pixel values to the
            #   range (minimum + jls_error, maximum - jls_error), where
            #   `jls_error` is the JPEG-LS 'NEAR' parameter and `minimum`
            #   and `maximum` are the min/max possible values for a given
            #   sample precision
            error = self.get_option("jls_error", 0)
            amax, amin = arr.max(), arr.min()
            within = amax <= (maximum - error) and amin >= (minimum + error)
            if error and not within:
                raise ValueError(
                    "The supported range of pixel values when performing lossy "
                    "JPEG-LS encoding of signed integers with a (0028,0103) 'Bits "
                    f"Stored' value of '{bits_stored}' and a 'jls_error' "
                    f"of '{error}' is ({minimum + error}, {maximum - error})"
                )

    def _validate_buffer(self) -> None:
        """Validate the supplied pixel data buffer."""
        # Check the length is at least as long as required
        length_bytes = self.frame_length(unit="bytes")
        expected_length = length_bytes * self.number_of_frames
        if (actual_length := len(self.src)) < expected_length:
            raise ValueError(
                "The length of the uncompressed pixel data doesn't match the expected "
                f"length - {actual_length} bytes actual vs. {expected_length} expected"
            )

        include_high_bits = self.get_option("include_high_bits", None)
        if include_high_bits is not None:
            return

        # FIXME: Hmm... bits_allocated != container size here?
        bits_allocated = self.bits_allocated
        bits_stored = self.bits_stored
        if bits_allocated == 1 or bits_stored == bits_allocated:
            return

        # Check for the presence of data in the unused bits above 'bits_stored'
        overflow = False
        is_signed = self.pixel_representation == 1
        bytes_per_pixel = actual_length // self.frame_length(unit="pixels")
        if not is_signed:
            # Start at the most significant byte and work towards the least
            for max_bits in range(bytes_per_pixel * 8, 0, -8):
                if overflow or max_bits <= bits_stored:
                    # Found data in high bits or the byte is below the bits_stored byte
                    break

                min_bits = max_bits - 8
                byte_offset = min_bits // 8
                if bits_stored < min_bits:
                    # The byte is above the bits_stored byte
                    actual_max = max(self.src[byte_offset::bytes_per_pixel])
                    overflow = actual_max != 0x00
                elif bits_stored < max_bits:
                    # The byte contains the bits_stored byte
                    actual_max = max(self.src[byte_offset::bytes_per_pixel])
                    overflow = actual_max > 2**(bits_stored - min_bits) - 1
        else:
            # Checking overflow in signed data is more complex since signed values may
            #   have fill bits, so we check for consistency instead
            # Start at the byte containing bits_stored to see if there are any negative
            #   integers
            min_bits = bits_stored + bits_stored % 8 - 8
            actual_max = max(self.src[min_bits // 8::bytes_per_pixel])
            if (0x01 << (bits_stored - min_bits - 1)) & actual_max:
                # Buffer contains signed integers
                # All bits above bits_stored must either be 0b0 or 0b1
                # Example for bits_stored 6: actual_max must be in either:
                #   0b0010_0000 to 0b0011_1111 [32 to 63] or
                #   0b1110_0000 to 0b1111_1111 [224 to 255]
                # So right shift and check the residual high bits
                shifted = actual_max >> (bits_stored - min_bits)
                overflow = shifted not in (0x00, 2**shifted - 1)
                fill_bits = (0x00, 0xFF)
            else:
                # Buffer contains only unsigned integers
                # Example for bits_stored 6: actual_max must be in
                #   0b0000_0000 to 0b0001_0000 [0 to 31]
                overflow = actual_max > 2**(bits_stored - min_bits) - 1
                fill_bits = (0x00, )

            # Check the bytes above the bits_stored byte
            if not overflow:
                # Start at the most significant byte and work downwards
                for max_bits in range(bytes_per_pixel * 8, min_bits, -8):
                    min_bits = max_bits - 8
                    actual_max = max(self.src[min_bits // 8::bytes_per_pixel])
                    # May produce a false negative but worst case the user
                    #   will explicitly allow or disallow the high bits
                    overflow = actual_max not in fill_bits
                    if overflow:
                        break

        if overflow:
            msg = (
                "The pixel data contains values that are outside the allowable range "
                f"for a (0028,0101) 'Bits Stored' value of '{bits_stored}', which may "
                "indicate the presence of overlays in the higher bits. To include the "
                "data in these high bits when compressing pass 'include_high_bits=True' "
                "or to exclude it pass 'include_high_bits=False'"
            )
            if self.transfer_syntax in _SHIFT_HIGH_BITS:
                msg += " (requires NumPy)"

            raise ValueError(msg)

    def _validate_encoding_profile(self) -> None:
        """Perform  UID specific validation of encoding parameters based on
        Part 5, Section 8 of the DICOM Standard.

        Encoding profiles should be:

        Tuple[str, int, Iterable[int], Iterable[int], Iterable[int]] as
        (
            PhotometricInterpretation, SamplesPerPixel, PixelRepresentation,
            BitsAllocated, BitsStored
        )
        """
        if self.transfer_syntax not in ENCODING_PROFILES:
            return

        # Test each profile and see if it matches source parameters
        profile = ENCODING_PROFILES[self.transfer_syntax]
        for pi, spp, px_repr, bits_a, bits_s in profile:
            try:
                assert self.photometric_interpretation == pi
                assert self.samples_per_pixel == spp
                assert self.pixel_representation in px_repr
                assert self.bits_allocated in bits_a
                assert self.bits_stored in bits_s
            except AssertionError:
                continue

            return

        raise ValueError(
            "One or more of the following values is not valid for pixel data "
            f"encoded with '{self.transfer_syntax.name}':\n"
            f"  (0028,0002) Samples per Pixel: {self.samples_per_pixel}\n"
            "  (0028,0006) Photometric Interpretation: "
            f"{self.photometric_interpretation}\n"
            f"  (0028,0100) Bits Allocated: {self.bits_allocated}\n"
            f"  (0028,0101) Bits Stored: {self.bits_stored}\n"
            f"  (0028,0103) Pixel Representation: {self.pixel_representation}\n"
            "See Part 5, Section 8.2 of the DICOM Standard for more information"
        )


class Encoder(CoderBase):
    """Factory class for data encoders.

    Every available ``Encoder`` instance in *pydicom* corresponds directly
    to a single DICOM *Transfer Syntax UID*, and provides a  mechanism for
    converting raw unencoded source data to meet the requirements of that
    transfer syntax using one or more :doc:`encoding plugins
    </guides/encoding/encoder_plugins>`.

    .. versionadded:: 2.2
    """

    def __init__(self, uid: UID) -> None:
        """Create a new data encoder.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The *Transfer Syntax UID* that the encoder supports.
        """
        super().__init__(uid, decoder=False)

    def encode(
        self,
        src: "bytes | np.ndarray | Dataset",
        *,
        index: int | None = None,
        validate: bool = True,
        include_high_bits: bool | None = None,
        encoding_plugin: str = "",
        **kwargs: Any,
    ) -> bytes:
        """Return an encoded frame of the pixel data in `src` as
        :class:`bytes`.

        .. warning::

            With the exception of *RLE Lossless*, this method requires the
            installation of additional packages to perform the actual pixel
            data encoding. See the :doc:`encoding documentation
            </guides/user/image_data_compression>` for more information.

        .. versionchanged:: 3.1

            Added the `include_high_bits` keyword parameter.

        Parameters
        ----------
        src : bytes, numpy.ndarray or pydicom.dataset.Dataset
            Single or multi-frame pixel data as one of the following:

            * :class:`~numpy.ndarray`: the uncompressed pixel data, should be
              :attr:`shaped<numpy.ndarray.shape>` as:

              * (rows, columns) for single frame, single sample data.
              * (rows, columns, planes) for single frame, multi-sample data.
              * (frames, rows, columns) for multi-frame, single sample data.
              * (frames, rows, columns, planes) for multi-frame and
                multi-sample data.

            * :class:`~pydicom.dataset.Dataset`: the dataset containing
              the uncompressed *Pixel Data* to be encoded.
            * :class:`bytes`: the uncompressed little-endian ordered pixel
              data. `src` should use 1, 2, 4 or 8 bytes per pixel, whichever
              of these is sufficient for the (0028,0103) *Bits Stored* value.
        index : int, optional
            Required when `src` contains multiple frames, this is the index
            of the frame to be encoded.
        validate : bool, optional
            If ``True`` (default) then validate the supplied encoding options
            and pixel data prior to encoding, otherwise if ``False`` no
            validation will be performed.
        include_high_bits : bool | None, optional
            If ``None`` (default) then raise an exception if the unused bits above
            *Bits Stored* contain data (such as overlays), otherwise either include the
            data in the higher bits when encoding (if ``True``) or exclude it (if
            ``False``, requires NumPy). Storing overlay data in these unused bits was
            retired from the DICOM Standard in 2004 and we recommend converting
            datasets to use the :dcm:`Overlay Plane module<part03/sect_C.9.2.html>`
            instead.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available
            plugins will be tried (default). For information on the available
            plugins for each encoder see the
            :mod:`API documentation<pydicom.pixels.encoders>`.
        **kwargs
            The following keyword parameters are required when `src` is
            :class:`bytes` or :class:`~numpy.ndarray`:

            * ``'rows'``: :class:`int` - the number of rows of pixels in `src`,
              maximum 65535.
            * ``'columns'``: :class:`int` - the number of columns of pixels in
              `src`, maximum 65535.
            * ``'number_of_frames'``: :class:`int` - the number of frames
              in `src`.
            * ``'samples_per_pixel'``: :class:`int` - the number of samples
              per pixel in `src`, should be 1 or 3.
            * ``'bits_allocated'``: :class:`int` - the number of bits used
              to contain each pixel, should be a multiple of 8.
            * ``'bits_stored'``: :class:`int` - the number of bits actually
              used per pixel. For example, an ``ndarray`` `src` might have a
              :class:`~numpy.dtype` of ``'uint16'`` (range 0 to 65535) but
              only contain 12-bit pixel values (range 0 to 4095).
            * ``'pixel_representation'``: :class:`int` - the type of data
              being encoded, ``0`` for unsigned, ``1`` for 2's complement
              (signed)
            * ``'photometric_interpretation'``: :class:`str` - the intended
              color space of the *encoded* pixel data, such as ``'YBR_FULL'``.

            Optional keyword parameters for the encoding plugin may also be
            present. See the :doc:`encoding plugin options
            </guides/encoding/encoder_plugin_options>` for more information.

        Returns
        -------
        bytes
            The encoded pixel data.
        """
        if index is not None and index < 0:
            raise ValueError("'index' must be greater than or equal to 0")

        runner = EncodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_option("include_high_bits", include_high_bits)
        runner.set_encoders(
            cast(
                dict[str, "EncodeFunction"],
                self._validate_plugins(encoding_plugin),
            ),
        )

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate()

        if runner.number_of_frames > 1 and index is None:
            raise ValueError(
                "The 'index' of the frame to be encoded is required for "
                "multi-frame pixel data"
            )

        return runner.encode(index)

    def iter_encode(
        self,
        src: "bytes | np.ndarray | Dataset",
        *,
        validate: bool = True,
        include_high_bits: bool | None = None,
        encoding_plugin: str = "",
        **kwargs: Any,
    ) -> Iterator[bytes]:
        """Yield encoded frames of the pixel data in `src` as :class:`bytes`.

        .. warning::

            With the exception of *RLE Lossless*, this method requires the
            installation of additional packages to perform the actual pixel
            data encoding. See the :doc:`encoding documentation
            </guides/user/image_data_compression>` for more information.

        .. versionchanged:: 3.1

            Added the `include_high_bits` keyword parameter.

        Parameters
        ----------
        src : bytes, numpy.ndarray or pydicom.dataset.Dataset
            Single or multi-frame pixel data as one of the following:

            * :class:`~numpy.ndarray`: the uncompressed pixel data, should be
              :attr:`shaped<numpy.ndarray.shape>` as:

              * (rows, columns) for single frame, single sample data.
              * (rows, columns, planes) for single frame, multi-sample data.
              * (frames, rows, columns) for multi-frame, single sample data.
              * (frames, rows, columns, planes) for multi-frame and
                multi-sample data.

            * :class:`~pydicom.dataset.Dataset`: the dataset containing
              the uncompressed *Pixel Data* to be encoded.
            * :class:`bytes`: the uncompressed little-endian ordered pixel
              data. `src` should use 1, 2, 4 or 8 bytes per pixel, whichever
              of these is sufficient for the (0028,0103) *Bits Stored* value.
        validate : bool, optional
            If ``True`` (default) then validate the supplied encoding options
            and pixel data prior to encoding, otherwise if ``False`` no
            validation will be performed.
        include_high_bits : bool | None, optional
            If ``None`` (default) then raise an exception if the unused bits above
            *Bits Stored* contain data (such as overlays), otherwise either include the
            data in the higher bits when encoding (if ``True``) or exclude it (if
            ``False``, requires NumPy). Storing overlay data in these unused bits was
            retired from the DICOM Standard in 2004 and we recommend converting
            datasets to use the :dcm:`Overlay Plane module<part03/sect_C.9.2.html>`
            instead.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available
            plugins will be tried (default). For information on the available
            plugins for each encoder see the
            :mod:`API documentation<pydicom.pixels.encoders>`.
        **kwargs
            The following keyword parameters are required when `src` is
            :class:`bytes` or :class:`~numpy.ndarray`:

            * ``'rows'``: :class:`int` - the number of rows of pixels in `src`,
              maximum 65535.
            * ``'columns'``: :class:`int` - the number of columns of pixels in
              `src`, maximum 65535.
            * ``'number_of_frames'``: :class:`int` - the number of frames
              in `src`.
            * ``'samples_per_pixel'``: :class:`int` - the number of samples
              per pixel in `src`, should be 1 or 3.
            * ``'bits_allocated'``: :class:`int` - the number of bits used
              to contain each pixel, should be a multiple of 8.
            * ``'bits_stored'``: :class:`int` - the number of bits actually
              used per pixel. For example, an ``ndarray`` `src` might have a
              :class:`~numpy.dtype` of ``'uint16'`` (range 0 to 65535) but
              only contain 12-bit pixel values (range 0 to 4095).
            * ``'pixel_representation'``: :class:`int` - the type of data
              being encoded, ``0`` for unsigned, ``1`` for 2's complement
              (signed)
            * ``'photometric_interpretation'``: :class:`str` - the intended
              color space of the encoded pixel data, such as ``'YBR_FULL'``.

            Optional keyword parameters for the encoding plugin may also be
            present. See the :doc:`encoding plugin options
            </guides/encoding/encoder_plugin_options>` for more information.

        Yields
        ------
        bytes
            An encoded frame of pixel data.
        """
        runner = EncodeRunner(self.UID)
        runner.set_source(src)
        runner.set_options(**kwargs)
        runner.set_option("include_high_bits", include_high_bits)
        runner.set_encoders(
            cast(
                dict[str, "EncodeFunction"],
                self._validate_plugins(encoding_plugin),
            ),
        )

        if config.debugging:
            LOGGER.debug(runner)

        if validate:
            runner.validate()

        if runner.number_of_frames == 1:
            yield runner.encode(None)
            return

        for index in range(runner.number_of_frames):
            yield runner.encode(index)


# UID: [
#   Photometric Interpretation (the intended value *after* encoding),
#   Samples per Pixel,
#   Pixel Representation,
#   Bits Allocated,
#   Bits Stored,
# ]
ProfileType = tuple[str, int, Iterable[int], Iterable[int], Iterable[int]]
ENCODING_PROFILES: dict[UID, list[ProfileType]] = {
    JPEGBaseline8Bit: [  # 1.2.840.10008.1.2.4.50: Table 8.2.1-1 in PS3.5
        ("MONOCHROME1", 1, (0,), (8,), (8,)),
        ("MONOCHROME2", 1, (0,), (8,), (8,)),
        ("YBR_FULL_422", 3, (0,), (8,), (8,)),
        ("RGB", 3, (0,), (8,), (8,)),
    ],
    JPEGExtended12Bit: [  # 1.2.840.10008.1.2.4.51: Table 8.2.1-1 in PS3.5
        ("MONOCHROME1", 1, (0,), (8,), (8,)),
        ("MONOCHROME1", 1, (0,), (16,), (12,)),
        ("MONOCHROME2", 1, (0,), (8,), (8,)),
        ("MONOCHROME2", 1, (0,), (16,), (12,)),
    ],
    JPEGLossless: [  # 1.2.840.10008.1.2.4.57: Table 8.2.1-2 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16), range(1, 17)),
        ("MONOCHROME2", 1, (0, 1), (8, 16), range(1, 17)),
        ("PALETTE COLOR", 1, (0,), (8, 16), range(1, 17)),
        ("YBR_FULL", 3, (0,), (8, 16), range(1, 17)),
        ("RGB", 3, (0,), (8, 16), range(1, 17)),
    ],
    JPEGLosslessSV1: [  # 1.2.840.10008.1.2.4.70: Table 8.2.1-2 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16), range(1, 17)),
        ("MONOCHROME2", 1, (0, 1), (8, 16), range(1, 17)),
        ("PALETTE COLOR", 1, (0,), (8, 16), range(1, 17)),
        ("YBR_FULL", 3, (0,), (8, 16), range(1, 17)),
        ("RGB", 3, (0,), (8, 16), range(1, 17)),
    ],
    JPEGLSLossless: [  # 1.2.840.10008.1.2.4.80: Table 8.2.3-1 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16), range(2, 17)),
        ("MONOCHROME2", 1, (0, 1), (8, 16), range(2, 17)),
        ("PALETTE COLOR", 1, (0,), (8, 16), range(2, 17)),
        ("YBR_FULL", 3, (0,), (8,), range(2, 9)),
        ("RGB", 3, (0,), (8, 16), range(2, 17)),
    ],
    JPEGLSNearLossless: [  # 1.2.840.10008.1.2.4.81: Table 8.2.3-1 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16), range(2, 17)),
        ("MONOCHROME2", 1, (0, 1), (8, 16), range(2, 17)),
        ("YBR_FULL", 3, (0,), (8,), range(2, 9)),
        ("RGB", 3, (0,), (8, 16), range(2, 17)),
    ],
    JPEG2000Lossless: [  # 1.2.840.10008.1.2.4.90: Table 8.2.4-1 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16, 24, 32, 40), range(1, 39)),
        ("MONOCHROME2", 1, (0, 1), (8, 16, 24, 32, 40), range(1, 39)),
        ("PALETTE COLOR", 1, (0,), (8, 16), range(1, 17)),
        ("YBR_RCT", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
        ("RGB", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
        ("YBR_FULL", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
    ],
    JPEG2000: [  # 1.2.840.10008.1.2.4.91: Table 8.2.4-1 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16, 24, 32, 40), range(1, 39)),
        ("MONOCHROME2", 1, (0, 1), (8, 16, 24, 32, 40), range(1, 39)),
        ("YBR_ICT", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
        ("RGB", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
        ("YBR_FULL", 3, (0,), (8, 16, 24, 32, 40), range(1, 39)),
    ],
    RLELossless: [  # 1.2.840.10008.1.2.5: Table 8.2.2-1 in PS3.5
        ("MONOCHROME1", 1, (0, 1), (8, 16), range(1, 17)),
        ("MONOCHROME2", 1, (0, 1), (8, 16), range(1, 17)),
        ("PALETTE COLOR", 1, (0,), (8, 16), range(1, 17)),
        ("YBR_FULL", 3, (0,), (8,), range(1, 9)),
        ("RGB", 3, (0,), (8, 16), range(1, 17)),
    ],
    # DeflatedImageFrameCompression: [],  No defined limitations in PS3.5 8.2.16
}

# Encoder names should be f"{UID.keyword}Encoder"
RLELosslessEncoder = Encoder(RLELossless)
RLELosslessEncoder.add_plugins(
    [
        ("pylibjpeg", ("pydicom.pixels.encoders.pylibjpeg", "_encode_frame")),
        ("gdcm", ("pydicom.pixels.encoders.gdcm", "encode_pixel_data")),
        ("pydicom", ("pydicom.pixels.encoders.native", "_encode_rle_frame")),
    ],
)

JPEGLSLosslessEncoder = Encoder(JPEGLSLossless)
JPEGLSLosslessEncoder.add_plugin(
    "pyjpegls", ("pydicom.pixels.encoders.pyjpegls", "_encode_frame")
)

JPEGLSNearLosslessEncoder = Encoder(JPEGLSNearLossless)
JPEGLSNearLosslessEncoder.add_plugin(
    "pyjpegls", ("pydicom.pixels.encoders.pyjpegls", "_encode_frame")
)

JPEG2000LosslessEncoder = Encoder(JPEG2000Lossless)
JPEG2000LosslessEncoder.add_plugin(
    "pylibjpeg", ("pydicom.pixels.encoders.pylibjpeg", "_encode_frame")
)

JPEG2000Encoder = Encoder(JPEG2000)
JPEG2000Encoder.add_plugin(
    "pylibjpeg", ("pydicom.pixels.encoders.pylibjpeg", "_encode_frame")
)

DeflatedImageFrameCompressionEncoder = Encoder(DeflatedImageFrameCompression)
DeflatedImageFrameCompressionEncoder.add_plugin(
    "pydicom",
    ("pydicom.pixels.encoders.native", "_encode_deflated_frame"),
)


# Available pixel data encoders
_PIXEL_DATA_ENCODERS = {
    # UID: (encoder, 'versionadded')
    RLELossless: (RLELosslessEncoder, "2.2"),
    JPEGLSLossless: (JPEGLSLosslessEncoder, "3.0"),
    JPEGLSNearLossless: (JPEGLSNearLosslessEncoder, "3.0"),
    JPEG2000Lossless: (JPEG2000LosslessEncoder, "3.0"),
    JPEG2000: (JPEG2000Encoder, "3.0"),
    DeflatedImageFrameCompression: (DeflatedImageFrameCompressionEncoder, "3.1"),
}


def _build_encoder_docstrings() -> None:
    """Override the default Encoder docstring."""
    plugin_doc_links = {
        "pydicom": ":ref:`pydicom <encoder_plugin_pydicom>`",
        "pylibjpeg": ":ref:`pylibjpeg <encoder_plugin_pylibjpeg>`",
        "gdcm": ":ref:`gdcm <encoder_plugin_gdcm>`",
        "pyjpegls": ":ref:`pyjpegls <encoder_plugin_pyjpegls>`",
    }

    for enc, versionadded in _PIXEL_DATA_ENCODERS.values():
        uid = enc.UID
        available = enc._available.keys()
        unavailable = enc._unavailable.keys()
        plugins = list(available) + list(unavailable)

        plugins = [plugin_doc_links[name] for name in sorted(plugins)]

        s = [f"A *Pixel Data* encoder for *{uid.name}* - ``{uid}``"]
        s.append("")
        s.append(f".. versionadded:: {versionadded}")
        s.append("")
        s.append(f"Encoding plugins: {', '.join(plugins)}")
        s.append("")
        s.append(
            "See the :class:`~pydicom.pixels.encoders.base.Encoder` "
            "reference for instance methods and attributes."
        )
        enc.__doc__ = "\n".join(s)


_build_encoder_docstrings()


def get_encoder(uid: str) -> Encoder:
    """Return the pixel data encoder corresponding to `uid`.

    .. versionadded:: 2.2

    +--------------------------------------------------+----------------+
    | Transfer Syntax                                  | Version added  |
    +-------------------------+------------------------+                +
    | Name                    | UID                    |                |
    +=========================+========================+================+
    | *JPEG-LS Lossless*      | 1.2.840.10008.1.2.4.80 | 3.0            |
    +-------------------------+------------------------+----------------+
    | *JPEG-LS Near Lossless* | 1.2.840.10008.1.2.4.81 | 3.0            |
    +-------------------------+------------------------+----------------+
    | *JPEG 2000 Lossless*    | 1.2.840.10008.1.2.4.90 | 3.0            |
    +-------------------------+------------------------+----------------+
    | *JPEG 2000*             | 1.2.840.10008.1.2.4.91 | 3.0            |
    +-------------------------+------------------------+----------------+
    | *RLE Lossless*          | 1.2.840.10008.1.2.5    | 2.2            |
    +-------------------------+------------------------+----------------+
    | *Deflated Image Frame   | 1.2.840.10008.1.8.1    | 3.1            |
    | Compression*            |                        |                |
    +-------------------------+------------------------+----------------+
    """
    uid = UID(uid)
    try:
        return _PIXEL_DATA_ENCODERS[uid][0]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data encoders have been implemented for '{uid.name}'"
        )
