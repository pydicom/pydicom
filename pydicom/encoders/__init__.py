"""Bulk data encoding.

>>> from pydicom.encoders import RLELosslessEncoder as encoder
>>> encoder.package
'gdcm'
>>> encoder.encode(ds: Dataset, **kwargs)
b'\x00...
>>> encoder.encode(arr: np.ndarray, ds, **kwargs)
b'\x00...
>>> encoder.encode(data: bytes, ds, **kwargs)
b'\x00...
>>> encoder.use_package('pylibjpeg')
RuntimeError: The 'pylibjpeg' package requires the 'pylibjpeg-rle' plugin
  to encode RLE Lossless

Examples
--------

Recurse through the current directory and compress all the datasets:

.. codeblock:: python

    from pathlib import Path

    from pydicom import dcmread
    from pydicom.uid import RLELossless

    for p in Path().glob('**/*'):
        ds = dcmread(p)
        ds.compress(RLELossless)
        ds.save_as(p)


Customise an encoder to suit your needs:

    from pydicom.encoders import RLELosslessEncoder

    encoder = RLELosslessEncoder
    encoder.use_package("pylibjpeg")
    # Input data is ordered big-endian
    encoder.set_options({"byteorder": '>'})
    # This is really redundant, you can do the same with
    ds.compress(RLELossless, **{'byteorder': '>'})

Encoder internals
    ?
"""
import sys
from typing import Callable, Generator

from pydicom.encaps import encapsulate
from pydicom.uid import UID, RLELossless

try:
    import numpy as np
except ImportError:
    pass


class EncoderFactory:
    """Factory class for *Pixel Data* encoders."""
    def __init__(self, uid: UID) -> None:
        # The *Transfer Syntax UID* data will be encoded to
        self._uid = uid
        # Available encoders (dependencies are met)
        self._available = {}
        # Unavailable encoders (dependencies not met)
        self._unavailable = {}
        # Hmm... need to be careful of state management with this
        self._package = None

    def add_decoder(self, package: str, func: Callable, err_msg: str) -> None:
        """Add an encoder function to the encoder.

        Parameters
        ----------
        package : str
            The name of the package that supplies the encoder.
        func : FIXME
            The entry point for the encoder function.
        err_msg : str
            The message to display if unable to import the encoder function.
        """
        try:
            # FIXME: try and import
            self._available[package] = func
        except ImportError:
            self._unavailable[package] = err_msg

    @property
    def available(self) -> bool:
        """Return ``True`` if the encoder has available packages."""
        return bool(self._available)

    @property
    def dependencies(self) -> Tuple[List[str]]:
        pass

    def _process_frame(self, arr: "np.ndarray", ds: "Dataset", **kwargs) -> bytes:
        """Check if arr is squeezable to ds and return LE uint8s as bytes.

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of uncompressed pixel data.
        ds : pydicom.dataset.Dataset
            The corresponding dataset.

        Returns
        -------
        bytes
            The array convert to bytes, with each pixel contained
            using *Bits Allocated* number of bits. The upper-leftmost pixel
            will be (possibly partly) contained by the first byte and the
            lower-rightmost pixel by the last byte. When the *Samples per
            Pixel* is greater than 1 the bytes will be ordered as (for RGB
            data) R1, G1, B1, R2, G2, B2, ... (i.e. *Planar Configuration* 0).
            When *Bits Allocated* is greater than 8 the bytes will use
            little-endian byte ordering.
        """
        # Check *Rows*, *Columns*, *Samples per Pixel* match array
        nr_samples = getattr(ds, 'SamplesPerPixel', 1) or 1
        _shape_check = {
            1: (ds.Rows * ds.Columns * nr_samples, ),
            2: (ds.Rows, ds.Columns),
            3: (ds.Rows, ds.Columns, nr_samples),
        }

        if len(arr.shape) > 3:
            raise ValueError("The maximum supported array dimensions is 4")

        # FIXME: 1D array fail on first condition, add test
        if (
            (nr_samples > 1 and len(arr.shape) != 3)
            or (_shape_check[len(arr.shape)] != arr.shape)
        ):
            raise ValueError("The shape of the array doesn't match the dataset")

        # Check *Pixel Representation* matches array
        ui = [
            np.issubdtype(arr.dtype, np.unsignedinteger),
            np.issubdtype(arr.dtype, np.signedinteger)
        ]

        # FIXME: add test
        if not any(ui):
            raise ValueError(
                "Invalid dtype kind, must be signed or unsigned integer"
            )

        if not ui[ds.PixelRepresentation]:
            raise ValueError(
                "Incompatible array dtype and dataset 'Pixel Representation'"
            )

        # Ensure *Bits Allocated* value is supported
        if ds.BitsAllocated not in (8, 16, 32, 64):
            raise ValueError(
                "Unsupported 'Bits Allocated' must be 8, 16, 32 or 64"
            )

        # Ensure *Samples per Pixel* value is supported
        if ds.SamplesPerPixel not in (1, 3):
            raise ValueError("Unsupported 'Samples per Pixel' must be 1 or 3")

        # Change array itemsize to match *Bits Allocated*, if possible
        bytes_allocated = ds.BitsAllocated // 8
        if bytes_allocated != arr.dtype.itemsize:
            # Check we won't clip the dataset if shrinking the itemsize
            if bytes_allocated < arr.dtype.itemsize:
                value_max, value_min = 2**ds.BitsAllocated - 1, 0
                if bool(ds.PixelRepresentation):
                    value_max = 2**(ds.BitsAllocated - 1) - 1
                    value_min = -2**(ds.BitsAllocated - 1)

                if arr.min() < value_min or arr.max() > value_max:
                    raise ValueError(
                        "Cannot modify the array to match 'Bits Allocated' "
                        "without clipping the pixel values"
                    )

            byteorder = '|' if ds.BitsAllocated == 8 else '<'
            arr = arr.astype(f"{byteorder}{arr.dtype.kind}{bytes_allocated}")

            # For signed need to bitwise and 0xff * (bytes_allocated - 1)
            # if less than 0

        # Convert the array to the required byte order (little-endian)
        # `byteorder` may be
        #   '|': none available, such as for 8 bit -> ignore
        #   '=': native system endianness -> change to '<' or '>'
        #   '<' or '>': little or big
        byteorder = arr.dtype.byteorder
        byteorder = self.endianness if byteorder == '=' else byteorder
        if byteorder == '>':
            arr = arr.astype(arr.dtype.newbyteorder('<'))

        return arr.tobytes()

    def encode(self, arr: "np.ndarray", ds: "Dataset", **kwargs) -> bytes:
        """

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of unencoded pixel data.
        ds : pydicom.dataset.Dataset
            The corresponding dataset.
        """
        return self._encode_frame(arr, ds, **kwargs)

    def encode_array(
        self, arr: "np.ndarray", ds: "Dataset", **kwargs
    ) -> Generator[bytes, None, None]:
        """Yields encoded frames.

        Parameters
        ----------
        arr : numpy.ndarray
            An ndarray containing one or more frames of unencoded pixel data.
        ds : pydicom.dataset.Dataset
            The corresponding dataset.
        """
        nr_frames = getattr(ds, 'NumberOfFrames', 1) or 1
        if nr_frames > 1:
            for frame in arr:
                yield self._encode_frame(frame, ds, **kwargs)
        else:
            yield self._encode_frame(arr, ds, **kwargs)

    def _encode_frame(self, arr: "np.ndarray", ds: "Dataset", **kwargs) -> bytes:
        """
        """
        arr = self._process_frame(arr, ds, **kwargs)
        failed_encoders = []

        if self._package:
            # Try specific encoder
            try:
                return self._available[name](arr, ds, **kwargs)
            except Exception as exc:
                failed_encoders.append(name)
        else:
            # Try all available encoders
            for name, func in self._available.items():
                try:
                    return func(arr, ds, **kwargs)
                except Exception as exc:
                    failed_encoders.append(name)

        # TODO: better exception message -> add exception to msg
        raise RuntimeError(
            f"Unable to encode the pixel data using the following packages: "
            f"{','.join(failed_encoders)}"
        )

    @property
    def endianness(self) -> str:
        """Return '<' if the system is little-endian, '>' otherwise"""
        return '<' if sys.byteorder == 'little' else '>'

    @property
    def uid(self) -> UID:
        """Return the encoder's corresponding *Transfer Syntax UID*"""
        return self._uid

    def use_package(self, package: Optional[str]) -> None:
        # FIXME
        if not package:
            self._package = None
        elif package in self._available:
            self._package = package
        elif package in self._unavailable:
            raise ValueError(
                f"The {package} is missing required dependencies: {}"
            )
        else:
            raise ValueError(
                f"{package} is not a package registered for use with the "
                f"{self.__class__.__name__} encoder. Available packages are: "
                f"{self._available.keys()}"
            )



RLELosslessEncoder = EncoderFactory(RLELossless)
RLELosslessEncoder.add_decoder(
    'pydicom',
    'pydicom.pixel_data_handlers.rle_handler.encode_rle_frame',
    'numpy'
)
RLELosslessEncoder.add_decoder(
    'pylibjpeg',
    'pylibjpeg.encode_pixel_data',
    'numpy and pylibjpeg (with the pylibjpeg-rle plugin)'
)


# Available pixel data encoders
_ENCODERS = {
    RLELossless: RLELosslessEncoder,
}


def get_encoder(uid):
    """Return an encoder for `uid`."""
    try:
        return _ENCODERS[uid]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data encoders have been implemented for '{uid}'"
        )
