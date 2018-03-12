"""Use the pillow python package to decode pixel transfer syntaxes."""
import sys
import io
import pydicom.encaps
import pydicom.uid
import logging
have_numpy = True
logger = logging.getLogger('pydicom')
try:
    import numpy
except ImportError:
    have_numpy = False
    raise

have_pillow = True
try:
    from PIL import Image as PILImg
except ImportError:
    # If that failed, try the alternate import syntax for PIL.
    try:
        import Image as PILImg
    except ImportError:
        # Neither worked, so it's likely not installed.
        have_pillow = False
        raise

PillowSupportedTransferSyntaxes = [
    pydicom.uid.JPEGBaseLineLossy8bit,
    pydicom.uid.JPEGLossless,
    pydicom.uid.JPEGBaseLineLossy12bit,
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEG2000TransferSyntaxes = [
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEGTransferSyntaxes = [
    pydicom.uid.JPEGBaseLineLossy8bit,
    pydicom.uid.JPEGBaseLineLossy12bit,
]

sys_is_little_endian = (sys.byteorder == 'little')
have_pillow_jpeg_plugin = False
have_pillow_jpeg2000_plugin = False
try:
    from PIL import _imaging as pillow_core
    have_pillow_jpeg_plugin = hasattr(pillow_core, "jpeg_decoder")
    have_pillow_jpeg2000_plugin = hasattr(pillow_core, "jpeg2k_decoder")
except Exception:
    pass


def supports_transfer_syntax(dicom_dataset):
    """
    Returns
    -------
    bool
        True if this pixel data handler might support this transfer syntax.

        False to prevent any attempt to try to use this handler
        to decode the given transfer syntax
    """
    if (have_pillow_jpeg_plugin and
            (dicom_dataset.file_meta.TransferSyntaxUID in
             PillowJPEGTransferSyntaxes)):
        return True
    if (have_pillow_jpeg2000_plugin and
            (dicom_dataset.file_meta.TransferSyntaxUID in
             PillowJPEG2000TransferSyntaxes)):
        return True
    return False


def needs_to_convert_to_RGB(dicom_dataset):
    return False


def should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
    should_change = dicom_dataset.SamplesPerPixel == 3
    return False


def get_pixeldata(dicom_dataset):
    """Use Pillow to decompress compressed Pixel Data.

    Returns
    -------
    numpy.ndarray
       The contents of the Pixel Data element (7FE0,0010) as an ndarray.

    Raises
    ------
    ImportError
        If PIL is not available.

    NotImplementedError
        if the transfer syntax is not supported

    TypeError
        if the pixel data type is unsupported
    """
    logger.debug("Trying to use Pillow to read pixel array "
                 "(has pillow = %s)", have_pillow)
    if not have_pillow:
        msg = ("The pillow package is required to use pixel_array for "
               "this transfer syntax {0}, and pillow could not be "
               "imported.".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise ImportError(msg)
    if (not have_pillow_jpeg_plugin and
            dicom_dataset.file_meta.TransferSyntaxUID in
            PillowJPEGTransferSyntaxes):
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow lacks the jpeg decoder plugin".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise NotImplementedError(msg)
    if (not have_pillow_jpeg2000_plugin and
            dicom_dataset.file_meta.TransferSyntaxUID in
            PillowJPEG2000TransferSyntaxes):
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow lacks the jpeg 2000 decoder plugin".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise NotImplementedError(msg)
    if (dicom_dataset.file_meta.TransferSyntaxUID not in
            PillowSupportedTransferSyntaxes):
        msg = ("this transfer syntax {0}, can not be read because "
               "Pillow does not support this syntax".format(
                   dicom_dataset.file_meta.TransferSyntaxUID.name))
        raise NotImplementedError(msg)

    # Make NumPy format code, e.g. "uint16", "int32" etc
    # from two pieces of info:
    # dicom_dataset.PixelRepresentation -- 0 for unsigned, 1 for signed;
    # dicom_dataset.BitsAllocated -- 8, 16, or 32
    if dicom_dataset.PixelRepresentation == 0:
        format_str = 'uint{}'.format(dicom_dataset.BitsAllocated)
    elif dicom_dataset.PixelRepresentation == 1:
        format_str = 'int{}'.format(dicom_dataset.BitsAllocated)
    else:
        format_str = 'bad_pixel_representation'
    try:
        numpy_format = numpy.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: "
               "format='{}', PixelRepresentation={}, "
               "BitsAllocated={}".format(
                   format_str,
                   dicom_dataset.PixelRepresentation,
                   dicom_dataset.BitsAllocated))
        raise TypeError(msg)

    if dicom_dataset.is_little_endian != sys_is_little_endian:
        numpy_format = numpy_format.newbyteorder('S')

    # decompress here
    if (dicom_dataset.file_meta.TransferSyntaxUID in
            PillowJPEGTransferSyntaxes):
        logger.debug("This is a JPEG lossy format")
        if dicom_dataset.BitsAllocated > 8:
            raise NotImplementedError("JPEG Lossy only supported if "
                                      "Bits Allocated = 8")
        generic_jpeg_file_header = (
            b'\xff\xd8\xff\xe0\x00\x10'
            b'JFIF\x00\x01\x01\x01\x00\x01\x00\x01\x00\x00')
        frame_start_from = 2
    elif (dicom_dataset.file_meta.TransferSyntaxUID in
          PillowJPEG2000TransferSyntaxes):
        logger.debug("This is a JPEG 2000 format")
        generic_jpeg_file_header = b''
        # generic_jpeg_file_header = b'\x00\x00\x00\x0C\x6A'
        #     b'\x50\x20\x20\x0D\x0A\x87\x0A'
        frame_start_from = 0
    else:
        logger.debug("This is a another pillow supported format")
        generic_jpeg_file_header = b''
        frame_start_from = 0
    try:
        UncompressedPixelData = b''
        if ('NumberOfFrames' in dicom_dataset and
                dicom_dataset.NumberOfFrames > 1):
            # multiple compressed frames
            CompressedPixelDataSeq = \
                pydicom.encaps.decode_data_sequence(
                    dicom_dataset.PixelData)
            for frame in CompressedPixelDataSeq:
                data = generic_jpeg_file_header + \
                    frame[frame_start_from:]
                fio = io.BytesIO(data)
                try:
                    decompressed_image = PILImg.open(fio)
                except IOError as e:
                    raise NotImplementedError(e.strerror)
                UncompressedPixelData += decompressed_image.tobytes()
        else:
            # single compressed frame
            UncompressedPixelData = pydicom.encaps.defragment_data(
                dicom_dataset.PixelData)
            UncompressedPixelData = generic_jpeg_file_header + \
                UncompressedPixelData[frame_start_from:]
            try:
                fio = io.BytesIO(UncompressedPixelData)
                decompressed_image = PILImg.open(fio)
            except IOError as e:
                raise NotImplementedError(e.strerror)
            UncompressedPixelData = decompressed_image.tobytes()
    except Exception:
        raise
    logger.debug(
        "Successfully read %s pixel bytes",
        len(UncompressedPixelData))
    pixel_array = numpy.copy(
        numpy.frombuffer(UncompressedPixelData, numpy_format))
    if (dicom_dataset.file_meta.TransferSyntaxUID in
            PillowJPEG2000TransferSyntaxes and
            dicom_dataset.BitsStored == 16):
        # WHY IS THIS EVEN NECESSARY??
        pixel_array &= 0x7FFF
    if should_change_PhotometricInterpretation_to_RGB(dicom_dataset):
        dicom_dataset.PhotometricInterpretation = "RGB"
    return pixel_array
