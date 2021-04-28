"""Interface for *Pixel Data* encoding."""

try:
    from pylibjpeg.utils import get_pixel_data_encoders
    HAVE_PYLJ = True
except ImportError:
    HAVE_PYLJ = False


def encode_pixel_data(src: bytes, ds: "Dataset", **kwargs) -> bytes:
    """Return the encoded image data in `src`.

    Parameters
    ----------
    src : bytes
        The raw image frame data to be encoded, ordered upper-left to
        lower-right with little-endian byte order if the number of bits per
        pixel is greater than 8.
    ds : pydicom.dataset.Dataset
        The corresponding dataset.
    **kwargs
        Optional parameters to pass to the encoder function.

    Returns
    -------
    bytes
        The encoded image data.
    """
    encoder = get_pixel_data_encoders()[kwargs['TransferSyntaxUID']]

    return encoder(src, ds, **kwargs)


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_PYLJ:
        return False

    return uid in get_pixel_data_encoders()
