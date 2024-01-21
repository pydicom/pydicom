# Copyright 2024 pydicom authors. See LICENSE file for details.

import importlib

from pydicom import uid
from pydicom.pixels.decoders.base import DecodeRunner
from pydicom.pixels.enums import PhotometricInterpretation as PI

try:
    import gdcm
except ImportError:
    pass


DECODER_DEPENDENCIES = {
    uid.JPEGBaseline8Bit: ("gdcm>=3.0",),
    uid.JPEGExtended12Bit: ("gdcm>=3.0",),
    uid.JPEGLossless: ("gdcm>=3.0",),
    uid.JPEGLosslessSV1: ("gdcm>=3.0",),
    uid.JPEGLSLossless: ("gdcm>=3.0",),
    uid.JPEGLSNearLossless: ("gdcm>=3.0",),
    uid.JPEG2000Lossless: ("gdcm>=3.0",),
    uid.JPEG2000: ("gdcm>=3.0",),
}


def _passes_version_check(minimum_version: tuple[int, ...]) -> bool:
    try:
        module = importlib.import_module("gdcm", "Version")
    except ModuleNotFoundError:
        return False

    version = module.Version.GetVersion()
    return tuple(int(x) for x in version.split(".")) >= minimum_version


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not _passes_version_check((3, 0)):
        return False

    return uid in DECODER_DEPENDENCIES


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytes:
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
    tsyntax = runner.transfer_syntax
    photometric_interpretation = runner.photometric_interpretation
    bits_stored = runner.bits_stored
    if tsyntax == uid.JPEGExtended12Bit:
        raise NotImplementedError(
            "GDCM does not support 'JPEG Extended' for samples with 12-bit precision"
        )

    fragment = gdcm.Fragment()
    fragment.SetByteStringValue(src)

    fragments = gdcm.SequenceOfFragments.New()
    fragments.AddFragment(fragment)

    elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
    elem.SetValue(fragments.__ref__())

    img = gdcm.Image()
    img.SetNumberOfDimensions(2)
    img.SetDimensions((runner.columns, runner.rows, 1))
    img.SetDataElement(elem)

    pi_type = gdcm.PhotometricInterpretation.GetPIType(photometric_interpretation)
    img.SetPhotometricInterpretation(gdcm.PhotometricInterpretation(pi_type))
    img.SetPlanarConfiguration(runner.planar_configuration)

    ts_type = gdcm.TransferSyntax.GetTSType(str.__str__(tsyntax))
    img.SetTransferSyntax(gdcm.TransferSyntax(ts_type))

    pixel_format = gdcm.PixelFormat(
        runner.samples_per_pixel,
        runner.bits_allocated,
        bits_stored,
        runner.bits_allocated - 1,
        runner.pixel_representation,
    )
    img.SetPixelFormat(pixel_format)

    # GDCM returns char* as str, so re-encode it to bytes
    frame = img.GetBuffer().encode("utf-8", "surrogateescape")

    # GDCM returns YBR_ICT and YBR_RCT as RGB
    if (
        tsyntax in (uid.JPEG2000Lossless, uid.JPEG2000)
        and photometric_interpretation in (PI.YBR_ICT, PI.YBR_RCT)
    ):
        runner.set_option("photometric_interpretation", PI.RGB)

    return frame
