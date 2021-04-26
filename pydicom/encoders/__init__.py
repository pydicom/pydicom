
import sys


# The native system endianness
_ENDIANNESS = '<' if sys.byteorder == 'little' else '>'

# Available pixel data encoders, not sure what this means or does (if anything)
_ENCODERS = [
    'JPEGBaselineEncoder'
    'RLEEncoder',
    'PyLibJPEGEncoder',
    'GDCMEncoder'
]
""""""

def get_encoder(uid):
    """Return an encoder for `uid`."""
    pass


# Kinda pointless...
for encoder in _ENCODERS:
    try:
        __import__(f"pydicom.encoders.{encoder}", globals(), locals(), [])
    except ImportError as exc:
        pass


"""
Usage

from pydicom.encoders import (
    RLELosslessEncoder
    JPEGBaseline8BitEncoder
    JPEGExtended12BitEncoder
    JPEGLosslessP14Encoder
    JPEGLosslessSV1Encoder
    JPEGLSLosslessEncoder
    JPEGLSNearLosslessEncoder
    JPEG2000LosslessEncoder
    JPEG2000Encoder
)
* Lots of imports
* Names are a bit long
* V. clear what each does

vs.

from pydicom.encoders import (
    PyLibJPEGEncoder,
    GDCMEncoder,
    PillowEncoder
)
* Fewer imports & shorter names, but what does each do?

Cons: having to write one for each transfer syntax...
Pros: easier for users to understand. Want RLE, grab RLE encoder!

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


for p in path.glob('**'):
    ds = dcmread(p)
    ds.PixelData = encoder.encode_and_encapsulate(ds)
    ds.save_as('...')


from pydicom.encoders import

# Or...
for p in path.glob('**'):
    ds = dcmread(p)
    ds.compress(arr, uid)
    ds.save_as('...')

Dataset.compress(arr, uid) internals
    # nice and simple 1-to-1 relationship
    encoder = pydicom.encoders.get_encoder(uid)
    if not encoder.available:
        raise SomeException(
            f"The {encoder.name} encoder requires one of the following "
            f"packages: {encoder.dependencies}"
        )

    ds.PixelData = encoder.encoder(arr)
    ds.file_meta.TransferSyntaxUID = uid


Encoder internals


"""

RLELosslessEncoder = EncoderFactory(RLELossless)
RLELosslessEncoder.add_decoder(
    'pylibjpeg',
    pylibjpeg.decode
)
RLELosslessEncoder.add_decoder(
    'pydicom',
    pydicom.pixel_data_handlers.rle_handler.encode_rle_frame
)


class EncoderFactory:
    """Base class for bulk data encoders."""
    def __init__(self, uid):
        self.handler = handler
        self.options = options or {}

    @property
    def available(self):
        # Generic
        return False

    @classmethod
    def encodeable(cls, ds, data_type):
        """Return ``True`` if the encoder can encode `arr`.

        Parameters
        ----------
        arr : numpy.ndarray
            The array containing the bulk data to be encoded.
        ds : pydicom.dataset.Dataset
            The corresponding dataset.
        arr_type : str, optional
            The type of bulk data contained in `arr`, default 'PixelData'.

        Returns
        -------
        bool
            ``True`` if the encoder can be used, ``False`` otherwise.
        """
        return False

    def encode(self, arr, uid, **kwargs):
        return NotImplementedError(
            "The 'encode' method has not been implemented by the "
            f"{self.__class__.__name__} encoder"
        )

    def _encode_frame(self, arr, uid, **kwargs):
        yield encoded

    def encode_and_encapsulate(self, arr, uid, **kwargs):
        # kwargs vs self.options
        from pydicom.encaps import encapsulate
        if nr_frames > 1:
            return encapsulate([encode(f, uid, **kwargs) for f in arr])

        return encapsulate([encode(arr, uid, **kwargs)])

    def encode_and_encapsulate_ext(self, arr, uid, **kwargs):
        from pydicom.encaps import encapsulate_extended
        if nr_frames > 1:
            return encapsulate_extended(
                [encode(frame, uid, **kwargs) for frame in arr]
            )

        return encapsulate_extended([encode(arr, uid, **kwargs)])
