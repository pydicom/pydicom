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
import multiprocessing
from pathlib import Path
import sys
from typing import (
    Callable, Generator, Tuple, List, Optional, Dict, Any, Union, cast
)

from pydicom.dataset import Dataset
from pydicom.encaps import encapsulate
from pydicom.pixel_data_handlers.util import get_expected_length
from pydicom.uid import UID, RLELossless

try:
    import numpy as np
except ImportError:
    pass


# TODO:
# Add docs for requirements of a plugin
class Encoder:
    """Class for data encoders.

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
        # Available encoding plugins
        self._available: Dict[str, Callable] = {}
        # Unavailable encoding plugins - missing dependencies or other reason
        self._unavailable: Dict[str, Tuple[str, Optional[str]]] = {}
        # Default encoding options
        self._defaults = {
            'transfer_syntax_uid': self.UID,
            'byteorder': '<',
        }

    # TODO: Add link to doc on plugin requirements
    def add_plugin(
        self, label: str, path: Tuple[str, str], err_msg: Optional[str] = None
    ) -> None:
        """Add an encoding plugin to the encoder.

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

        # `is_available(UID)` is required for plugins
        if module.is_available(self.UID):  # type: ignore[attr-defined]
            self._available[label] = getattr(module, path[1])
        else:
            # `ENCODER_DEPENDENCIES[UID]` is required for plugins
            self._unavailable[label] = module.ENCODER_DEPENDENCIES[self.UID]

    @staticmethod
    def _check_kwargs(kwargs: Dict[str, Union[int, str]]) -> None:
        """Raise TypeError if `kwargs` is missing required keys."""
        required_keys = [
            'rows', 'columns', 'samples_per_pixel', 'bits_allocated',
            'bits_stored', 'pixel_representation', 'photometric_interpretation'
        ]
        missing = [f"'{key}'" for key in required_keys if key not in kwargs]
        if missing:
            raise TypeError(
                f"Missing expected arguments: {', '.join(missing)}"
            )

    # TODO: test
    def encode(
        self,
        src: Union[bytes, "np.ndarray", "Dataset"],
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        decoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return pixel data from `src` as encoded :class:`bytes`.

        Parameters
        ----------
        src : bytes, numpy.ndarray or pydicom.dataset.Dataset
            Single or multi-frame pixel data as one of the following:

            * :class`bytes`: the uncompressed little-endian ordered pixel data
            * :class:`~numpy.ndarray`: the uncompressed pixel data, should be
              shaped as:

              * (Rows, Columns) for single frame, single sample data.
              * (Rows, Columns, Samples) for single frame, multi-sample data.
              * (Frames, Rows, Columns) for multi-frame, single sample data.
              * (Frames, Rows, Columns, Samples) for multi-frame and
                multi-sample data.
              * or the corresponding 1D array you'd get from ``arr.ravel()``.

            * :class:`~pydicom.dataset.Dataset`: the the dataset containing
              the compressed or uncompressed *Pixel Data* to be encoded. If the
              *Pixel Data* is compressed then a suitable pixel data handler
              must be available to decompress it.
        idx : int, optional
            Required when `src` contains multiple frames, this is the index
            of the frame to be encoded.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        decoding_plugin : str, optional
            The name of the pixel data decoding handler to use if `src`
            is a :class:`~pydicom.dataset.Dataset` containing compressed
            *Pixel Data*. If `decoding_plugin` is not specified then all
            available handlers will be tried.
        **kwargs
            The following keyword parameters are required when `src` is
            :class:`bytes` or :class:`~numpy.ndarray`:

            * ``'rows': int`` - the number of rows in `src`, maximum 65535.
            * ``'columns': int`` - the number of columns in `src`, maximum
              65535.
            * ``'number_of_frames: int'`` - the number of frames in `src`,
              required if the number of frames is greater than 1.
            * ``'samples_per_pixel': int`` - the number of samples per pixel in
              `src`, should be 1 or 3.
            * ``'bits_allocated': int`` - the number of bits used to contain
              the pixel data, should be 8, 16, 32 or 64.
            * ``'bits_stored': int`` - the number of bits actually used per
              pixel in `src`. For example, an ndarray `src` might have a
              :class:`~numpy.dtype` of 'uint16' (range 0 to 65535) but only
              contain 12-bit pixel values (range 0 to 4095).
            * ``'pixel_representation': int`` - the type of data being encoded,
              0 for unsigned, 1 for 2's complement
            * ``'photometric_interpretation': str`` - the colorspace of the
              pixel data, such as ``'RGB'``.

            FIXME
            Additional keyword parameters for the encoding plugin may also be
            present. See the documentation for the encoding plugins for what
            options are available.

        Returns
        -------
        bytes
            The encoded pixel data.
        """
        if isinstance(src, Dataset):
            return self._encode_dataset(
                src, idx, encoding_plugin, decoding_plugin, **kwargs
            )

        if isinstance(src, np.ndarray):
            return self._encode_array(src, idx, encoding_plugin, **kwargs)

        if isinstance(src, bytes):
            return self._encode_bytes(src, idx, encoding_plugin, **kwargs)

        raise TypeError(
            "'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
            f"not '{src.__class__.__name__}'"
        )

    # TODO: add validity check for kwargs
    # TODO: test
    def _encode_array(
        self,
        arr: "np.ndarray",
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return a single encoded frame from `arr`."""
        if len(arr.shape) > 4:
            raise ValueError(f"Unable to encode {len(arr.shape)}D ndarrays")

        if kwargs.get('number_of_frames', 1) > 1 or len(arr.shape) == 4:
            if idx is None:
                raise ValueError(
                    "The frame 'idx' is required for multi-frame pixel data"
                )

            arr = arr[idx]

        src = self._preprocess(arr, **kwargs)
        return self._process(src, encoding_plugin, **kwargs)

    # TODO: test
    # TODO: add validity check for kwargs
    def _encode_bytes(
        self,
        src: bytes,
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return a single encoded frame from `src`."""
        rows: int = kwargs['rows']
        columns: int = kwargs['columns']
        samples_per_pixel: int = kwargs['samples_per_pixel']
        bits_allocated: int = kwargs['bits_allocated']
        bytes_allocated = bits_allocated // 8

        # Expected length of a single frame
        expected_len = rows * columns * samples_per_pixel * bytes_allocated
        whole_frames = expected_len // len(src)

        # Insufficient data
        if whole_frames == 0:
            raise ValueError("Insufficient data too short")

        # Single frame with matching length or with padding
        if whole_frames == 1:
            return self._process(src[:expected_len], encoding_plugin, **kwargs)

        # Multiple frames
        if idx is not None:
            frame_offset = idx * expected_len
            return self._process(
                src[frame_offset:frame_offset + expected_len],
                encoding_plugin,
                **kwargs
            )

        raise ValueError("The 'idx' parameter is required with multiple frames")

    # TODO: exception message
    # TODO: test
    def _encode_dataset(
        self,
        ds: "Dataset",
        idx: Optional[int] = None,
        encoding_plugin: str = '',
        decoding_plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return a single encoded frame from the *Pixel Data* in `ds`."""
        try:
            kwargs.update(self.kwargs_from_ds(ds))
        except AttributeError as exc:
            raise AttributeError("FIXME") from exc

        tsyntax = cast(UID, ds.file_meta.TransferSyntaxUID)
        if not tsyntax.is_compressed:
            return self._encode_bytes(
                ds.PixelData, idx, encoding_plugin, **kwargs
            )

        # Pixel Data is compressed
        if decoding_plugin:
            ds.convert_pixel_data(handler_name=decoding_plugin)

        arr = ds.pixel_array

        if kwargs['number_of_frames'] > 1 or len(arr.shape) == 4:
            if idx is None:
                raise ValueError(
                    "The frame 'idx' is required for multi-frame pixel data"
                )

            arr = arr[idx]

        src = self._preprocess(arr, **kwargs)
        return self._process(src, encoding_plugin, **kwargs)

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the encoder has available plugins and can be
        used to encode data, ``False`` otherwise.
        """
        return bool(self._available)

    # TODO: test
    def iter_encode(
        self,
        src: Union[bytes, "np.ndarray", "Dataset"],
        encoding_plugin: str = '',
        decoding_plugin: str = '',
        **kwargs
    ) -> Generator[bytes, None, None]:
        """Yield encoded frames of the pixel data in  `src` as :class:`bytes`.

        Parameters
        ----------
        src : bytes, numpy.ndarray or pydicom.dataset.Dataset
            Single or multi-frame pixel data as one of the following:

            * :class`bytes`: the uncompressed little-endian ordered pixel data
            * :class:`~numpy.ndarray`: the uncompressed pixel data, should be
              shaped as:

              * (Rows, Columns) for single frame, single sample data.
              * (Rows, Columns, Samples) for single frame, multi-sample data.
              * (Frames, Rows, Columns) for multi-frame, single sample data.
              * (Frames, Rows, Columns, Samples) for multi-frame and
                multi-sample data.
              * or the corresponding 1D array you'd get from ``arr.ravel()``.

            * :class:`~pydicom.dataset.Dataset`: the the dataset containing
              the compressed or uncompressed *Pixel Data* to be encoded. If the
              *Pixel Data* is compressed then a suitable pixel data handler
              must be available to decompress it.
        idx : int, optional
            Required when `src` contains multiple frames, this is the index
            of the frame to be encoded.
        encoding_plugin : str, optional
            The name of the pixel data encoding plugin to use. If
            `encoding_plugin` is not specified then all available plugins will
            be tried.
        decoding_plugin : str, optional
            The name of the pixel data decoding handler to use if `src`
            is a :class:`~pydicom.dataset.Dataset` containing compressed
            *Pixel Data*. If `decoding_plugin` is not specified then all
            available handlers will be tried.
        **kwargs
            The following keyword parameters are required when `src` is
            :class:`bytes` or :class:`~numpy.ndarray`:

            * ``'rows': int`` - the number of rows in `src`, maximum 65535.
            * ``'columns': int`` - the number of columns in `src`, maximum
              65535.
            * ``'number_of_frames: int'`` - the number of frames in `src`,
              required if the number of frames is greater than 1.
            * ``'samples_per_pixel': int`` - the number of samples per pixel in
              `src`, should be 1 or 3.
            * ``'bits_allocated': int`` - the number of bits used to contain
              the pixel data, should be 8, 16, 32 or 64.
            * ``'bits_stored': int`` - the number of bits actually used per
              pixel in `src`. For example, an ndarray `src` might have a
              :class:`~numpy.dtype` of 'uint16' (range 0 to 65535) but only
              contain 12-bit pixel values (range 0 to 4095).
            * ``'pixel_representation': int`` - the type of data being encoded,
              0 for unsigned, 1 for 2's complement
            * ``'photometric_interpretation': str`` - the colorspace of the
              pixel data, such as ``'RGB'``.

            FIXME
            Additional keyword parameters for the encoding plugin may also be
            present. See the documentation for the encoding plugins for what
            options are available.

        Yields
        ------
        bytes
            An encoded frame of pixel data.
        """
        if isinstance(src, Dataset):
            nr_frames = cast(Optional[str], src.get('NumberOfFrames', 1))
            for idx in range(int(nr_frames or 1)):
                yield self._encode_dataset(
                    src, idx, encoding_plugin, decoding_plugin, **kwargs
                )
        elif isinstance(src, np.ndarray):
            for idx in range(kwargs.get('number_of_frames', 1)):
                yield self._encode_array(src, idx, encoding_plugin, **kwargs)
        elif isinstance(src, bytes):
            for idx in range(kwargs.get('number_of_frames', 1)):
                yield self._encode_bytes(src, idx, encoding_plugin, **kwargs)
        else:
            raise TypeError(
                "'src' must be bytes, numpy.ndarray or "
                f"pydicom.dataset.Dataset, not '{src.__class__.__name__}'"
            )

    # TODO: better name
    @staticmethod
    def kwargs_from_ds(ds: "Dataset") -> Dict[str, Union[int, str]]:
        """Return a *kwargs* dict from `ds`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to use as a source of keyword parameters.

        Returns
        -------
        Dict[str, Union[int, str]]
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
        required = [
            "Rows", "Columns", "SamplesPerPixel", "BitsAllocated",
            "BitsStored", "PixelRepresentation", "PhotometricInterpretation"
        ]
        missing = [f"'{kw}'" for kw in required if kw not in ds]
        if missing:
            raise AttributeError(
                "The following required elements are missing from the "
                f"dataset: {', '.join(missing)}"
            )
        empty = [f"'{kw}'" for kw in required if ds[kw].VM == 0]
        if empty:
            raise AttributeError(
                "The following required dataset elements have a VM of 0: "
                f"{', '.join(empty)}"
            )

        rows = cast(int, ds.Rows)  # US
        columns = cast(int, ds.Columns)  # US
        samples_per_pixel = cast(int, ds.SamplesPerPixel)  # US
        bits_allocated = cast(int, ds.BitsAllocated)  # US
        bits_stored = cast(int, ds.BitsStored)  # US
        pixel_representation = cast(int, ds.PixelRepresentation)  # US
        photometric_interpretation = cast(str, ds.PhotometricInterpretation)  # CS

        # IS, may be missing, None or "1", "2", ...
        nr_frames = cast(Optional[str], ds.get('NumberOfFrames', 1))

        return {
            'rows': rows,
            'columns': columns,
            'samples_per_pixel': samples_per_pixel,
            'number_of_frames': int(nr_frames or 1),
            'bits_allocated': bits_allocated,
            'bits_stored': bits_stored,
            'pixel_representation': pixel_representation,
            'photometric_interpretation': photometric_interpretation,
        }

    @property
    def name(self) -> str:
        """Return the name of the encoder."""
        return f"{self.UID.keyword}Encoder"

    @property
    def missing_dependencies(self) -> List[str]:
        """Return nice strings for plugins when missing dependencies"""
        s = []
        for label, deps in self._unavailable.items():
            if len(deps) > 1:
                s.append(
                    f"{label} - requires {', '.join(deps[:-1])} and {deps[-1]}"
                )
            else:
                s.append(f"{label} - requires {deps[0]}")

        return s

    def _preprocess(self, arr: "np.ndarray", **kwargs) -> bytes:
        """Preprocess `arr` before encoding to ensure it meets requirements.

        `arr` will be checked against the required keys in `kwargs` before
        being converted to little-endian ordered bytes.

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
            * `bits_stored`: int
            * `pixel_representation`: int

        Returns
        -------
        bytes
            The pixel data in `arr` converted to little-endian ordered bytes.
        """
        rows: int = kwargs['rows']
        cols: int = kwargs['columns']
        samples_per_pixel: int = kwargs['samples_per_pixel']
        bits_allocated: int = kwargs['bits_allocated']
        bytes_allocated = bits_allocated // 8
        bits_stored: int = kwargs['bits_stored']
        pixel_repr: int = kwargs['pixel_representation']

        shape = arr.shape
        dims = len(shape)
        dtype = arr.dtype

        # Ensure *Samples per Pixel* value is supported
        if samples_per_pixel not in (1, 3):
            raise ValueError(
                "Unable to encode as a samples per pixel value of "
                f"{samples_per_pixel} is not supported (must be 1 or 3)"
            )

        # Check shape/length of `arr` matches
        valid_shapes = {
            1: (rows * cols * samples_per_pixel, ),
            2: (rows, cols),
            3: (rows, cols, samples_per_pixel),
        }

        if valid_shapes[dims] != shape:
            raise ValueError(
                f"Unable to encode as the shape of the ndarray {shape} "
                "doesn't match the values for the rows, columns and samples "
                "per pixel"
            )

        if samples_per_pixel > 1 and dims == 2:
            raise ValueError(
                f"Unable to encode as the shape of the ndarray {shape} "
                "is not consistent with a samples per pixel value of 3"
            )

        ui = [
            np.issubdtype(dtype, np.unsignedinteger),
            np.issubdtype(dtype, np.signedinteger)
        ]
        if not any(ui):
            raise ValueError(
                f"Unable to encode as the ndarray's dtype '{dtype}' is "
                "not supported"
            )

        # Check *Pixel Representation* is consistent with `arr`
        if not ui[pixel_repr]:
            s = ['unsigned', 'signed'][pixel_repr]
            raise ValueError(
                f"Unable to encode as the ndarray's dtype '{dtype}' is "
                f"not consistent with pixel representation '{pixel_repr}' "
                f"({s} int)"
            )

        # Checks for *Bits Allocated*
        if bits_allocated not in (8, 16, 32, 64):
            raise ValueError(
                "Unable to encode as a bits allocated value of "
                f"{bits_allocated} is not supported (must be 8, 16, 32 or 64)"
            )

        if bytes_allocated != dtype.itemsize:
            raise ValueError(
                f"Unable to encode as the ndarray's dtype '{dtype}' is "
                "not consistent with a bits allocated value of "
                f"{bits_allocated}"
            )

        if bits_allocated < bits_stored:
            raise ValueError(
                "Unable to encode as the bits stored value is greater than "
                "the bits allocated value"
            )

        # Convert the array to the required byte order (little-endian)
        sys_endianness = '<' if sys.byteorder == 'little' else '>'
        # `byteorder` may be
        #   '|': none available, such as for 8 bit -> ignore
        #   '=': native system endianness -> change to '<' or '>'
        #   '<' or '>': little or big
        byteorder = dtype.byteorder
        byteorder = sys_endianness if byteorder == '=' else byteorder
        if byteorder == '>':
            arr = arr.astype(dtype.newbyteorder('<'))

        return arr.tobytes()

    # TODO: test
    def _process(
        self,
        src: bytes,
        plugin: str = '',
        **kwargs
    ) -> bytes:
        """Return an encoded frame from `arr` as :class:`bytes`.

        Parameters
        ----------
        arr : numpy.ndarray
            An :class:`~numpy.ndarray` containing single or multi-framed
            image data to be encoded.
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

        failed_encoders: List[Tuple[str, str]] = []
        if plugin:
            # Try specific encoder
            #try:
            return self._available[plugin](src, **kwargs)
            #except Exception as exc:
            #failed_encoders.append(plugin)
        else:
            # Try all available encoders
            for name, func in self._available.items():
                #try:
                return func(src, **kwargs)
                #except Exception as exc:
                #failed_encoders.append((name, exc))

        # TODO: better exception message -> add exception to msg
        raise RuntimeError(
            f"Unable to encode the pixel data using the following packages: "
            f"{','.join([i[0] for i in failed_encoders])}"
        )

    def remove_plugin(self, label: str) -> None:
        """Remove a plugin from the encoder.

        Parameters
        ----------
        label : str
            The label of the plugin to remove.
        """
        if label in self._available:
            del self._available[label]
        elif label in self._unavailable:
            del self._unavailable
        else:
            raise ValueError(f"Unable to remove '{label}', no such plugin'")

    @property
    def UID(self) -> UID:
        """Return the *Transfer Syntax UID* corresponding to the encoder"""
        return self._uid


# Encoder names should be f"{UID.keyword}Encoder"
RLELosslessEncoder = Encoder(RLELossless)
"""An *RLE Lossless** encoder for *Pixel Data*.

.. versionadded:: 2.2
"""
RLELosslessEncoder.add_plugin(
    'pylibjpeg',
    ('pydicom.encoders.pylibjpeg', 'encode_pixel_data'),
)
RLELosslessEncoder.add_plugin(
    'pydicom',
    ('pydicom.pixel_data_handlers.rle_handler', '_wrap_rle_encode_frame'),
)


# Available pixel data encoders
_PIXEL_DATA_ENCODERS = {
    RLELossless: RLELosslessEncoder,
}


def get_encoder(uid: str) -> Encoder:
    """Return an encoder for `uid`.

    .. versionadded:: 2.2
    """
    uid = cast(UID, UID(uid))
    try:
        return _PIXEL_DATA_ENCODERS[uid]
    except KeyError:
        raise NotImplementedError(
            f"No pixel data encoders have been implemented for '{uid.name}'"
        )


# TODO: use standalone encoding func so can modify in place
def parallel_encode(
    path: Union[str, Path],
    uid: str,
    recurse: bool = True,
    nprocs: int = multiprocessing.cpu_count(),
    **kwargs
) -> List["Dataset"]:
    """Use :mod:`multiprocessing` to compress the *Pixel Data* in multiple
    `datasets`.

    .. versionadded:: 2.2

    Calls the :meth:`~pydicom.dataset.Dataset.compress` method on each of the
    `datasets`.

    Parameters
    ----------
    datasets : list of pydicom.dataset.Dataset
        The datasets to use.
    uid : str
        The *Transfer Syntax UID* to use for compressing.
    **kwargs
        Optional parameters to pass to
        :meth:`~pydicomd.dataset.Dataset.compress`

    Returns
    -------
    List[Dataset]
        The datasets with compressed *Pixel Data*.
    """
    # Based on https://stackoverflow.com/a/16071616/12606901
    def func(q_in, q_out) -> None:
        while True:
            idx, ds = q_in.get()
            if idx is None:
                break

            ds.compress(uid, **kwargs)
            q_out.put((idx, ds))

    q_in  = multiprocessing.Queue(1)  # type: ignore[var-annotated]
    q_out = multiprocessing.Queue()  # type: ignore[var-annotated]

    proc = [
        multiprocessing.Process(target=func, args=(q_in, q_out))
        for _ in range(nprocs)
    ]
    for p in proc:
        p.daemon = True
        p.start()

    sent = [q_in.put((idx, ds)) for idx, ds in enumerate(datasets)]  # type: ignore[func-returns-value]
    [q_in.put((None, None)) for _ in range(nprocs)]  # type: ignore[func-returns-value]
    result = [q_out.get() for _ in range(len(sent))]

    [p.join() for p in proc]  # type: ignore[func-returns-value]

    return [ds for idx, ds in sorted(result)]
