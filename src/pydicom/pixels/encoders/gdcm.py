# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from typing import cast

from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.uid import RLELossless

try:
    import gdcm

    GDCM_VERSION = tuple(int(x) for x in gdcm.Version.GetVersion().split("."))
    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False


ENCODER_DEPENDENCIES = {
    RLELossless: ("gdcm>=3.0.10",),
}


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_GDCM or GDCM_VERSION < (3, 0, 10):
        return False

    return uid in ENCODER_DEPENDENCIES


def encode_pixel_data(src: bytes, runner: EncodeRunner) -> bytes:
    """Return the encoded image data in `src`.

    Parameters
    ----------
    src : bytes
        The raw image frame data to be encoded.
    runner : pydicom.pixels.encoders.base.EncodeRunner
        The runner managing the encoding process.

    Returns
    -------
    bytes
        The encoded image data.
    """
    byteorder = runner.get_option("byteorder", "<")
    if byteorder == ">":
        raise ValueError("Unsupported option \"byteorder = '>'\"")

    return _ENCODERS[runner.transfer_syntax](src, runner)


def _rle_encode(src: bytes, runner: EncodeRunner) -> bytes:
    """Return RLE encoded image data from `src`.

    Parameters
    ----------
    src : bytes
        The raw image frame data to be encoded.
    runner : pydicom.pixels.encoders.base.EncodeRunner
        The runner managing the encoding process.

    Returns
    -------
    bytes
        The encoded image data.
    """
    if runner.bits_allocated > 32:
        raise ValueError("Unable to encode more than 32-bit data")

    # Create a gdcm.Image with the uncompressed `src` data
    pi = gdcm.PhotometricInterpretation.GetPIType(runner.photometric_interpretation)

    # GDCM's null photometric interpretation gets used for invalid values
    if pi == gdcm.PhotometricInterpretation.PI_END:
        raise ValueError(
            f"Invalid photometric interpretation '{runner.photometric_interpretation}'"
        )

    # `src` uses little-endian byte ordering
    ts = gdcm.TransferSyntax.ImplicitVRLittleEndian

    # Must use ImageWriter().GetImage() to create a gdcmImage
    #   also have to make sure `writer` doesn't go out of scope
    writer = gdcm.ImageWriter()
    image = writer.GetImage()
    image.SetNumberOfDimensions(2)
    image.SetDimensions((runner.columns, runner.rows, 1))
    image.SetPhotometricInterpretation(gdcm.PhotometricInterpretation(pi))
    image.SetTransferSyntax(gdcm.TransferSyntax(ts))

    pixel_format = gdcm.PixelFormat(
        runner.samples_per_pixel,
        runner.bits_allocated,
        runner.bits_stored,
        runner.bits_stored - 1,
        runner.pixel_representation,
    )
    image.SetPixelFormat(pixel_format)
    if runner.samples_per_pixel > 1:
        # Default `src` is planar configuration 0 (i.e. R1 G1 B1 R2 G2 B2)
        image.SetPlanarConfiguration(0)

    # Add the Pixel Data element and set the value to `src`
    elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
    elem.SetByteStringValue(src)
    image.SetDataElement(elem)

    # Converts an image to match the set transfer syntax
    converter = gdcm.ImageChangeTransferSyntax()

    # Set up the converter with the intended transfer syntax...
    rle = gdcm.TransferSyntax.GetTSType(runner.transfer_syntax)
    converter.SetTransferSyntax(gdcm.TransferSyntax(rle))
    # ...and image to be converted
    converter.SetInput(image)

    # Perform the conversion, returns bool
    # 'PALETTE COLOR' and a lossy transfer syntax will return False
    result = converter.Change()
    if not result:
        raise RuntimeError(
            "ImageChangeTransferSyntax.Change() returned a failure result"
        )

    # A new gdcmImage with the converted pixel data element
    image = converter.GetOutput()

    # The element's value is the encapsulated encoded pixel data
    seq = image.GetDataElement().GetSequenceOfFragments()

    # RLECodec::Code() uses only 1 fragment per frame
    if seq is None or seq.GetNumberOfFragments() != 1:
        # Covers both no sequence and unexpected number of fragments
        raise RuntimeError("Unexpected number of fragments found in the 'Pixel Data'")

    fragment = seq.GetFragment(0).GetByteValue().GetBuffer()
    return cast(bytes, fragment.encode("utf-8", "surrogateescape"))


_ENCODERS = {RLELossless: _rle_encode}
