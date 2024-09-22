# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Common objects for pixel data handling."""

from enum import Enum, unique
from importlib import import_module
from typing import TYPE_CHECKING, Any, TypedDict

from pydicom.misc import warn_and_log
from pydicom.pixels.utils import as_pixel_options
from pydicom.uid import UID

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable
    from pydicom.dataset import Dataset
    from pydicom.pixels.decoders.base import DecodeOptions, DecodeFunction
    from pydicom.pixels.encoders.base import EncodeOptions, EncodeFunction


Buffer = bytes | bytearray | memoryview


class CoderBase:
    """Base class for Decoder and Encoder."""

    def __init__(self, uid: UID, decoder: bool) -> None:
        """Create a new data decoder or encoder.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The supported *Transfer Syntax UID*.
        decoder : bool
            ``True`` for a decoder subclass, ``False`` for an encoder subclass.
        """
        # The *Transfer Syntax UID* data will be encoded to
        self._uid = uid
        # Available plugins
        self._available: dict[str, Callable] = {}
        # Unavailable plugins - missing dependencies or other reason
        self._unavailable: dict[str, tuple[str, ...]] = {}
        # True for a Decoder class, False for an Encoder class
        self._decoder = decoder

    def add_plugin(self, label: str, import_path: tuple[str, str]) -> None:
        """Add a plugin to the class instance.

        .. warning::

            This method is not thread-safe.

        The requirements for encoding plugins are available
        :doc:`here</guides/encoding/encoder_plugins>`, while the requirements
        for decoding plugins are available :doc:`here
        </guides/decoding/decoder_plugins>`.

        Only encoding plugins should be added to
        :class:`~pydicom.pixels.encoders.base.Encoder` class instances
        and only decoding plugins should be added to
        :class:`~pydicom.pixels.decoders.base.Decoder` class instances.

        Parameters
        ----------
        label : str
            The label to use for the plugin, should be unique.
        import_path : Tuple[str, str]
            The module import path and the function's name (e.g.
            ``('pydicom.pixels.encoders.pylibjpeg', 'encode_pixel_data')`` or
            ``('pydicom.pixels.decoders.pylibjpeg', 'decode_pixel_data')``).

        Raises
        ------
        ModuleNotFoundError
            If the module import path is incorrect or unavailable.
        AttributeError
            If the plugin's required functions and attributes aren't found in
            the module.
        """
        if label in self._available or label in self._unavailable:
            raise ValueError(
                f"'{type(self).__name__}' already has a plugin named '{label}'"
            )

        module = import_module(import_path[0])

        # `is_available(UID)` is required for plugins
        if module.is_available(self.UID):
            self._available[label] = getattr(module, import_path[1])
        else:
            # `DE/ENCODER_DEPENDENCIES[UID]` is required for plugins
            if self._decoder:
                deps = module.DECODER_DEPENDENCIES
            else:
                deps = module.ENCODER_DEPENDENCIES

            if self.UID not in deps:
                raise ValueError(
                    f"The '{label}' plugin doesn't support '{self.UID.name}'"
                )

            self._unavailable[label] = deps[self.UID]

    def add_plugins(self, plugins: list[tuple[str, tuple[str, str]]]) -> None:
        """Add multiple plugins to the class instance.

        .. warning::

            This method is not thread-safe.

        The requirements for encoding plugins are available
        :doc:`here</guides/encoding/encoder_plugins>`, while the requirements
        for decoding plugins are available :doc:`here
        </guides/decoding/decoder_plugins>`.

        Only encoding plugins should be added to
        :class:`~pydicom.pixels.encoders.base.Encoder` class instances
        and only decoding plugins should be added to
        :class:`~pydicom.pixels.decoders.base.Decoder` class instances.

        Parameters
        ----------
        plugins : list[tuple[str, tuple[str, str]]]
            A list of [label, import path] for the plugins, where:

            * `label` is the label to use for the plugin, which should be unique.
            * `import path` is the module import path and the function's
              name (e.g. ``('pydicom.pixels.encoders.pylibjpeg', 'encode_pixel_data')``
              or ``('pydicom.pixels.decoders.pylibjpeg', 'decode_pixel_data')``).
        """
        for label, import_path in plugins:
            self.add_plugin(label, import_path)

    @property
    def available_plugins(self) -> tuple[str, ...]:
        """Return a tuple containing available plugins."""
        return tuple(sorted(self._available.keys()))

    @property
    def is_available(self) -> bool:
        """Return ``True`` if plugins are available that can be used to encode or
        decode data, ``False`` otherwise.
        """
        if self._decoder and not self.UID.is_encapsulated:
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
        """Return nice strings for plugins with missing dependencies."""
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

    def remove_plugin(self, label: str) -> None:
        """Remove a plugin.

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
        """Return the corresponding *Transfer Syntax UID* as :class:`~pydicom.uid.UID`."""
        return self._uid

    def _validate_plugins(
        self, plugin: str = ""
    ) -> dict[str, "DecodeFunction"] | dict[str, "EncodeFunction"]:
        """Return available plugins.

        Parameters
        ----------
        plugin : str, optional
            If not used (default) then return all available plugins, otherwise
            only return the plugin with a matching name (if it's available).

        Returns
        -------
        dict[str, DecodeFunction] | dict[str, EncodeFunction]
            A dict of available {plugin name: decode/encode function} that can
            be used to decode/encode the corresponding pixel data.
        """
        if self._decoder and not self.UID.is_encapsulated:
            return {}  # type: ignore[return-value]

        if plugin:
            if plugin in self.available_plugins:
                return {plugin: self._available[plugin]}

            if deps := self._unavailable.get(plugin, None):
                missing = deps[0]
                if len(deps) > 1:
                    missing = f"{', '.join(deps[:-1])} and {deps[-1]}"

                if self._decoder:
                    raise RuntimeError(
                        f"Unable to decompress '{self.UID.name}' pixel data because "
                        f"the specified plugin is missing dependencies:\n\t{plugin} "
                        f"- requires {missing}"
                    )

                raise RuntimeError(
                    f"Unable to compress the pixel data using '{self.UID.name}' because "
                    f"the specified plugin is missing dependencies:\n\t{plugin} "
                    f"- requires {missing}"
                )

            msg = (
                f"No plugin named '{plugin}' has been added to '{self.UID.keyword}"
                f"{type(self).__name__}'"
            )
            if self._available:
                msg += f", available plugins are: {', '.join(self.available_plugins)}"

            raise ValueError(msg)

        if self._available:
            return self._available.copy()

        missing = "\n".join([f"\t{s}" for s in self.missing_dependencies])
        if self._decoder:
            raise RuntimeError(
                f"Unable to decompress '{self.UID.name}' pixel data because all "
                f"plugins are missing dependencies:\n{missing}"
            )

        raise RuntimeError(
            f"Unable to compress the pixel data using '{self.UID.name}' because all "
            f"plugins are missing dependencies:\n{missing}"
        )


# TODO: Python 3.11 switch to StrEnum
@unique
class PhotometricInterpretation(str, Enum):
    """Values for (0028,0004) *Photometric Interpretation*"""

    # Standard Photometric Interpretations from C.7.6.3.1.2 in Part 3
    MONOCHROME1 = "MONOCHROME1"
    MONOCHROME2 = "MONOCHROME2"
    PALETTE_COLOR = "PALETTE COLOR"
    RGB = "RGB"
    YBR_FULL = "YBR_FULL"
    YBR_FULL_422 = "YBR_FULL_422"
    YBR_ICT = "YBR_ICT"
    YBR_RCT = "YBR_RCT"
    HSV = "HSV"  # Retired
    ARGB = "ARGB"  # Retired
    CMYK = "CMYK"  # Retired
    YBR_PARTIAL_422 = "YBR_PARTIAL_422"  # Retired
    YBR_PARTIAL_420 = "YBR_PARTIAL_420"  # Retired

    # TODO: no longer needed if StrEnum
    def __str__(self) -> str:
        return str.__str__(self)


class RunnerBase:
    """Base class for the pixel data decoding/encoding process managers."""

    def __init__(self, tsyntax: UID) -> None:
        """Create a new runner for encoding/decoding data.

        Parameters
        ----------
        tsyntax : pydicom.uid.UID
            The transfer syntax UID corresponding to the pixel data to be
            decoded.
        """
        # Runner options
        self._opts: DecodeOptions | EncodeOptions = {}
        self.set_option("transfer_syntax_uid", tsyntax)
        # Runner options that cannot be deleted, only modified
        self._undeletable: tuple[str, ...] = ("transfer_syntax_uid",)

        # The source type, one of "Dataset", "Buffer", "Array" or "BinaryIO"
        self._src_type = "UNDEFINED"

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

    def del_option(self, name: str) -> None:
        """Delete option `name` from the runner."""
        if name in self._undeletable:
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

    def frame_length(self, unit: str = "bytes") -> int | float:
        """Return the expected length (in number of bytes or pixels) of each
        frame of pixel data.

        Parameters
        ----------
        unit : str, optional
            If ``"bytes"`` then returns the expected length of the pixel data
            in whole bytes and NOT including an odd length trailing NULL
            padding byte. If ``"pixels"`` then returns the expected length of
            the pixel data in terms of the total number of pixels (default
            ``"bytes"``).

        Returns
        -------
        int | float
            The expected length of a single frame of pixel data in either whole
            bytes or pixels, excluding the NULL trailing padding byte for odd
            length data. For "pixels", an integer will always be returned. For
            "bytes", a float will be returned for images with BitsAllocated of
            1 whose frames do not consist of a whole number of bytes.
        """
        length: int | float = self.rows * self.columns * self.samples_per_pixel

        if unit == "pixels":
            return length

        # Correct for the number of bytes per pixel
        if self.bits_allocated == 1:
            if self.transfer_syntax.is_encapsulated:
                # Determine the nearest whole number of bytes needed to contain
                # 1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits,
                # which are packed into 12.5 -> 13 bytes
                length = length // 8 + (length % 8 > 0)
            else:
                # For native, "bit-packed" pixel data, frames are not padded so
                # this may not be a whole number of bytes e.g. 10x10 = 100
                # pixels images are packed into 12.5 bytes
                length = length / 8
                if length.is_integer():
                    length = int(length)
        else:
            length *= self.bits_allocated // 8

        # DICOM Standard, Part 4, Annex C.7.6.3.1.2 - native only
        if (
            self.photometric_interpretation == PhotometricInterpretation.YBR_FULL_422
            and not self.transfer_syntax.is_encapsulated
        ):
            length = length // 3 * 2

        return length

    def get_option(self, name: str, default: Any = None) -> Any:
        """Return the value of the option `name`."""
        return self._opts.get(name, default)

    @property
    def is_array(self) -> bool:
        """Return ``True`` if the pixel data source is an :class:`~numpy.ndarray`"""
        return self._src_type == "Array"

    @property
    def is_binary(self) -> bool:
        """Return ``True`` if the pixel data source is BinaryIO"""
        return self._src_type == "BinaryIO"

    @property
    def is_buffer(self) -> bool:
        """Return ``True`` if the pixel data source is a buffer-like"""
        return self._src_type == "Buffer"

    @property
    def is_dataset(self) -> bool:
        """Return ``True`` if the pixel data source is a :class:`~pydicom.dataset.Dataset`"""
        return self._src_type == "Dataset"

    @property
    def number_of_frames(self) -> int:
        """Return the expected number of frames in the data."""
        if (value := self._opts.get("number_of_frames", None)) is not None:
            return value

        raise AttributeError("No value for 'number_of_frames' has been set")

    @property
    def options(self) -> "DecodeOptions | EncodeOptions":
        """Return a reference to the runner's options dict."""
        return self._opts

    @property
    def photometric_interpretation(self) -> str:
        """Return the expected photometric interpretation of the data."""
        if (value := self._opts.get("photometric_interpretation", None)) is not None:
            return value

        raise AttributeError("No value for 'photometric_interpretation' has been set")

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

    def set_option(self, name: str, value: Any) -> None:
        """Set a runner option.

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
                warn_and_log(
                    f"A value of '{value}' for (0028,0008) 'Number of Frames' is "
                    "invalid, assuming 1 frame"
                )
                value = 1
        elif name == "photometric_interpretation":
            if value == "PALETTE COLOR":
                value = PhotometricInterpretation.PALETTE_COLOR
            try:
                value = PhotometricInterpretation[value]
            except KeyError:
                pass

        self._opts[name] = value  # type: ignore[literal-required]

    def set_options(self, **kwargs: "DecodeOptions | EncodeOptions") -> None:
        """Set multiple runner options.

        Parameters
        ----------
        kwargs : dict[str, Any]
            A dictionary containing the options as ``{name: value}``, where
            `name` is the name of the option and `value` is it's value.
        """
        for name, value in kwargs.items():
            self.set_option(name, value)

    def _set_options_ds(self, ds: "Dataset") -> None:
        """Set options using a dataset.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to use.
        """
        self.set_options(**as_pixel_options(ds))

    @property
    def transfer_syntax(self) -> UID:
        """Return the expected transfer syntax corresponding to the data."""
        return self._opts["transfer_syntax_uid"]

    def validate(self) -> None:
        """Validate the runner options and source data (if any)."""
        raise NotImplementedError(
            f"{type(self).__name__}.validate() has not been implemented"
        )

    def _validate_options(self) -> None:
        """Validate the supplied options to ensure they meet requirements."""
        prefix = "Missing required element: (0028"
        if self._opts.get("bits_allocated") is None:
            raise AttributeError(f"{prefix},0100) 'Bits Allocated'")

        if not 1 <= self.bits_allocated <= 64 or (
            self.bits_allocated != 1 and self.bits_allocated % 8
        ):
            raise ValueError(
                f"A (0028,0100) 'Bits Allocated' value of '{self.bits_allocated}' "
                "is invalid, it must be 1 or a multiple of 8 and in the range (1, 64)"
            )

        if "Float" not in self.pixel_keyword:
            if self._opts.get("bits_stored") is None:
                raise AttributeError(f"{prefix},0101) 'Bits Stored'")

            if not 1 <= self.bits_stored <= self.bits_allocated <= 64:
                raise ValueError(
                    f"A (0028,0101) 'Bits Stored' value of '{self.bits_stored}' is "
                    "invalid, it must be in the range (1, 64) and no greater than "
                    "the (0028,0100) 'Bits Allocated' value of "
                    f"'{self.bits_allocated}'"
                )

        if self._opts.get("columns") is None:
            raise AttributeError(f"{prefix},0011) 'Columns'")

        if not 0 < self.columns <= 2**16 - 1:
            raise ValueError(
                f"A (0028,0011) 'Columns' value of '{self.columns}' is invalid, "
                "it must be in the range (1, 65535)"
            )

        # Number of Frames is conditionally required
        if self._opts.get("number_of_frames") is not None and self.number_of_frames < 1:
            raise ValueError(
                f"A (0028,0008) 'Number of Frames' value of '{self.number_of_frames}' "
                "is invalid, it must be greater than or equal to 1"
            )

        if self._opts.get("photometric_interpretation") is None:
            raise AttributeError(f"{prefix},0004) 'Photometric Interpretation'")

        try:
            PhotometricInterpretation[self.photometric_interpretation]
        except KeyError:
            if self.photometric_interpretation != "PALETTE COLOR":
                raise ValueError(
                    "Unknown (0028,0004) 'Photometric Interpretation' value "
                    f"'{self.photometric_interpretation}'"
                )

        kw = ("PixelData", "FloatPixelData", "DoubleFloatPixelData")
        if self.pixel_keyword not in kw:
            raise ValueError(f"Unknown 'pixel_keyword' value '{self.pixel_keyword}'")

        if self.pixel_keyword == "PixelData":
            if self._opts.get("pixel_representation") is None:
                raise AttributeError(f"{prefix},0103) 'Pixel Representation'")

            if self.pixel_representation not in (0, 1):
                raise ValueError(
                    "A (0028,0103) 'Pixel Representation' value of "
                    f"'{self.pixel_representation}' is invalid, it must be 0 or 1"
                )

        if self._opts.get("rows") is None:
            raise AttributeError(f"{prefix},0010) 'Rows'")

        if not 0 < self.rows <= 2**16 - 1:
            raise ValueError(
                f"A (0028,0010) 'Rows' value of '{self.rows}' is invalid, it "
                "must be in the range (1, 65535)"
            )

        if self._opts.get("samples_per_pixel") is None:
            raise AttributeError(f"{prefix},0002) 'Samples per Pixel'")

        if self.samples_per_pixel not in (1, 3):
            raise ValueError(
                f"A (0028,0002) 'Samples per Pixel' value of '{self.samples_per_pixel}' "
                "is invalid, it must be 1 or 3"
            )

        if self.samples_per_pixel == 3:
            if self._opts.get("planar_configuration") is None:
                raise AttributeError(f"{prefix},0006) 'Planar Configuration'")

            if self.planar_configuration not in (0, 1):
                raise ValueError(
                    "A (0028,0006) 'Planar Configuration' value of "
                    f"'{self.planar_configuration}' is invalid, it must be 0 or 1"
                )


class RunnerOptions(TypedDict, total=False):
    """Options accepted by RunnerBase"""

    ## Pixel data description options
    # Required
    bits_allocated: int
    bits_stored: int
    columns: int
    number_of_frames: int
    photometric_interpretation: str
    pixel_keyword: str
    pixel_representation: int
    rows: int
    samples_per_pixel: int
    transfer_syntax_uid: UID

    # Conditionally required if samples_per_pixel > 1
    planar_configuration: int

    # Optional
    # The Extended Offset Table values
    extended_offsets: tuple[bytes, bytes] | tuple[list[int], list[int]]
