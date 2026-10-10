"""One-bit native pixel data must retain its bit order during compression."""

from io import BytesIO
import zlib

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import generate_frames
from pydicom.uid import (
    DeflatedImageFrameCompression,
    ExplicitVRBigEndian,
    ExplicitVRLittleEndian,
    MultiFrameSingleBitSecondaryCaptureImageStorage,
)


@pytest.mark.parametrize("vr", ["OB", "OW"])
@pytest.mark.parametrize("syntax", [ExplicitVRLittleEndian, ExplicitVRBigEndian])
@pytest.mark.parametrize(
    "columns,canonical,big_endian_words,expected_frames",
    [
        (16, b"\x01\x00", b"\x00\x01", [b"\x01\x00"]),
        (8, b"\x13\x87", b"\x87\x13", [b"\x13", b"\x87"]),
        (9, b"\x01\x04\x02\x00", b"\x04\x01\x00\x02", [b"\x01\x00", b"\x02\x01"]),
        (7, b"\x11\x21\x09\x00", b"\x21\x11\x00\x09", [b"\x11", b"\x42", b"\x24"]),
        (3, b"\x9d\x01", b"\x01\x9d", [b"\x05", b"\x03", b"\x06"]),
    ],
)
def test_one_bit_pixel_data_word_order(
    vr, syntax, columns, canonical, big_endian_words, expected_frames
):
    """Check real encoding and file round trips against authored packed bits."""
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = syntax
    ds.SOPClassUID = MultiFrameSingleBitSecondaryCaptureImageStorage
    ds.SOPInstanceUID = "1.2.3.4"
    ds.Rows = 1
    ds.Columns = columns
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.NumberOfFrames = len(expected_frames)
    ds.BitsAllocated = ds.BitsStored = 1
    ds.HighBit = ds.PixelRepresentation = 0
    stored = (
        big_endian_words if syntax == ExplicitVRBigEndian and vr == "OW" else canonical
    )
    ds.add_new(0x7FE00010, vr, stored)

    ds.compress(
        DeflatedImageFrameCompression,
        encoding_plugin="pydicom",
        generate_instance_uid=False,
    )
    stream = BytesIO()
    ds.save_as(stream, enforce_file_format=True)
    stream.seek(0)
    restored = dcmread(stream)
    assert restored.file_meta.TransferSyntaxUID == DeflatedImageFrameCompression
    assert restored.BitsAllocated == 1
    encoded_frames = generate_frames(
        restored.PixelData, number_of_frames=len(expected_frames)
    )
    # zlib is an independent decoder: do not let a matching pixel-decoder bug
    # hide the encoder's byte/bit ordering error.
    actual = [zlib.decompress(frame, wbits=-15) for frame in encoded_frames]
    assert actual == expected_frames
