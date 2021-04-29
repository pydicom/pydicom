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

Save encoded *Pixel Data* to file (single or multi-framed):

.. codeblock:: python

    from pydicom import dcmread
    from pydicom.data import get_testdata_file
    from pydicom.encoders import RLELosslessEncoder as encoder

    ds = get_testdata_file("CT_small.dcm", read=True)

    with open('pixel_data.rle', 'wb') as f:
        f.write(encoder.encode(..., ds, frame=0))  # no arr :< -> add new method
"""
from importlib import import_module
import sys
from typing import Callable, Generator, Tuple, List, Optional, Dict, Any

from pydicom.encaps import encapsulate
from pydicom.uid import UID, RLELossless

try:
    import numpy as np
except ImportError:
    pass


# TODO:
# Add docs for requirements of a plugin
class EncoderFactory:
    """Factory class for data encoders.

    .. versionadded:: 2.2
    """
    def __init__(self, uid: UID) -> None:
        """Create a new data encoder.

        Parameteres
        -----------
        uid : pydicom.uid.UID
            The *Transfer Syntax UID* that the encoder supports.
        """
        # The *Transfer Syntax UID* data will be encoded to
        self._uid = uid
        # Available encoders
        self._available: Dict[str, Callable] = {}
        # Unavailable encoders
        self._unavailable: Dict[str, str] = {}
        # Default encoding options
        self._defaults = {
            'transfer_syntax_uid': self.UID,
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

    def encode(
        self,
        ds: "Dataset",
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        decoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return an encoded frame of the *Pixel Data* in  `ds` as
        :class:`bytes`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset, optional
            The dataset containing the *Pixel Data* to be encoded.
        idx : int, optional
            When the *Pixel Data* in `ds` contains multiple frames, this is
            the index of the frame to be encoded.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        decoding_plugin : str, optional
            The name of the pixel data decoding handler to use if `ds` contains
            compressed *Pixel Data*. If `decoding_plugin` is not specified then
            all available handlers will be tried.
        **kwargs
            [FIXME] Optional parameters for the encoding plugin. See the
            documentation for the encoding plugins for what options are
            available.

        Returns
        -------
        bytes
            The encoded pixel data.
        """
        try:
            kwargs.update(self.kwargs_from_ds(ds))
        except AttributeError as exc:
            raise AttributeError("FIXME") from exc

        if decoding_plugin:
            ds.convert_pixel_data(handler_name=decoding_plugin)

        arr = ds.pixel_array

        if idx is None and kwargs['number_of_frames'] > 1:
            raise ValueError("FIXME")
        else:
            arr = arr[idx]

        return self._encode(arr, idx, encoding_plugin, **kwargs)

    def encode_array(
        self,
        arr: "np.ndarray",
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return an encoded frame from `arr` as :class:`bytes`.

        Parameters
        ----------
        arr : numpy.ndarray
            A single or multi-framed :class:`~numpy.ndarray` containing
            uncompressed pixel data. Should be shaped as:

            * (Rows, Columns) for single frame, single sample data.
            * (Rows, Columns, Samples) for single frame, multi-sample data.
            * (Frames, Rows, Columns) for multi framed, single sample data.
            * (Frames, Rows, Columns, Samples) for multi-framed and
              multi-sample data.
            * or the corresponding 1D array you'd get from ``arr.ravel()``.

            For multi-sample data `arr` should be in RGB colorspace.
        idx : int, optional
            When `arr` contains multiple frames, this is the index of the
            frame to be encoded.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        **kwargs
            The following parameters are required:

            * ``'rows': int`` - the number of rows in `arr`, maximum 65535.
            * ``'columns': int`` - the number of columns in `arr`, maximum
              65535.
            * ``'samples_per_pixel': int`` - the number of samples per pixel in
              `arr`, should be 1 or 3.
            * ``'bits_allocated': int`` - the number of bits used to contain
              the pixel data, should be 8, 16, 32 or 64.
            * ``'bits_stored': int`` - the number of bits actually used per
              pixel in `arr`. For example, `arr` might have a
              :class:`~numpy.dtype` of 'uint16' (range 0 to 65535) but only
              contain 12-bit pixel values (range 0 to 4095).

            `kwargs` may also contain optional parameters for the encoding
            function. See the [FIXME] documentation for the encoding plugins
            for what options are available.
        """
        if idx is None and kwargs['number_of_frames'] > 1:
            raise ValueError("FIXME")
        else:
            arr = arr[idx]

        return self._encode(arr, idx, encoding_plugin, **kwargs)

    def iter_encode(
        self,
        ds: "Dataset",
        encoding_plugin: str = '',
        decoding_plugin: str = '',
        **kwargs
    ) -> Generator[bytes, None, None]:
        """Yield an encoded frame of the *Pixel Data* in  `ds` as
        :class:`bytes`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset, optional
            The dataset containing the *Pixel Data* to be encoded.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        decoding_plugin : str, optional
            The name of the pixel data decoding handler to use if `ds` contains
            compressed *Pixel Data*. If `decoding_plugin` is not specified then
            all available handlers will be tried.
        **kwargs
            FIXME Optional parameters for the encoding plugin. See the
            documentation for the encoding plugins for what options are
            available.

        Yields
        ------
        bytes
            An encoded frame of pixel data.
        """
        try:
            kwargs.update(self.kwargs_from_ds(ds))
        except AttributeError as exc:
            raise AttributeError("FIXME") from exc

        if decoding_plugin:
            ds.convert_pixel_data(handler_name=decoding_plugin)

        arr = ds.pixel_array

        if kwargs['number_of_frames'] > 1:
            for frame in arr:
                yield self._process(frame, plugin=encoding_plugin, **kwargs)
        else:
            yield self._process(arr, plugin=encoding_plugin, **kwargs)

    def iter_encode_array(
        self,
        arr: "np.ndarray",
        encoding_plugin: str = '',
        **kwargs
    ) -> Generator[bytes, None, None]:
        """Yield an encoded frame from single or multi-framed `arr`.

        Parameters
        ----------
        arr : numpy.ndarray
            The uncompressed single or multi-framed pixel data. Should be
            shaped as (Rows, Columns), (Rows, Columns, Samples), (Frames,
            Rows, Columns), (Frames, Rows, Columns, Samples) or the
            corresponding 1D array.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        **kwargs
            FIXME

        Yields
        ------
        bytes
            An encoded pixel data frame.
        """
        if kwargs['number_of_frames'] > 1:
            for frame in arr:
                yield self._process(frame, plugin=encoding_plugin, **kwargs)
        else:
            yield self._process(arr, plugin=encoding_plugin, **kwargs)

    @staticmethod
    def kwargs_from_ds(ds: "Dataset") -> Dict[str, Any]:
        """Return a *kargs* dict from `ds`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to use as a source of keyword parameters.

        Returns
        -------
        Dict[str, Any]
            A dict with the following keys, with values from the corresponding
            dataset elements:

            * `rows`: int
            * `columns`: int
            * `samples_per_pixel`: int
            * `number_of_frames`: int, default ``1`` if not present
            * `bits_allocated`: int
            * `bits_stored`: int
            * `pixel_representation`: int
            * `photometric_interpretation`: str
        """
        kwargs = {
            'rows': ds.Rows,  # US
            'columns': ds.Columns,  # US
            'samples_per_pixel': ds.SamplesPerPixel,
            'number_of_frames': int(ds.get('NumberOfFrames', 1) or 1),  # IS
            'bits_allocated': ds.BitsAllocated,  # US
            'bits_stored': ds.BitsStored,  # US
            'pixel_representation': ds.PixelRepresentation,  # US
            'photometric_interpretation': ds.PhotometricInterpretation,  # CS
        }

        return kwargs

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

    def _preprocess(self, arr: "np.ndarray", **kwargs) -> bytes:
        """Process `arr` before encoding to ensure it meets requirements.

        `arr` will be checked and modified if necessary to match the required
        keys in `kwargs` before being converted to raw bytes.

        The following modifications may be made to `arr` prior to conversion
        to bytes:

        * Each value will be contained using `bits_allocated` number of bits,
          which means `arr` will have its itemsize increased or decreased
          accordingly. If doing so will result in over or underflowing pixel
          values then a :class:`ValueError` exception will be raised.
        * When `bits_allocated` is greater than 8, the array will be
          converted to little-endian byte ordering.

        Parameters
        ----------
        arr : numpy.ndarray
            A single frame of uncompressed pixel data. Should be shaped as
            (Rows, Columns) or (Rows, Columns, Samples) or the corresponding
            1D array.
        **kwargs
            Required parameters:

            * `rows`: int
            * `columns`: int
            * `samples_per_pixel`: int
            * `number_of_frames`: int
            * `bits_allocated`: int
            * `pixel_representation`: int

        Returns
        -------
        bytes
            The pixel data `arr` converted to little-endian ordered bytes.
        """
        # Check *Rows*, *Columns*, *Samples per Pixel* match array
        rows = kwargs['rows']
        cols = kwargs['columns']
        samples_per_pixel = kwargs['samples_per_pixel']
        bits_allocated = kwargs['bits_allocated']
        pixel_repr = kwargs['pixel_representation']

        _shape_check = {
            1: (rows * cols * samples_per_pixel, ),
            2: (rows, cols),
            3: (rows, cols, samples_per_pixel),
        }

        if len(arr.shape) > 3:
            raise ValueError("The maximum supported array dimensions is 4")

        # FIXME: 1D array fail on first condition, add test
        if (
            (samples_per_pixel > 1 and len(arr.shape) != 3)
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

        if not ui[pixel_repr]:
            raise ValueError(
                "Incompatible array dtype and dataset 'Pixel Representation'"
            )

        # Ensure *Bits Allocated* value is supported
        if bits_allocated not in (8, 16, 32, 64):
            raise ValueError(
                "Unsupported 'Bits Allocated' must be 8, 16, 32 or 64"
            )

        # Ensure *Samples per Pixel* value is supported
        if samples_per_pixel not in (1, 3):
            raise ValueError("Unsupported 'Samples per Pixel' must be 1 or 3")

        # Change array itemsize to match *Bits Allocated*, if possible
        bytes_allocated = bits_allocated // 8
        if bytes_allocated != arr.dtype.itemsize:
            # Check we won't clip the dataset if shrinking the itemsize
            if bytes_allocated < arr.dtype.itemsize:
                value_max, value_min = 2**bits_allocated - 1, 0
                if bool(pixel_repr):
                    value_max = 2**(bits_allocated - 1) - 1
                    value_min = -2**(bits_allocated - 1)

                if arr.min() < value_min or arr.max() > value_max:
                    raise ValueError(
                        "Cannot modify the array to match 'Bits Allocated' "
                        "without clipping the pixel values"
                    )

            byteorder = '|' if bits_allocated == 8 else '<'
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

    def _process(
        self,
        arr: "np.ndarray",
        idx: Optional[int] = None,
        plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return an encoded frame from `arr` as :class:`bytes`.

        Parameters
        ----------
        arr : numpy.ndarray
            An :class:`~numpy.ndarray` containing single or multi-framed
            image data to be encoded.
        idx : int, optional
            When `arr` contains multiple frames, this is the index of the
            frame to be encoded.
        plugin : str, optional
            The name of the encoding plugin to use. If not specified then all
            available plugins will be tried.
        **kwargs
            Required parameters:

            May also contain optional parameters for the encoding function.

        Returns
        ------
        bytes
            The encoded pixel data frame.

        Raises
        ------
        ValueError
            If `arr` contains multiple frames but the `idx` of the frame
            to be encoded is not specified.
        """
        # Add our defaults, but don't overwrite existing options
        kwargs = {**self._defaults, **kwargs}

        # Process the pixel array and convert to little-endian ordered bytes
        src = self._preprocess(arr, **kwargs)

        failed_encoders = []
        if plugin:
            # Try specific encoder
            try:
                return self._available[plugin](src, **kwargs)
            except Exception as exc:
                failed_encoders.append(plugin)
        else:
            # Try all available encoders
            for name, func in self._available.items():
                try:
                    return func(src, **kwargs)
                except Exception as exc:
                    failed_encoders.append((name, exc))

        # TODO: better exception message -> add exception to msg
        raise RuntimeError(
            f"Unable to encode the pixel data using the following packages: "
            f"{','.join(failed_encoders)}"
        )

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
"""A *Pixel Data* encoder for *RLE Lossless**

.. versionadded:: 2.2
"""
RLELosslessEncoder.register_plugin(
    'pylibjpeg',
    ('pydicom.encoders.pylibjpeg', 'encode_pixel_data'),
    'numpy and pylibjpeg (with the pylibjpeg-rle plugin)'
)
RLELosslessEncoder.register_plugin(
    'pydicom',
    ('pydicom.pixel_data_handlers.rle_handler', '_wrap_rle_encode_frame'),
)


# Available pixel data encoders
_PIXEL_DATA_ENCODERS = {
    RLELossless: RLELosslessEncoder,
}


def get_encoder(uid, encoder_type='PixelData'):
    """Return an encoder for `uid`.

    .. versionadded:: 2.2
    """
    try:
        return _PIXEL_DATA_ENCODERS[uid]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data encoders have been implemented for '{uid.name}'"
        )
