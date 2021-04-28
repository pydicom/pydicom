"""Bulk data encoding.

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
"""
from importlib import import_module
import sys
from typing import Callable, Generator, Tuple, List, Optional, Dict

from pydicom.encaps import encapsulate
from pydicom.uid import UID, RLELossless

try:
    import numpy as np
except ImportError:
    pass


# TODO:
# Add docs for requirements of a plugin
#   Method for encoding a frame (without dataset) -> bytes
#   Method for encoding a array (with dataset) -> Generator[bytes]
#   Method for encoding a frame (with dataset) -> bytes
class EncoderFactory:
    """Factory class for data encoders."""
    def __init__(self, uid: UID, data_type: str = 'PixelData') -> None:
        """Create a new data encoder.

        Parameteres
        -----------
        uid : pydicom.uid.UID
            The *Transfer Syntax UID* that the encoder supports.
        data_type : str, optional
            The data type the encoder is used for. Currently only
            ``'PixelData'`` is available.
        """
        # The *Transfer Syntax UID* data will be encoded to
        self._uid = uid
        # The data type the encoder is used for
        self._data_type = data_type
        # Available encoders
        self._available: Dict[str, Callable] = {}
        # Unavailable encoders
        self._unavailable: Dict[str, str] = {}
        # Default encoding options
        self._defaults = {
            'transfer_syntax': self.UID,
            'byteorder': '<',
        }

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the encoder has available plugins and can be
        used to encode data, ``False`` otherwise.
        """
        return bool(self._available)

    def deregister_plugin(self, label: str) -> None:
        """Deregister a plugin from the encoder.

        Parameters
        ----------
        label : str
            The label of the plugin to deregister.
        """
        if label in self._available:
            del self._available[package]

        if label in self._unavailable:
            del self._unavailable

    # TODO
    # Add a method for standalone (datasetless) encoding?
    def encode(
        self, arr: "np.ndarray", ds: Optional["Dataset"] = None, **kwargs
    ) -> bytes:
        """Return the single-framed `arr` as encoded bytes.

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of uncompressed pixel data. Should be shaped as
            (Rows, Columns) or (Rows, Columns, Samples) or the corresponding
            1D array.
        ds : pydicom.dataset.Dataset, optional
            The dataset corresponding to `arr`. If not used then `kwargs` must
            contain all the parameters required by the encoder.
        **kwargs
            Optional parameters for the encoding function. If `ds` is not used
            then, at a minimum, the following are required:

            * ``'rows'`` - the number of rows in `arr`
            * ``'columns'`` - the number of columns in `arr`
            * ``'samples_per_pixel'`` - the number of samples per pixel in
              `arr`
            * ``'bits_allocated'`` - the number of bits per pixel in `arr`
            * ``'bits_stored'`` - the number of bits actually used per pixel
              in `arr`
            * ``'pixel_representation'`` - something
            * ``'photometric_interpretation'`` - the photometric interpretation
              of the pixels in `arr`

        Returns
        -------
        bytes
            The encoded pixel data.
        """
        return self._encode_frame(arr, ds, **kwargs)

    def _encode_frame(
        self, arr: "np.ndarray", ds: "Dataset", **kwargs
    ) -> bytes:
        """Return an encoded frame from `arr`.

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of uncompressed pixel data. Should be shaped as
            (Rows, Columns) or (Rows, Columns, Samples) or the corresponding
            1D array.
        ds : pydicom.dataset.Dataset or None
            The dataset corresponding to `arr`, if ``None`` then `kwargs` must
            contain all the parameters required by the encoder.
        **kwargs
            Optional parameters for the encoder.

        Returns
        ------
        bytes
            The encoded pixel data frame.
        """
        # Add our defaults, but don't overwrite existing options
        kwargs = {**self._default, **kwargs}

        # Or create ds... hmm
        if ds:
            kwargs['rows'] = ds.Rows
            kwargs['columns'] = ds.Columns
            kwargs['samples_per_pixel'] = ds.SamplesPerPixel
            kwargs['bits_allocated'] = ds.BitsAllocated
            kwargs['bits_stored'] = ds.BitsStored
            kwargs['number_of_frames'] = getattr(ds, "NumberOfFrames", 1) or 1
            kwargs['pixel_representation'] = ds.PixelRepresentation
            kwargs['photometric_interpretation'] = ds.PhotometricInterpretation

        # Process the pixel array and convert to little-endian ordered bytes
        src = self._preprocess(arr, ds, **kwargs)

        failed_encoders = []
        if 'use_package' in kwargs:
            name = kwargs['use_package']
            # Try specific encoder
            try:
                return self._available[name](src, ds, **kwargs)
            except Exception as exc:
                failed_encoders.append(name)
        else:
            # Try all available encoders
            for name, func in self._available.items():
                try:
                    return func(src, ds, **kwargs)
                except Exception as exc:
                    failed_encoders.append((name, exc))

        # TODO: better exception message -> add exception to msg
        raise RuntimeError(
            f"Unable to encode the pixel data using the following packages: "
            f"{','.join(failed_encoders)}"
        )

    def iter_encode(
        self, arr: "np.ndarray", ds: Optional["Dataset"] = None, **kwargs
    ) -> Generator[bytes, None, None]:
        """Yield an encoded frame from single or multi-framed `arr`.

        Parameters
        ----------
        arr : numpy.ndarray
            The uncompressed single or multi-framed pixel data. Should be
            shaped as (Rows, Columns), (Rows, Columns, Samples), (Frames,
            Rows, Columns), (Frames, Rows, Columns, Samples) or the
            corresponding 1D array.
        ds : pydicom.dataset.Dataset
            The dataset corresponding to `arr`.
        **kwargs
            Optional parameters for the encoding function.

        Yields
        ------
        bytes
            An encoded pixel data frame.
        """
        nr_frames = getattr(ds, 'NumberOfFrames', 1) or 1
        if nr_frames > 1:
            for frame in arr:
                yield self._encode_frame(frame, ds, **kwargs)
        else:
            yield self._encode_frame(arr, ds, **kwargs)

    @property
    def name(self) -> str:
        """Return the name of the encoder."""
        return f"{self.UID.keyword}Encoder"

    @property
    def plugins(self) -> List[str]:
        """Return a list of labels for plugins registered with the encoder."""
        return list(self._available.keys()) + list(self._unavailable.keys())

    @property
    def plugin_dependencies(self) -> List[str]:
        # What is this for?
        pass

    def _preprocess(self, arr: "np.ndarray", ds: "Dataset", **kwargs) -> bytes:
        """Process `arr` before encoding to ensure it meets requirements.

        `arr` will be checked and modified if necessary to match the `ds`
        DICOM dataset before being converted to raw bytes.

        The following modifications may be made to `arr` prior to conversion
        to bytes:

        * Each value will be contained using *Bits Allocated* number of bits,
          which means `arr` will have its itemsize increased or decreased
          accordingly. If doing so will result in over or underflowing pixel
          values then a :class:`ValueError` exception will be raised.
        * When the *Bits Allocated* is greater than 8, the array will be
          converted to little-endian byte ordering.

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of uncompressed pixel data. Should be shaped as
            (Rows, Columns) or (Rows, Columns, Samples) or the corresponding
            1D array.
        ds : pydicom.dataset.Dataset
            The dataset corresponding to `arr`.
        **kwargs
            Optional parameters for the processing, none are currently
            available.

        Returns
        -------
        bytes
            The pixel data `arr` converted to little-endian ordered bytes.
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
        byteorder = self.system_endianness if byteorder == '=' else byteorder
        if byteorder == '>':
            arr = arr.astype(arr.dtype.newbyteorder('<'))

        return arr.tobytes()

    # TODO: err_msg is probably redundant, but would be nice for complicated cases
    def register_plugin(
        self, label: str, path: Tuple[str, str], err_msg: Optional[str] = None
    ) -> None:
        """Register a plugin with the encoder.

        Parameters
        ----------
        label : str
            The label to use for the plugin, should be unique.
        path : Tuple[str, str]
            The module import path and the encoding function name (e.g.
            ``('pydicom.encoders.pylibjpeg', 'encode_pixel_data')``).
        err_msg : str
            A message that may be displayed if unable to use the plugin's
            encoding function due to missing dependencies.
        """
        if label in self._available or label in self._unavailable:
            raise ValueError(
                f"'{self.name}' already has a plugin named '{label}'"
            )

        module = import_module(path[0])
        dependencies = getattr(module, "ENCODER_DEPENDENCIES")

        if module.is_available(self.UID):
            self._available[label] = getattr(module, path[1])
        else:
            self._unavailable[label] = (dependencies, err_msg)

    @property
    def system_endianness(self) -> str:
        """Return '<' if the system is little-endian, '>' otherwise"""
        return '<' if sys.byteorder == 'little' else '>'

    @property
    def UID(self) -> UID:
        """Return the *Transfer Syntax UID* corresponding to the encoder"""
        return self._uid


# Encoder names should be f"{UID.keyword}Encoder"
RLELosslessEncoder = EncoderFactory(RLELossless)
RLELosslessEncoder.register_plugin(
    'pylibjpeg',
    ('pydicom.encoders.pylibjpeg', 'encode_pixel_data'),
    'numpy and pylibjpeg (with the pylibjpeg-rle plugin)'
)
RLELosslessEncoder.register_plugin(
    'pydicom',
    ('pydicom.pixel_data_handlers.rle_handler', '_wrap_encode_frame'),
)


# Available pixel data encoders
_PIXEL_DATA_ENCODERS = {
    RLELossless: RLELosslessEncoder,
}


def get_encoder(uid, encoder_type='PixelData'):
    """Return an encoder for `uid`."""
    try:
        return _PIXEL_DATA_ENCODERS[uid]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data encoders have been implemented for '{uid.name}'"
        )
