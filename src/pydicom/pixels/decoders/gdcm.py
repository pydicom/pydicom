from typing import Any

from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)

try:
    import gdcm
    from gdcm import DataElement

    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False


# >= 3.0
DECODER_DEPENDENCIES = {
    JPEGBaseline8Bit: ("gdcm>=2.8.8",),
    JPEGExtended12Bit: ("gdcm>=2.8.8",),
    JPEGLossless: ("gdcm>=2.8.8",),
    JPEGLosslessSV1: ("gdcm>=2.8.8",),
    JPEGLSLossless: ("gdcm>=2.8.8",),
    JPEGLSNearLossless: ("gdcm>=2.8.8",),
    JPEG2000Lossless: ("gdcm>=2.8.8",),
    JPEG2000: ("gdcm>=2.8.8",),
    RLELossless: ("gdcm>=2.8.8",),
}


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_GDCM:
        return False

    # In memory decoding support added in v2.8.8
    if [int(x) for x in gdcm.Version.GetVersion().split(".")] < [2, 8, 8]:
        return False

    return uid in DECODER_DEPENDENCIES


def _create_data_element(src: bytes) -> "DataElement":
    """Return a ``gdcm.DataElement`` for the *Pixel Data*.

    Parameters
    ----------
    src : bytes
        An encoded Pixel Data frame.

    Returns
    -------
    gdcm.DataElement
        The converted *Pixel Data* element.
    """
    fragment = gdcm.Fragment()
    fragment.SetByteStringValue(src)

    fragments = gdcm.SequenceOfFragments.New()
    fragments.AddFragment(fragment)

    elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
    elem.SetValue(fragments.__ref__())

    return elem


def _create_image(elem: "DataElement", **kwargs: Any) -> "gdcm.Image":
    """Return a ``gdcm.Image``.

    Parameters
    ----------
    elem : gdcm.DataElement
        The ``gdcm.DataElement`` *Pixel Data* element.
    kwargs
        * rows
        * columns
        * transfer_syntax_uid
        * samples_per_pixel
        * bits_allocated
        * bits_stored
        * pixel_representation
        * photometric_interpretation

    Returns
    -------
    gdcm.Image
    """
    columns = kwargs["columns"]
    rows = kwargs["rows"]
    samples_per_pixel = kwargs["samples_per_pixel"]
    bits_allocated = kwargs["bits_allocated"]
    bits_stored = kwargs["bits_stored"]
    pixel_representation = kwargs["pixel_representation"]
    photometric_interpretation = kwargs["photometric_interpretation"]
    planar_configuration = kwargs["planar_configuration"]
    tsyntax = kwargs["transfer_syntax_uid"]

    img = gdcm.Image()
    img.SetNumberOfDimensions(2)
    img.SetDimensions((columns, rows, 1))
    img.SetDataElement(elem)

    pi_type = gdcm.PhotometricInterpretation.GetPIType(photometric_interpretation)
    img.SetPhotometricInterpretation(gdcm.PhotometricInterpretation(pi_type))
    img.SetPlanarConfiguration(planar_configuration)

    ts_type = gdcm.TransferSyntax.GetTSType(str.__str__(tsyntax))
    img.SetTransferSyntax(gdcm.TransferSyntax(ts_type))

    pixel_format = gdcm.PixelFormat(
        samples_per_pixel,
        bits_allocated,
        bits_stored,
        bits_allocated - 1,
        pixel_representation,
    )
    img.SetPixelFormat(pixel_format)

    return img


def _decode_frame(src: bytes, **kwargs: Any) -> bytes:
    elem = _create_data_element(src)
    img = _create_image(elem, **kwargs)

    # GDCM returns char* as str, so re-encode it to bytes
    return img.GetBuffer().encode("utf-8", "surrogateescape")
