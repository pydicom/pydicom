from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.data import get_testdata_file
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    HTJ2KLossless,
    HTJ2KLosslessRPCL,
    HTJ2K,
    RLELossless,
)

if TYPE_CHECKING:
    from pydicom import Dataset


class PixelReference:
    def __init__(
        self,
        name: str,
        dtype: str,
        test: Callable[["PixelReference", "np.ndarray", dict[str, Any]], None],
    ) -> None:
        self.name = name
        self.dtype = dtype
        self._ds: Dataset
        self._test = test

    @property
    def ds(self) -> "Dataset":
        """Return the dataset containing the pixel data"""
        if getattr(self, "_ds", None) is None:
            self._ds = get_testdata_file(self.name, read=True)

        return self._ds

    @property
    def number_of_frames(self) -> int:
        """Return the expected number of frames of pixel data"""
        value = self.ds.get("NumberOfFrames", 1)
        value = int(value) if isinstance(value, str) else value
        if value in (None, 0):
            value = 1

        return value

    @property
    def meta(self) -> list[str | int]:
        """Return a list of pixel metadata."""
        attr = [
            self.ds.file_meta.TransferSyntaxUID,
            self.ds.BitsAllocated,
            self.ds.BitsStored,
            self.ds.Rows,
            self.ds.Columns,
            self.ds.SamplesPerPixel,
            self.number_of_frames,
            self.ds.PhotometricInterpretation,
            self.ds[self.pixel_keyword].VR,
        ]
        if self.pixel_keyword == "PixelData":
            attr.append(self.ds.PixelRepresentation)

        return attr

    @property
    def path(self) -> Path:
        return Path(get_testdata_file(self.name))

    @property
    def pixel_keyword(self) -> str:
        """Return the keyword used by the pixel data."""
        if "PixelData" in self.ds:
            return "PixelData"

        if "FloatPixelData" in self.ds:
            return "FloatPixelData"

        if "DoubleFloatPixelData" in self.ds:
            return "DoubleFloatPixelData"

        return ""

    @property
    def shape(self) -> tuple[int, ...]:
        """Return the expected array shape."""
        shape = []
        if self.number_of_frames > 1:
            shape.append(self.number_of_frames)

        shape += [self.ds.Rows, self.ds.Columns]
        if self.ds.SamplesPerPixel > 1:
            shape.append(self.ds.SamplesPerPixel)

        return tuple(shape)

    def __str__(self) -> str:
        """Return a string representation of the pixel reference."""
        s = [
            self.name,
            f"  Transfer Syntax: {self.ds.file_meta.TransferSyntaxUID.name}",
            f"  BitsAllocated: {self.ds.BitsAllocated}",
            f"  BitsStored: {self.ds.BitsStored}",
            f"  Rows: {self.ds.Rows}",
            f"  Columns: {self.ds.Columns}",
            f"  SamplesPerPixel: {self.ds.SamplesPerPixel}",
            f"  NumberOfFrames: {self.number_of_frames}",
            f"  PhotometricInterpretation: {self.ds.PhotometricInterpretation}",
            f"  Pixel VR: {self.ds[self.pixel_keyword].VR}",
        ]
        if self.pixel_keyword == "PixelData":
            s.append(f"  PixelRepresentation: {self.ds.PixelRepresentation}")

        return "\n".join(s)

    def test(self, arr: "np.ndarray", **kwargs: dict[str, Any]) -> None:
        self._test(self, arr, **kwargs)


PIXEL_REFERENCE = {}


# Little endian native datasets
# EXPL: ExplicitVRLittleEndian
# IMPL: ImplicitVRLittleEndian
# DEFL: DeflatedExplicitVRLittleEndian
# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.


# EXPL, (1, 1), (1, 512, 512, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert (0, 1, 1) == tuple(arr[155, 180:183])
    assert (1, 0, 1, 0) == tuple(arr[155, 310:314])
    assert (0, 1, 1) == tuple(arr[254, 78:81])
    assert (1, 0, 0, 1, 1, 0) == tuple(arr[254, 304:310])


EXPL_1_1_1F = PixelReference("liver_1frame.dcm", "u1", test)


# EXPL, (1, 1), (3, 512, 512, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    assert arr.max() == 1
    assert arr.min() == 0

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert 0 == frame[0][0]
        assert (0, 1, 1) == tuple(frame[155, 180:183])
        assert (1, 0, 1, 0) == tuple(frame[155, 310:314])
        assert (0, 1, 1) == tuple(frame[254, 78:81])
        assert (1, 0, 0, 1, 1, 0) == tuple(frame[254, 304:310])

    # Frame 2
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert 1 == frame[256][256]
        assert 0 == frame[146, :254].max()
        assert (0, 1, 1, 1, 1, 1, 0, 1) == tuple(frame[146, 253:261])
        assert 0 == frame[146, 261:].max()
        assert 0 == frame[210, :97].max()
        assert 1 == frame[210, 97:350].max()
        assert 0 == frame[210, 350:].max()

    # Frame 3
    if index in (None, 2):
        frame = arr if index == 2 else arr[2]
        assert 0 == frame[511][511]
        assert 0 == frame[147, :249].max()
        assert (0, 1, 0, 1, 1, 1) == tuple(frame[147, 248:254])
        assert (1, 0, 1, 0, 1, 1) == tuple(frame[147, 260:266])
        assert 0 == frame[147, 283:].max()
        assert 0 == frame[364, :138].max()
        assert (0, 1, 0, 1, 1, 0, 0, 1) == tuple(frame[364, 137:145])
        assert (1, 0, 0, 1, 0) == tuple(frame[364, 152:157])
        assert 0 == frame[364, 157:].max()


EXPL_1_1_3F = PixelReference("liver.dcm", "u1", test)


# DEFL, (8, 8), (1, 512, 512, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert 41 == arr[10].min()
    assert 255 == arr[10].max()
    assert (138, 65, 65, 65, 65, 35, 35, 35) == tuple(arr[300, 255:263])
    assert 65 == arr[500].min()
    assert 219 == arr[500].max()


DEFL_8_1_1F = PixelReference("image_dfl.dcm", "u1", test)


# EXPL, (8, 8), (1, 600, 800, 1), OW, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    assert 244 == arr[0].min() == arr[0].max()
    assert (1, 246, 1) == tuple(arr[300, 491:494])
    assert 0 == arr[-1].min() == arr[-1].max()


EXPL_8_1_1F = PixelReference("OBXXXX1A.dcm", "u1", test)


# EXPL, (8, 8), (2, 600, 800, 1), OW, PALETTE COLOR, "u1"
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert 244 == frame[0].min() == frame[0].max()
        assert (1, 246, 1) == tuple(frame[300, 491:494])
        assert 0 == frame[-1].min() == frame[-1].max()

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert 11 == frame[0].min() == frame[0].max()
        assert (254, 9, 254) == tuple(frame[300, 491:494])
        assert 255 == frame[-1].min() == frame[-1].max()


EXPL_8_1_2F = PixelReference("OBXXXX1A_2frame.dcm", "u1", test)


# EXPL, (8, 8), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (255, 0, 0) == tuple(arr[5, 50, :])
    assert (255, 128, 128) == tuple(arr[15, 50, :])
    assert (0, 255, 0) == tuple(arr[25, 50, :])
    assert (128, 255, 128) == tuple(arr[35, 50, :])
    assert (0, 0, 255) == tuple(arr[45, 50, :])
    assert (128, 128, 255) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (64, 64, 64) == tuple(arr[75, 50, :])
    assert (192, 192, 192) == tuple(arr[85, 50, :])
    assert (255, 255, 255) == tuple(arr[95, 50, :])


EXPL_8_3_1F = PixelReference("SC_rgb.dcm", "u1", test)


# EXPL, (8, 8), (1, 3, 3, 3), OW, RGB, 0
def test(ref, arr, **kwargs):
    assert arr[0].tolist() == [
        [166, 141, 52],
        [166, 141, 52],
        [166, 141, 52],
    ]
    assert arr[1].tolist() == [
        [63, 87, 176],
        [63, 87, 176],
        [63, 87, 176],
    ]
    assert arr[2].tolist() == [
        [158, 158, 158],
        [158, 158, 158],
        [158, 158, 158],
    ]


EXPL_8_3_1F_ODD = PixelReference("SC_rgb_small_odd.dcm", "u1", test)


# EXPL, (8, 8), (1, 100, 100, 3), OB, YBR_FULL_422, 0
def test(ref, arr, **kwargs):
    assert (76, 85, 255) == tuple(arr[5, 50, :])
    assert (166, 106, 193) == tuple(arr[15, 50, :])
    assert (150, 46, 20) == tuple(arr[25, 50, :])
    assert (203, 86, 75) == tuple(arr[35, 50, :])
    assert (29, 255, 107) == tuple(arr[45, 50, :])
    assert (142, 193, 118) == tuple(arr[55, 50, :])
    assert (0, 128, 128) == tuple(arr[65, 50, :])
    assert (64, 128, 128) == tuple(arr[75, 50, :])
    assert (192, 128, 128) == tuple(arr[85, 50, :])
    assert (255, 128, 128) == tuple(arr[95, 50, :])


EXPL_8_3_1F_YBR422 = PixelReference("SC_ybr_full_422_uncompressed.dcm", "u1", test)


# EXPL, (8, 8),  (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    if kwargs.get("as_rgb"):
        assert (254, 0, 0) == tuple(arr[5, 50, :])
        assert (255, 127, 127) == tuple(arr[15, 50, :])
        assert (0, 255, 5) == tuple(arr[25, 50, :])
        assert (129, 255, 129) == tuple(arr[35, 50, :])
        assert (0, 0, 254) == tuple(arr[45, 50, :])
        assert (128, 127, 255) == tuple(arr[55, 50, :])
        assert (0, 0, 0) == tuple(arr[65, 50, :])
        assert (64, 64, 64) == tuple(arr[75, 50, :])
        assert (192, 192, 192) == tuple(arr[85, 50, :])
        assert (255, 255, 255) == tuple(arr[95, 50, :])
    else:
        assert (76, 85, 255) == tuple(arr[5, 50, :])
        assert (166, 106, 193) == tuple(arr[15, 50, :])
        assert (150, 46, 20) == tuple(arr[25, 50, :])
        assert (203, 86, 75) == tuple(arr[35, 50, :])
        assert (29, 255, 107) == tuple(arr[45, 50, :])
        assert (142, 193, 118) == tuple(arr[55, 50, :])
        assert (0, 128, 128) == tuple(arr[65, 50, :])
        assert (64, 128, 128) == tuple(arr[75, 50, :])
        assert (192, 128, 128) == tuple(arr[85, 50, :])
        assert (255, 128, 128) == tuple(arr[95, 50, :])


EXPL_8_3_1F_YBR = PixelReference("SC_ybr_full_uncompressed.dcm", "u1", test)


# EXPL, (8, 8), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (255, 0, 0) == tuple(frame[5, 50, :])
        assert (255, 128, 128) == tuple(frame[15, 50, :])
        assert (0, 255, 0) == tuple(frame[25, 50, :])
        assert (128, 255, 128) == tuple(frame[35, 50, :])
        assert (0, 0, 255) == tuple(frame[45, 50, :])
        assert (128, 128, 255) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (64, 64, 64) == tuple(frame[75, 50, :])
        assert (192, 192, 192) == tuple(frame[85, 50, :])
        assert (255, 255, 255) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 255, 255) == tuple(frame[5, 50, :])
        assert (0, 127, 127) == tuple(frame[15, 50, :])
        assert (255, 0, 255) == tuple(frame[25, 50, :])
        assert (127, 0, 127) == tuple(frame[35, 50, :])
        assert (255, 255, 0) == tuple(frame[45, 50, :])
        assert (127, 127, 0) == tuple(frame[55, 50, :])
        assert (255, 255, 255) == tuple(frame[65, 50, :])
        assert (191, 191, 191) == tuple(frame[75, 50, :])
        assert (63, 63, 63) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPL_8_3_2F = PixelReference("SC_rgb_2frame.dcm", "u1", test)


# IMPL, (8, 8), (1, 256, 256, 3), OW, RGB, 0
def test(ref, arr, **kwargs):
    assert arr[29, 77:81].tolist() == [
        [240, 243, 246],
        [214, 210, 213],
        [150, 134, 134],
        [244, 244, 244],
    ]
    assert arr[224:227, 253].tolist() == [
        [231, 236, 238],
        [190, 175, 178],
        [215, 200, 202],
    ]


IMPL_08_08_3_0_1F_RGB = PixelReference("SC_rgb_jpeg_dcmd.dcm", "u1", test)


# EXPL, (16, 16), (1, 128, 128, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert arr[24, 36:40].tolist() == [520, 802, 930, 1008]
    assert arr[40:45, 40].tolist() == [1138, 1165, 1113, 1088, 1072]


EXPL_16_16_1F = PixelReference("CT_small.dcm", "i2", test)


# IMPL, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert (422, 319, 361) == tuple(arr[0, 31:34])
    assert (366, 363, 322) == tuple(arr[31, :3])
    assert (1369, 1129, 862) == tuple(arr[-1, -3:])
    # Last pixel
    assert 862 == arr[-1, -1]


IMPL_16_1_1F = PixelReference("MR_small_implicit.dcm", "<i2", test)


# EXPL, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert (422, 319, 361) == tuple(arr[0, 31:34])
    assert (366, 363, 322) == tuple(arr[31, :3])
    assert (1369, 1129, 862) == tuple(arr[-1, -3:])
    # Last pixel
    assert 862 == arr[-1, -1]


EXPL_16_1_1F = PixelReference("MR_small.dcm", "<i2", test)


# EXPL, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
# Pixel Data with 128 bytes trailing padding
def test(ref, arr, **kwargs):
    assert (422, 319, 361) == tuple(arr[0, 31:34])
    assert (366, 363, 322) == tuple(arr[31, :3])
    assert (1369, 1129, 862) == tuple(arr[-1, -3:])
    # Last pixel
    assert 862 == arr[-1, -1]


EXPL_16_1_1F_PAD = PixelReference("MR_small_padded.dcm", "<i2", test)


# EXPL, (16, 12), (10, 64, 64, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (206, 197, 159) == tuple(frame[0, 31:34])
        assert (49, 78, 128) == tuple(frame[31, :3])
        assert (362, 219, 135) == tuple(frame[-1, -3:])

    # Frame 5
    if index in (None, 4):
        frame = arr if index == 4 else arr[4]
        assert (67, 82, 44) == tuple(frame[0, 31:34])
        assert (37, 41, 17) == tuple(frame[31, :3])
        assert (225, 380, 355) == tuple(frame[-1, -3:])

    # Frame 10
    if index in (None, 9):
        frame = arr if index == 9 else arr[9]
        assert (72, 86, 69) == tuple(frame[0, 31:34])
        assert (25, 4, 9) == tuple(frame[31, :3])
        assert (227, 300, 147) == tuple(frame[-1, -3:])


EXPL_16_1_10F = PixelReference("emri_small.dcm", "<u2", test)


# EXPL, (16, 16), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (65535, 0, 0) == tuple(arr[5, 50, :])
    assert (65535, 32896, 32896) == tuple(arr[15, 50, :])
    assert (0, 65535, 0) == tuple(arr[25, 50, :])
    assert (32896, 65535, 32896) == tuple(arr[35, 50, :])
    assert (0, 0, 65535) == tuple(arr[45, 50, :])
    assert (32896, 32896, 65535) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (16448, 16448, 16448) == tuple(arr[75, 50, :])
    assert (49344, 49344, 49344) == tuple(arr[85, 50, :])
    assert (65535, 65535, 65535) == tuple(arr[95, 50, :])


EXPL_16_3_1F = PixelReference("SC_rgb_16bit.dcm", "<u2", test)


# EXPL, (16, 16), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (65535, 0, 0) == tuple(frame[5, 50, :])
        assert (65535, 32896, 32896) == tuple(frame[15, 50, :])
        assert (0, 65535, 0) == tuple(frame[25, 50, :])
        assert (32896, 65535, 32896) == tuple(frame[35, 50, :])
        assert (0, 0, 65535) == tuple(frame[45, 50, :])
        assert (32896, 32896, 65535) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (16448, 16448, 16448) == tuple(frame[75, 50, :])
        assert (49344, 49344, 49344) == tuple(frame[85, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 65535, 65535) == tuple(frame[5, 50, :])
        assert (0, 32639, 32639) == tuple(frame[15, 50, :])
        assert (65535, 0, 65535) == tuple(frame[25, 50, :])
        assert (32639, 0, 32639) == tuple(frame[35, 50, :])
        assert (65535, 65535, 0) == tuple(frame[45, 50, :])
        assert (32639, 32639, 0) == tuple(frame[55, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[65, 50, :])
        assert (49087, 49087, 49087) == tuple(frame[75, 50, :])
        assert (16191, 16191, 16191) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPL_16_3_2F = PixelReference("SC_rgb_16bit_2frame.dcm", "<u2", test)


# IMPL, (32, 32), (1, 10, 10, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert (1249000, 1249000, 1250000) == tuple(arr[0, :3])
    assert (1031000, 1029000, 1027000) == tuple(arr[4, 3:6])
    assert (803000, 801000, 798000) == tuple(arr[-1, -3:])


IMPL_32_1_1F = PixelReference("rtdose_1frame.dcm", "<u4", test)


# IMPL, (32, 32), (15, 10, 10, 1), OW, MONOCHROME2,
def test(ref, arr, **kwargs):
    index = kwargs.get("index")

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (1249000, 1249000, 1250000) == tuple(frame[0, :3])
        assert (1031000, 1029000, 1027000) == tuple(frame[4, 3:6])
        assert (803000, 801000, 798000) == tuple(frame[-1, -3:])

    # Frame 8
    if index in (None, 7):
        frame = arr if index == 7 else arr[7]
        assert (1253000, 1253000, 1249000) == tuple(frame[0, :3])
        assert (1026000, 1023000, 1022000) == tuple(frame[4, 3:6])
        assert (803000, 803000, 803000) == tuple(frame[-1, -3:])

    # Frame 15
    if index in (None, 14):
        frame = arr if index == 14 else arr[14]
        assert (1249000, 1250000, 1251000) == tuple(frame[0, :3])
        assert (1031000, 1031000, 1031000) == tuple(frame[4, 3:6])
        assert (801000, 800000, 799000) == tuple(frame[-1, -3:])


IMPL_32_1_15F = PixelReference("rtdose.dcm", "<u4", test)


# EXPL, (32, 32), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (4294967295, 0, 0) == tuple(arr[5, 50, :])
    assert (4294967295, 2155905152, 2155905152) == tuple(arr[15, 50, :])
    assert (0, 4294967295, 0) == tuple(arr[25, 50, :])
    assert (2155905152, 4294967295, 2155905152) == tuple(arr[35, 50, :])
    assert (0, 0, 4294967295) == tuple(arr[45, 50, :])
    assert (2155905152, 2155905152, 4294967295) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (1077952576, 1077952576, 1077952576) == tuple(arr[75, 50, :])
    assert (3233857728, 3233857728, 3233857728) == tuple(arr[85, 50, :])
    assert (4294967295, 4294967295, 4294967295) == tuple(arr[95, 50, :])


EXPL_32_3_1F = PixelReference("SC_rgb_32bit.dcm", "<u4", test)


# EXPL, (32, 32), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (4294967295, 0, 0) == tuple(frame[5, 50, :])
        assert (4294967295, 2155905152, 2155905152) == tuple(frame[15, 50, :])
        assert (0, 4294967295, 0) == tuple(frame[25, 50, :])
        assert (2155905152, 4294967295, 2155905152) == tuple(frame[35, 50, :])
        assert (0, 0, 4294967295) == tuple(frame[45, 50, :])
        assert (2155905152, 2155905152, 4294967295) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (1077952576, 1077952576, 1077952576) == tuple(frame[75, 50, :])
        assert (3233857728, 3233857728, 3233857728) == tuple(frame[85, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 4294967295, 4294967295) == tuple(frame[5, 50, :])
        assert (0, 2139062143, 2139062143) == tuple(frame[15, 50, :])
        assert (4294967295, 0, 4294967295) == tuple(frame[25, 50, :])
        assert (2139062143, 0, 2139062143) == tuple(frame[35, 50, :])
        assert (4294967295, 4294967295, 0) == tuple(frame[45, 50, :])
        assert (2139062143, 2139062143, 0) == tuple(frame[55, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(frame[65, 50, :])
        assert (3217014719, 3217014719, 3217014719) == tuple(frame[75, 50, :])
        assert (1061109567, 1061109567, 1061109567) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPL_32_3_2F = PixelReference("SC_rgb_32bit_2frame.dcm", "<u4", test)


PIXEL_REFERENCE[ExplicitVRLittleEndian] = [
    EXPL_1_1_1F,
    EXPL_1_1_3F,
    EXPL_8_1_1F,
    EXPL_8_1_2F,
    EXPL_8_3_1F,
    EXPL_8_3_1F_ODD,
    EXPL_8_3_1F_YBR422,
    EXPL_8_3_1F_YBR,
    EXPL_8_3_2F,
    EXPL_16_16_1F,
    EXPL_16_1_1F,
    EXPL_16_1_1F_PAD,
    EXPL_16_1_10F,
    EXPL_16_3_1F,
    EXPL_16_3_2F,
    EXPL_32_3_1F,
    EXPL_32_3_2F,
]
PIXEL_REFERENCE[ImplicitVRLittleEndian] = [
    IMPL_08_08_3_0_1F_RGB,
    IMPL_16_1_1F,
    IMPL_32_1_1F,
    IMPL_32_1_15F,
]
PIXEL_REFERENCE[DeflatedExplicitVRLittleEndian] = [DEFL_8_1_1F]


# Big endian datasets
# EXPB: ExplicitVRBigEndian
# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.


# EXPB, (1, 1), (1, 512, 512, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert 0 == arr.min()
    assert 1 == arr.max()
    assert tuple(arr[145, 250:260]) == (0, 0, 0, 0, 1, 1, 1, 1, 1, 0)


EXPB_1_1_1F = PixelReference("liver_expb_1frame.dcm", "u1", test)


# EXPB, (1, 1), (3, 512, 512, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    assert arr.max() == 1
    assert arr.min() == 0

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert 0 == frame[0][0]
        assert (0, 1, 1) == tuple(frame[155, 180:183])
        assert (1, 0, 1, 0) == tuple(frame[155, 310:314])
        assert (0, 1, 1) == tuple(frame[254, 78:81])
        assert (1, 0, 0, 1, 1, 0) == tuple(frame[254, 304:310])

    # Frame 2
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert 1 == frame[256][256]
        assert 0 == frame[146, :254].max()
        assert (0, 1, 1, 1, 1, 1, 0, 1) == tuple(frame[146, 253:261])
        assert 0 == frame[146, 261:].max()
        assert 0 == frame[210, :97].max()
        assert 1 == frame[210, 97:350].max()
        assert 0 == frame[210, 350:].max()

    # Frame 3
    if index in (None, 2):
        frame = arr if index == 2 else arr[2]
        assert 0 == frame[147, :249].max()
        assert 0 == frame[511][511]
        assert (0, 1, 0, 1, 1, 1) == tuple(frame[147, 248:254])
        assert (1, 0, 1, 0, 1, 1) == tuple(frame[147, 260:266])
        assert 0 == frame[147, 283:].max()
        assert 0 == frame[364, :138].max()
        assert (0, 1, 0, 1, 1, 0, 0, 1) == tuple(frame[364, 137:145])
        assert (1, 0, 0, 1, 0) == tuple(frame[364, 152:157])
        assert 0 == frame[364, 157:].max()


EXPB_1_1_3F = PixelReference("liver_expb.dcm", "u1", test)


# EXPB, (8, 8), (1, 600, 800, 1), OW, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    assert 244 == arr[0].min() == arr[0].max()
    assert (1, 246, 1) == tuple(arr[300, 491:494])
    assert 0 == arr[-1].min() == arr[-1].max()


EXPB_8_1_1F = PixelReference("OBXXXX1A_expb.dcm", "u1", test)


# EXPB, (8, 8), (2, 600, 800, 1), OW, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert 244 == frame[0].min() == frame[0].max()
        assert (1, 246, 1) == tuple(frame[300, 491:494])
        assert 0 == frame[-1].min() == frame[-1].max()

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert 11 == frame[0].min() == frame[0].max()
        assert (254, 9, 254) == tuple(frame[300, 491:494])
        assert 255 == frame[-1].min() == frame[-1].max()


EXPB_8_1_2F = PixelReference("OBXXXX1A_expb_2frame.dcm", "u1", test)


# EXPB, (8, 8), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (255, 0, 0) == tuple(arr[5, 50, :])
    assert (255, 128, 128) == tuple(arr[15, 50, :])
    assert (0, 255, 0) == tuple(arr[25, 50, :])
    assert (128, 255, 128) == tuple(arr[35, 50, :])
    assert (0, 0, 255) == tuple(arr[45, 50, :])
    assert (128, 128, 255) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (64, 64, 64) == tuple(arr[75, 50, :])
    assert (192, 192, 192) == tuple(arr[85, 50, :])
    assert (255, 255, 255) == tuple(arr[95, 50, :])


EXPB_8_3_1F = PixelReference("SC_rgb_expb.dcm", "u1", test)


# EXPB, (8, 8), (1, 3, 3, 3), OW, RGB, 0
def test(ref, arr, **kwargs):
    assert arr[0, 0].tolist() == [166, 141, 52]
    assert arr[1, 0].tolist() == [63, 87, 176]
    assert arr[2, 0].tolist() == [158, 158, 158]
    assert arr[-1, -1].tolist() == [158, 158, 158]


EXPB_8_3_1F_ODD = PixelReference("SC_rgb_small_odd_big_endian.dcm", "u1", test)


# EXPB, (8, 8), (1, 60, 80, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert arr[9, 3:6].tolist() == [[171, 171, 171], [255, 255, 255], [255, 255, 0]]
    assert arr[58, 8:12].tolist() == [
        [255, 236, 0],
        [255, 183, 0],
        [255, 175, 0],
        [255, 183, 0],
    ]


EXPB_8_8_3_1F_RGB = PixelReference("ExplVR_BigEnd.dcm", "u1", test)


# EXPB, (8, 8), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (255, 0, 0) == tuple(frame[5, 50, :])
        assert (255, 128, 128) == tuple(frame[15, 50, :])
        assert (0, 255, 0) == tuple(frame[25, 50, :])
        assert (128, 255, 128) == tuple(frame[35, 50, :])
        assert (0, 0, 255) == tuple(frame[45, 50, :])
        assert (128, 128, 255) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (64, 64, 64) == tuple(frame[75, 50, :])
        assert (192, 192, 192) == tuple(frame[85, 50, :])
        assert (255, 255, 255) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 255, 255) == tuple(frame[5, 50, :])
        assert (0, 127, 127) == tuple(frame[15, 50, :])
        assert (255, 0, 255) == tuple(frame[25, 50, :])
        assert (127, 0, 127) == tuple(frame[35, 50, :])
        assert (255, 255, 0) == tuple(frame[45, 50, :])
        assert (127, 127, 0) == tuple(frame[55, 50, :])
        assert (255, 255, 255) == tuple(frame[65, 50, :])
        assert (191, 191, 191) == tuple(frame[75, 50, :])
        assert (63, 63, 63) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPB_8_3_2F = PixelReference("SC_rgb_expb_2frame.dcm", "u1", test)


# EXPB, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert (422, 319, 361) == tuple(arr[0, 31:34])
    assert (366, 363, 322) == tuple(arr[31, :3])
    assert (1369, 1129, 862) == tuple(arr[-1, -3:])
    # Last pixel
    assert 862 == arr[-1, -1]


EXPB_16_1_1F = PixelReference("MR_small_expb.dcm", ">i2", test)


# EXPB, (16, 12), (10, 64, 64, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (206, 197, 159) == tuple(frame[0, 31:34])
        assert (49, 78, 128) == tuple(frame[31, :3])
        assert (362, 219, 135) == tuple(frame[-1, -3:])

    # Frame 5
    if index in (None, 4):
        frame = arr if index == 4 else arr[4]
        assert (67, 82, 44) == tuple(frame[0, 31:34])
        assert (37, 41, 17) == tuple(frame[31, :3])
        assert (225, 380, 355) == tuple(frame[-1, -3:])

    # Frame 10
    if index in (None, 9):
        frame = arr if index == 9 else arr[9]
        assert (72, 86, 69) == tuple(frame[0, 31:34])
        assert (25, 4, 9) == tuple(frame[31, :3])
        assert (227, 300, 147) == tuple(frame[-1, -3:])


EXPB_16_1_10F = PixelReference("emri_small_big_endian.dcm", ">u2", test)


# EXPB, (16, 16), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (65535, 0, 0) == tuple(arr[5, 50, :])
    assert (65535, 32896, 32896) == tuple(arr[15, 50, :])
    assert (0, 65535, 0) == tuple(arr[25, 50, :])
    assert (32896, 65535, 32896) == tuple(arr[35, 50, :])
    assert (0, 0, 65535) == tuple(arr[45, 50, :])
    assert (32896, 32896, 65535) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (16448, 16448, 16448) == tuple(arr[75, 50, :])
    assert (49344, 49344, 49344) == tuple(arr[85, 50, :])
    assert (65535, 65535, 65535) == tuple(arr[95, 50, :])


EXPB_16_3_1F = PixelReference("SC_rgb_expb_16bit.dcm", ">u2", test)


# EXPB, (16, 16), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (65535, 0, 0) == tuple(frame[5, 50, :])
        assert (65535, 32896, 32896) == tuple(frame[15, 50, :])
        assert (0, 65535, 0) == tuple(frame[25, 50, :])
        assert (32896, 65535, 32896) == tuple(frame[35, 50, :])
        assert (0, 0, 65535) == tuple(frame[45, 50, :])
        assert (32896, 32896, 65535) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (16448, 16448, 16448) == tuple(frame[75, 50, :])
        assert (49344, 49344, 49344) == tuple(frame[85, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 65535, 65535) == tuple(frame[5, 50, :])
        assert (0, 32639, 32639) == tuple(frame[15, 50, :])
        assert (65535, 0, 65535) == tuple(frame[25, 50, :])
        assert (32639, 0, 32639) == tuple(frame[35, 50, :])
        assert (65535, 65535, 0) == tuple(frame[45, 50, :])
        assert (32639, 32639, 0) == tuple(frame[55, 50, :])
        assert (65535, 65535, 65535) == tuple(frame[65, 50, :])
        assert (49087, 49087, 49087) == tuple(frame[75, 50, :])
        assert (16191, 16191, 16191) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPB_16_3_2F = PixelReference("SC_rgb_expb_16bit_2frame.dcm", ">u2", test)


# EXPB, (32, 32), (1, 10, 10, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert (1249000, 1249000, 1250000) == tuple(arr[0, :3])
    assert (1031000, 1029000, 1027000) == tuple(arr[4, 3:6])
    assert (803000, 801000, 798000) == tuple(arr[-1, -3:])


EXPB_32_1_1F = PixelReference("rtdose_expb_1frame.dcm", ">u4", test)


# EXPB, (32, 32), (15, 10, 10, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (1249000, 1249000, 1250000) == tuple(frame[0, :3])
        assert (1031000, 1029000, 1027000) == tuple(frame[4, 3:6])
        assert (803000, 801000, 798000) == tuple(frame[-1, -3:])

    # Frame 8
    if index in (None, 7):
        frame = arr if index == 7 else arr[7]
        assert (1253000, 1253000, 1249000) == tuple(frame[0, :3])
        assert (1026000, 1023000, 1022000) == tuple(frame[4, 3:6])
        assert (803000, 803000, 803000) == tuple(frame[-1, -3:])

    # Frame 15
    if index in (None, 14):
        frame = arr if index == 14 else arr[14]
        assert (1249000, 1250000, 1251000) == tuple(frame[0, :3])
        assert (1031000, 1031000, 1031000) == tuple(frame[4, 3:6])
        assert (801000, 800000, 799000) == tuple(frame[-1, -3:])


EXPB_32_1_15F = PixelReference("rtdose_expb.dcm", ">u4", test)


# EXPB, (32, 32), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert (4294967295, 0, 0) == tuple(arr[5, 50, :])
    assert (4294967295, 2155905152, 2155905152) == tuple(arr[15, 50, :])
    assert (0, 4294967295, 0) == tuple(arr[25, 50, :])
    assert (2155905152, 4294967295, 2155905152) == tuple(arr[35, 50, :])
    assert (0, 0, 4294967295) == tuple(arr[45, 50, :])
    assert (2155905152, 2155905152, 4294967295) == tuple(arr[55, 50, :])
    assert (0, 0, 0) == tuple(arr[65, 50, :])
    assert (1077952576, 1077952576, 1077952576) == tuple(arr[75, 50, :])
    assert (3233857728, 3233857728, 3233857728) == tuple(arr[85, 50, :])
    assert (4294967295, 4294967295, 4294967295) == tuple(arr[95, 50, :])


EXPB_32_3_1F = PixelReference("SC_rgb_expb_32bit.dcm", ">u4", test)


# EXPB, (32, 32), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert (4294967295, 0, 0) == tuple(frame[5, 50, :])
        assert (4294967295, 2155905152, 2155905152) == tuple(frame[15, 50, :])
        assert (0, 4294967295, 0) == tuple(frame[25, 50, :])
        assert (2155905152, 4294967295, 2155905152) == tuple(frame[35, 50, :])
        assert (0, 0, 4294967295) == tuple(frame[45, 50, :])
        assert (2155905152, 2155905152, 4294967295) == tuple(frame[55, 50, :])
        assert (0, 0, 0) == tuple(frame[65, 50, :])
        assert (1077952576, 1077952576, 1077952576) == tuple(frame[75, 50, :])
        assert (3233857728, 3233857728, 3233857728) == tuple(frame[85, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(frame[95, 50, :])

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert (0, 4294967295, 4294967295) == tuple(frame[5, 50, :])
        assert (0, 2139062143, 2139062143) == tuple(frame[15, 50, :])
        assert (4294967295, 0, 4294967295) == tuple(frame[25, 50, :])
        assert (2139062143, 0, 2139062143) == tuple(frame[35, 50, :])
        assert (4294967295, 4294967295, 0) == tuple(frame[45, 50, :])
        assert (2139062143, 2139062143, 0) == tuple(frame[55, 50, :])
        assert (4294967295, 4294967295, 4294967295) == tuple(frame[65, 50, :])
        assert (3217014719, 3217014719, 3217014719) == tuple(frame[75, 50, :])
        assert (1061109567, 1061109567, 1061109567) == tuple(frame[85, 50, :])
        assert (0, 0, 0) == tuple(frame[95, 50, :])


EXPB_32_3_2F = PixelReference("SC_rgb_expb_32bit_2frame.dcm", ">u4", test)


PIXEL_REFERENCE[ExplicitVRBigEndian] = [
    EXPB_1_1_1F,
    EXPB_1_1_3F,
    EXPB_8_1_1F,
    EXPB_8_1_2F,
    EXPB_8_3_1F,
    EXPB_8_3_1F_ODD,
    EXPB_8_8_3_1F_RGB,
    EXPB_8_3_2F,
    EXPB_16_1_1F,
    EXPB_16_1_10F,
    EXPB_16_3_1F,
    EXPB_16_3_2F,
    EXPB_32_1_1F,
    EXPB_32_1_15F,
    EXPB_32_3_1F,
    EXPB_32_3_2F,
]


# RLE Lossless
# RLE: RLELossless
# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.


# RLE, (8, 8), (1, 600, 800, 1), OB, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    assert arr[0].min() == arr[0].max() == 244
    assert tuple(arr[300, 491:494]) == (1, 246, 1)
    assert arr[-1].min() == arr[-1].max() == 0


RLE_8_1_1F = PixelReference("OBXXXX1A_rle.dcm", "u1", test)


# RLE, (8, 8), (2, 600, 800, 1), OB, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert 244 == frame[0].min() == frame[0].max() == 244
        assert tuple(frame[300, 491:494]) == (1, 246, 1)
        assert frame[-1].min() == frame[-1].max() == 0

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert 11 == frame[0].min() == frame[0].max()
        assert tuple(frame[300, 491:494]) == (254, 9, 254)
        assert frame[-1].min() == frame[-1].max() == 255


RLE_8_1_2F = PixelReference("OBXXXX1A_rle_2frame.dcm", "u1", test)


# RLE, (8, 8), (1, 100, 100, 3), OB, PALETTE COLOR, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (255, 0, 0)
    assert tuple(arr[15, 50, :]) == (255, 128, 128)
    assert tuple(arr[25, 50, :]) == (0, 255, 0)
    assert tuple(arr[35, 50, :]) == (128, 255, 128)
    assert tuple(arr[45, 50, :]) == (0, 0, 255)
    assert tuple(arr[55, 50, :]) == (128, 128, 255)
    assert tuple(arr[65, 50, :]) == (0, 0, 0)
    assert tuple(arr[75, 50, :]) == (64, 64, 64)
    assert tuple(arr[85, 50, :]) == (192, 192, 192)
    assert tuple(arr[95, 50, :]) == (255, 255, 255)


RLE_8_3_1F = PixelReference("SC_rgb_rle.dcm", "u1", test)


# RLE, (8, 8), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert tuple(frame[5, 50, :]) == (255, 0, 0)
        assert tuple(frame[15, 50, :]) == (255, 128, 128)
        assert tuple(frame[25, 50, :]) == (0, 255, 0)
        assert tuple(frame[35, 50, :]) == (128, 255, 128)
        assert tuple(frame[45, 50, :]) == (0, 0, 255)
        assert tuple(frame[55, 50, :]) == (128, 128, 255)
        assert tuple(frame[65, 50, :]) == (0, 0, 0)
        assert tuple(frame[75, 50, :]) == (64, 64, 64)
        assert tuple(frame[85, 50, :]) == (192, 192, 192)
        assert tuple(frame[95, 50, :]) == (255, 255, 255)

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert tuple(frame[5, 50, :]) == (0, 255, 255)
        assert tuple(frame[15, 50, :]) == (0, 127, 127)
        assert tuple(frame[25, 50, :]) == (255, 0, 255)
        assert tuple(frame[35, 50, :]) == (127, 0, 127)
        assert tuple(frame[45, 50, :]) == (255, 255, 0)
        assert tuple(frame[55, 50, :]) == (127, 127, 0)
        assert tuple(frame[65, 50, :]) == (255, 255, 255)
        assert tuple(frame[75, 50, :]) == (191, 191, 191)
        assert tuple(frame[85, 50, :]) == (63, 63, 63)
        assert tuple(frame[95, 50, :]) == (0, 0, 0)


RLE_8_3_2F = PixelReference("SC_rgb_rle_2frame.dcm", "u1", test)


# RLE, (16, 16), (1, 64, 64, 1), OB, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert tuple(arr[0, 31:34]) == (422, 319, 361)
    assert tuple(arr[31, :3]) == (366, 363, 322)
    assert tuple(arr[-1, -3:]) == (1369, 1129, 862)


RLE_16_1_1F = PixelReference("MR_small_RLE.dcm", "<i2", test)


# RLE, (16, 12), (10, 64, 64, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert tuple(frame[0, 31:34]) == (206, 197, 159)
        assert tuple(frame[31, :3]) == (49, 78, 128)
        assert tuple(frame[-1, -3:]) == (362, 219, 135)

    # Frame 5
    if index in (None, 4):
        frame = arr if index == 4 else arr[4]
        assert tuple(frame[0, 31:34]) == (67, 82, 44)
        assert tuple(frame[31, :3]) == (37, 41, 17)
        assert tuple(frame[-1, -3:]) == (225, 380, 355)

    # Frame 10
    if index in (None, 9):
        frame = arr if index == 9 else arr[9]
        assert tuple(frame[0, 31:34]) == (72, 86, 69)
        assert tuple(frame[31, :3]) == (25, 4, 9)
        assert tuple(frame[-1, -3:]) == (227, 300, 147)


RLE_16_1_10F = PixelReference("emri_small_RLE.dcm", "<u2", test)


# RLE, (16, 16), (1, 100, 100, 3), OW, RGB, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (65535, 0, 0)
    assert tuple(arr[15, 50, :]) == (65535, 32896, 32896)
    assert tuple(arr[25, 50, :]) == (0, 65535, 0)
    assert tuple(arr[35, 50, :]) == (32896, 65535, 32896)
    assert tuple(arr[45, 50, :]) == (0, 0, 65535)
    assert tuple(arr[55, 50, :]) == (32896, 32896, 65535)
    assert tuple(arr[65, 50, :]) == (0, 0, 0)
    assert tuple(arr[75, 50, :]) == (16448, 16448, 16448)
    assert tuple(arr[85, 50, :]) == (49344, 49344, 49344)
    assert tuple(arr[95, 50, :]) == (65535, 65535, 65535)


RLE_16_3_1F = PixelReference("SC_rgb_rle_16bit.dcm", "<u2", test)


# RLE, (16, 16), (2, 100, 100, 3), OW, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert tuple(frame[5, 50, :]) == (65535, 0, 0)
        assert tuple(frame[15, 50, :]) == (65535, 32896, 32896)
        assert tuple(frame[25, 50, :]) == (0, 65535, 0)
        assert tuple(frame[35, 50, :]) == (32896, 65535, 32896)
        assert tuple(frame[45, 50, :]) == (0, 0, 65535)
        assert tuple(frame[55, 50, :]) == (32896, 32896, 65535)
        assert tuple(frame[65, 50, :]) == (0, 0, 0)
        assert tuple(frame[75, 50, :]) == (16448, 16448, 16448)
        assert tuple(frame[85, 50, :]) == (49344, 49344, 49344)
        assert tuple(frame[95, 50, :]) == (65535, 65535, 65535)

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert tuple(frame[5, 50, :]) == (0, 65535, 65535)
        assert tuple(frame[15, 50, :]) == (0, 32639, 32639)
        assert tuple(frame[25, 50, :]) == (65535, 0, 65535)
        assert tuple(frame[35, 50, :]) == (32639, 0, 32639)
        assert tuple(frame[45, 50, :]) == (65535, 65535, 0)
        assert tuple(frame[55, 50, :]) == (32639, 32639, 0)
        assert tuple(frame[65, 50, :]) == (65535, 65535, 65535)
        assert tuple(frame[75, 50, :]) == (49087, 49087, 49087)
        assert tuple(frame[85, 50, :]) == (16191, 16191, 16191)
        assert tuple(frame[95, 50, :]) == (0, 0, 0)


RLE_16_3_2F = PixelReference("SC_rgb_rle_16bit_2frame.dcm", "<u2", test)


# RLE, (32, 32), (1, 10, 10, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[0, :3]) == (1249000, 1249000, 1250000)
    assert tuple(arr[4, 3:6]) == (1031000, 1029000, 1027000)
    assert tuple(arr[-1, -3:]) == (803000, 801000, 798000)


RLE_32_1_1F = PixelReference("rtdose_rle_1frame.dcm", "<u4", test)


# RLE, (32, 32), (15, 10, 10, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert tuple(frame[0, :3]) == (1249000, 1249000, 1250000)
        assert tuple(frame[4, 3:6]) == (1031000, 1029000, 1027000)
        assert tuple(frame[-1, -3:]) == (803000, 801000, 798000)

    # Frame 8
    if index in (None, 7):
        frame = arr if index == 7 else arr[7]
        assert tuple(frame[0, :3]) == (1253000, 1253000, 1249000)
        assert tuple(frame[4, 3:6]) == (1026000, 1023000, 1022000)
        assert tuple(frame[-1, -3:]) == (803000, 803000, 803000)

    # Frame 15
    if index in (None, 14):
        frame = arr if index == 14 else arr[14]
        assert tuple(frame[0, :3]) == (1249000, 1250000, 1251000)
        assert tuple(frame[4, 3:6]) == (1031000, 1031000, 1031000)
        assert tuple(frame[-1, -3:]) == (801000, 800000, 799000)


RLE_32_1_15F = PixelReference("rtdose_rle.dcm", "<u4", test)


# RLE, (32, 32), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (4294967295, 0, 0)
    assert tuple(arr[15, 50, :]) == (4294967295, 2155905152, 2155905152)
    assert tuple(arr[25, 50, :]) == (0, 4294967295, 0)
    assert tuple(arr[35, 50, :]) == (2155905152, 4294967295, 2155905152)
    assert tuple(arr[45, 50, :]) == (0, 0, 4294967295)
    assert tuple(arr[55, 50, :]) == (2155905152, 2155905152, 4294967295)
    assert tuple(arr[65, 50, :]) == (0, 0, 0)
    assert tuple(arr[75, 50, :]) == (1077952576, 1077952576, 1077952576)
    assert tuple(arr[85, 50, :]) == (3233857728, 3233857728, 3233857728)
    assert tuple(arr[95, 50, :]) == (4294967295, 4294967295, 4294967295)


RLE_32_3_1F = PixelReference("SC_rgb_rle_32bit.dcm", "<u4", test)


# RLE, (32, 32), (2, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    index = kwargs.get("index", None)

    # Frame 1
    if index in (None, 0):
        frame = arr if index == 0 else arr[0]
        assert tuple(frame[5, 50, :]) == (4294967295, 0, 0)
        assert tuple(frame[15, 50, :]) == (4294967295, 2155905152, 2155905152)
        assert tuple(frame[25, 50, :]) == (0, 4294967295, 0)
        assert tuple(frame[35, 50, :]) == (2155905152, 4294967295, 2155905152)
        assert tuple(frame[45, 50, :]) == (0, 0, 4294967295)
        assert tuple(frame[55, 50, :]) == (2155905152, 2155905152, 4294967295)
        assert tuple(frame[65, 50, :]) == (0, 0, 0)
        assert tuple(frame[75, 50, :]) == (1077952576, 1077952576, 1077952576)
        assert tuple(frame[85, 50, :]) == (3233857728, 3233857728, 3233857728)
        assert tuple(frame[95, 50, :]) == (4294967295, 4294967295, 4294967295)

    # Frame 2 is frame 1 inverted
    if index in (None, 1):
        frame = arr if index == 1 else arr[1]
        assert tuple(frame[5, 50, :]) == (0, 4294967295, 4294967295)
        assert tuple(frame[15, 50, :]) == (0, 2139062143, 2139062143)
        assert tuple(frame[25, 50, :]) == (4294967295, 0, 4294967295)
        assert tuple(frame[35, 50, :]) == (2139062143, 0, 2139062143)
        assert tuple(frame[45, 50, :]) == (4294967295, 4294967295, 0)
        assert tuple(frame[55, 50, :]) == (2139062143, 2139062143, 0)
        assert tuple(frame[65, 50, :]) == (4294967295, 4294967295, 4294967295)
        assert tuple(frame[75, 50, :]) == (3217014719, 3217014719, 3217014719)
        assert tuple(frame[85, 50, :]) == (1061109567, 1061109567, 1061109567)
        assert tuple(frame[95, 50, :]) == (0, 0, 0)


RLE_32_3_2F = PixelReference("SC_rgb_rle_32bit_2frame.dcm", "<u4", test)


PIXEL_REFERENCE[RLELossless] = [
    RLE_8_1_1F,
    RLE_8_1_2F,
    RLE_8_3_1F,
    RLE_8_3_2F,
    RLE_16_1_1F,
    RLE_16_1_10F,
    RLE_16_3_1F,
    RLE_16_3_2F,
    RLE_32_1_1F,
    RLE_32_1_15F,
    RLE_32_3_1F,
    RLE_32_3_2F,
]


# JPEG - ISO/IEC 10918 Standard
# JPGB: JPEGBaseline8Bit
# JPGE: JPEGExtended12Bit
# JPGL: JPEGLossless
# JPGS: JPEGLosslessSV1


# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.
# 0: JPGB, (8, 8), (1, 3, 3, 3), OB, YBR_FULL, 0
# Uses a JFIF APP marker
def test(ref, arr, **kwargs):
    # Pillow, pylibjpeg
    assert tuple(arr[0, 0, :]) == (138, 78, 147)
    assert tuple(arr[1, 0, :]) == (90, 178, 108)
    assert tuple(arr[2, 0, :]) == (158, 126, 129)


JPGB_08_08_3_0_1F_YBR_FULL = PixelReference("SC_rgb_small_odd_jpeg.dcm", "u1", test)


# JPGB, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# JPEG baseline in RGB colourspace with no APP14 marker
def test(ref, arr, **kwargs):
    assert arr[29, 77:81].tolist() == [
        [240, 243, 246],
        [214, 210, 213],
        [150, 134, 134],
        [244, 244, 244],
    ]
    if kwargs.get("plugin", None) in ("pillow", "gdcm"):
        assert arr[224:227, 253].tolist() == [
            [231, 236, 238],
            [190, 175, 178],
            [215, 200, 202],
        ]
    else:
        assert arr[224:227, 253].tolist() == [
            [232, 236, 238],
            [190, 175, 178],
            [215, 200, 202],
        ]


JPGB_08_08_3_0_1F_RGB_NO_APP14 = PixelReference(
    "SC_jpeg_no_color_transform.dcm", "u1", test
)


# JPGB, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# JPEG baseline in RGB colourspace with APP14 Adobe v101 marker
def test(ref, arr, **kwargs):
    plugin = kwargs.get("plugin", None)
    if plugin in ("pillow", "gdcm"):
        assert arr[99:104, 172].tolist() == [
            [243, 244, 246],
            [229, 224, 235],
            [204, 190, 213],
            [194, 176, 203],
            [204, 188, 211],
        ]
        assert arr[84, 239:243].tolist() == [
            [229, 225, 234],
            [174, 174, 202],
            [187, 185, 203],
            [210, 207, 225],
        ]
    elif plugin == "pylibjpeg":
        assert arr[99:104, 172].tolist() == [
            [243, 244, 246],
            [229, 224, 235],
            [204, 191, 213],
            [194, 176, 203],
            [204, 188, 211],
        ]
        assert arr[84, 239:243].tolist() == [
            [229, 225, 234],
            [174, 174, 202],
            [187, 185, 203],
            [211, 207, 225],
        ]


JPGB_08_08_3_0_1F_RGB_APP14 = PixelReference(
    "SC_jpeg_no_color_transform_2.dcm", "u1", test
)


# JPGB, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# JPEG baseline in RGB colourspace with APP14 Adobe v101 marker
def test(ref, arr, **kwargs):
    plugin = kwargs.get("plugin", None)
    if plugin in ("pillow", "gdcm"):
        assert arr[99:104, 172].tolist() == [
            [243, 244, 246],
            [229, 224, 235],
            [204, 190, 213],
            [194, 176, 203],
            [204, 188, 211],
        ]
        assert arr[84, 239:243].tolist() == [
            [229, 225, 234],
            [174, 174, 202],
            [187, 185, 203],
            [210, 207, 225],
        ]
    elif plugin == "pylibjpeg":
        assert arr[99:104, 172].tolist() == [
            [243, 244, 246],
            [229, 224, 235],
            [204, 191, 213],
            [194, 176, 203],
            [204, 188, 211],
        ]
        assert arr[84, 239:243].tolist() == [
            [229, 225, 234],
            [174, 174, 202],
            [187, 185, 203],
            [211, 207, 225],
        ]


JPGB_08_08_3_0_1F_RGB_DCMD_APP14 = PixelReference(
    "SC_rgb_jpeg_app14_dcmd.dcm", "u1", test
)


# JPGB, (8, 8), (120, 480, 640, 3), OB, YBR_FULL_422, 0
def test(ref, arr, **kwargs):
    # Pillow, pylibjpeg, gdcm
    if kwargs.get("as_rgb", False) and kwargs.get("plugin", None) == "pylibjpeg":
        index = kwargs.get("index", None)
        if index == 0:
            assert arr[278, 300:310].tolist() == [
                [64, 64, 64],
                [76, 76, 76],
                [86, 86, 86],
                [95, 95, 95],
                [95, 95, 95],
                [97, 97, 97],
                [98, 98, 98],
                [98, 98, 98],
                [106, 106, 106],
                [108, 108, 108],
            ]

        if index == 60:
            assert arr[278, 300:310].tolist() == [
                [36, 36, 36],
                [38, 38, 38],
                [41, 41, 41],
                [47, 47, 47],
                [50, 50, 50],
                [50, 50, 50],
                [53, 53, 53],
                [51, 51, 51],
                [47, 47, 47],
                [38, 38, 38],
            ]

        if index == -1:
            assert arr[278, 300:310].tolist() == [
                [46, 46, 46],
                [55, 55, 55],
                [64, 64, 64],
                [74, 74, 74],
                [81, 81, 81],
                [86, 86, 86],
                [97, 97, 97],
                [104, 104, 104],
                [110, 110, 110],
                [117, 117, 117],
            ]

        return

    assert arr[0, 278, 300:310].tolist() == [
        [64, 128, 128],
        [76, 128, 128],
        [86, 128, 128],
        [95, 128, 128],
        [95, 128, 128],
        [97, 128, 128],
        [98, 128, 128],
        [98, 128, 128],
        [106, 128, 128],
        [108, 128, 128],
    ]
    if kwargs.get("plugin", None) in ("pillow", "gdcm"):
        assert arr[59, 278, 300:310].tolist() == [
            [22, 128, 128],
            [22, 128, 128],
            [27, 128, 128],
            [32, 128, 128],
            [32, 128, 128],
            [29, 128, 128],
            [23, 128, 128],
            [21, 128, 128],
            [24, 128, 128],
            [33, 128, 128],
        ]
        assert arr[-1, 278, 300:310].tolist() == [
            [46, 128, 128],
            [55, 128, 128],
            [64, 128, 128],
            [74, 128, 128],
            [80, 128, 128],
            [86, 128, 128],
            [97, 128, 128],
            [104, 128, 128],
            [110, 128, 128],
            [117, 128, 128],
        ]
    elif kwargs.get("plugin", None) == "pylibjpeg":
        assert arr[59, 278, 300:310].tolist() == [
            [22, 128, 128],
            [22, 128, 128],
            [27, 128, 128],
            [32, 128, 128],
            [32, 128, 128],
            [30, 128, 128],
            [23, 128, 128],
            [21, 128, 128],
            [24, 128, 128],
            [33, 128, 128],
        ]
        assert arr[-1, 278, 300:310].tolist() == [
            [46, 128, 128],
            [55, 128, 128],
            [64, 128, 128],
            [74, 128, 128],
            [81, 128, 128],
            [86, 128, 128],
            [97, 128, 128],
            [104, 128, 128],
            [110, 128, 128],
            [117, 128, 128],
        ]


JPGB_08_08_3_0_120F_YBR_FULL_422 = PixelReference(
    "color3d_jpeg_baseline.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (76, 85, 255)
    assert tuple(arr[15, 50, :]) == (166, 106, 193)
    assert tuple(arr[25, 50, :]) == (150, 46, 20)
    assert tuple(arr[35, 50, :]) == (203, 86, 75)
    assert tuple(arr[45, 50, :]) == (29, 255, 107)
    assert tuple(arr[55, 50, :]) == (142, 193, 118)
    assert tuple(arr[65, 50, :]) == (0, 128, 128)
    assert tuple(arr[75, 50, :]) == (64, 128, 128)
    assert tuple(arr[85, 50, :]) == (192, 128, 128)
    assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_1F_YBR_FULL = PixelReference("SC_rgb_jpeg_dcmtk.dcm", "u1", test)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL_422, 0
# Different subsampling 411, 422, 444
def test(ref, arr, **kwargs):
    if kwargs.get("plugin", None) in ("pillow", "gdcm"):
        assert tuple(arr[5, 50, :]) == (76, 85, 254)
        assert tuple(arr[15, 50, :]) == (166, 109, 190)
        assert tuple(arr[25, 50, :]) == (150, 46, 21)
        assert tuple(arr[35, 50, :]) == (203, 85, 74)
        assert tuple(arr[45, 50, :]) == (29, 255, 108)
        assert tuple(arr[55, 50, :]) == (142, 192, 117)
        assert tuple(arr[65, 50, :]) == (0, 128, 128)
        assert tuple(arr[75, 50, :]) == (64, 128, 128)
        assert tuple(arr[85, 50, :]) == (192, 128, 128)
        assert tuple(arr[95, 50, :]) == (255, 128, 128)
    else:
        # pylibjpeg
        assert tuple(arr[5, 50, :]) == (76, 85, 254)
        assert tuple(arr[15, 50, :]) == (166, 108, 190)
        assert tuple(arr[25, 50, :]) == (150, 46, 21)
        assert tuple(arr[35, 50, :]) == (203, 86, 74)
        assert tuple(arr[45, 50, :]) == (29, 255, 107)
        assert tuple(arr[55, 50, :]) == (142, 192, 117)
        assert tuple(arr[65, 50, :]) == (0, 128, 128)
        assert tuple(arr[75, 50, :]) == (64, 128, 128)
        assert tuple(arr[85, 50, :]) == (192, 128, 128)
        assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_0_1F_YBR_FULL_422_411 = PixelReference(
    "SC_rgb_dcmtk_+eb+cy+np.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL_422, 0
def test(ref, arr, **kwargs):
    # Pillow, pylibjpeg
    assert tuple(arr[5, 50, :]) == (76, 85, 255)
    assert tuple(arr[15, 50, :]) == (166, 106, 193)
    assert tuple(arr[25, 50, :]) == (150, 46, 20)
    assert tuple(arr[35, 50, :]) == (203, 86, 75)
    assert tuple(arr[45, 50, :]) == (29, 255, 107)
    assert tuple(arr[55, 50, :]) == (142, 193, 118)
    assert tuple(arr[65, 50, :]) == (0, 128, 128)
    assert tuple(arr[75, 50, :]) == (64, 128, 128)
    assert tuple(arr[85, 50, :]) == (192, 128, 128)
    assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_0_1F_YBR_FULL_422_422 = PixelReference(
    "SC_rgb_dcmtk_+eb+cy+s2.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    if kwargs.get("plugin", None) in ("pillow", "gdcm"):
        assert tuple(arr[5, 50, :]) == (76, 85, 254)
        assert tuple(arr[15, 50, :]) == (166, 109, 190)
        assert tuple(arr[25, 50, :]) == (150, 46, 21)
        assert tuple(arr[35, 50, :]) == (203, 85, 74)
        assert tuple(arr[45, 50, :]) == (29, 255, 108)
        assert tuple(arr[55, 50, :]) == (142, 192, 117)
        assert tuple(arr[65, 50, :]) == (0, 128, 128)
        assert tuple(arr[75, 50, :]) == (64, 128, 128)
        assert tuple(arr[85, 50, :]) == (192, 128, 128)
        assert tuple(arr[95, 50, :]) == (255, 128, 128)
    else:
        # pylibjpeg
        assert tuple(arr[5, 50, :]) == (76, 85, 254)
        assert tuple(arr[15, 50, :]) == (166, 108, 190)
        assert tuple(arr[25, 50, :]) == (150, 46, 21)
        assert tuple(arr[35, 50, :]) == (203, 86, 74)
        assert tuple(arr[45, 50, :]) == (29, 255, 107)
        assert tuple(arr[55, 50, :]) == (142, 192, 117)
        assert tuple(arr[65, 50, :]) == (0, 128, 128)
        assert tuple(arr[75, 50, :]) == (64, 128, 128)
        assert tuple(arr[85, 50, :]) == (192, 128, 128)
        assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_0_1F_YBR_FULL_411 = PixelReference(
    "SC_rgb_dcmtk_+eb+cy+n1.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    # pillow, pylibjpeg
    assert tuple(arr[5, 50, :]) == (76, 85, 255)
    assert tuple(arr[15, 50, :]) == (166, 106, 193)
    assert tuple(arr[25, 50, :]) == (150, 46, 20)
    assert tuple(arr[35, 50, :]) == (203, 86, 75)
    assert tuple(arr[45, 50, :]) == (29, 255, 107)
    assert tuple(arr[55, 50, :]) == (142, 193, 118)
    assert tuple(arr[65, 50, :]) == (0, 128, 128)
    assert tuple(arr[75, 50, :]) == (64, 128, 128)
    assert tuple(arr[85, 50, :]) == (192, 128, 128)
    assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_0_1F_YBR_FULL_422 = PixelReference(
    "SC_rgb_dcmtk_+eb+cy+n2.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    # pillow, pylibjpeg
    assert tuple(arr[5, 50, :]) == (76, 85, 255)
    assert tuple(arr[15, 50, :]) == (166, 106, 193)
    assert tuple(arr[25, 50, :]) == (150, 46, 20)
    assert tuple(arr[35, 50, :]) == (203, 86, 75)
    assert tuple(arr[45, 50, :]) == (29, 255, 107)
    assert tuple(arr[55, 50, :]) == (142, 193, 118)
    assert tuple(arr[65, 50, :]) == (0, 128, 128)
    assert tuple(arr[75, 50, :]) == (64, 128, 128)
    assert tuple(arr[85, 50, :]) == (192, 128, 128)
    assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_0_1F_YBR_FULL_444 = PixelReference(
    "SC_rgb_dcmtk_+eb+cy+s4.dcm", "u1", test
)


# JPGB, (8, 8), (1, 100, 100, 3), OB, RGB, 0
# Uses RGB component IDs
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (255, 0, 0)
    assert tuple(arr[15, 50, :]) == (255, 128, 128)
    assert tuple(arr[25, 50, :]) == (0, 255, 0)
    assert tuple(arr[35, 50, :]) == (128, 255, 128)
    assert tuple(arr[45, 50, :]) == (0, 0, 255)
    assert tuple(arr[55, 50, :]) == (128, 128, 255)
    assert tuple(arr[65, 50, :]) == (0, 0, 0)
    assert tuple(arr[75, 50, :]) == (64, 64, 64)
    assert tuple(arr[85, 50, :]) == (192, 192, 192)
    assert tuple(arr[95, 50, :]) == (255, 255, 255)


JPGB_08_08_3_0_1F_RGB = PixelReference("SC_rgb_dcmtk_+eb+cr.dcm", "u1", test)


# JPGB, (8, 8), (1, 100, 100, 3), OB, YBR_FULL, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (76, 85, 255)
    assert tuple(arr[15, 50, :]) == (166, 107, 191)
    assert tuple(arr[25, 50, :]) == (150, 44, 21)
    assert tuple(arr[35, 50, :]) == (203, 86, 75)
    assert tuple(arr[45, 50, :]) == (29, 255, 107)
    assert tuple(arr[55, 50, :]) == (142, 191, 118)
    assert tuple(arr[65, 50, :]) == (0, 128, 128)
    assert tuple(arr[75, 50, :]) == (64, 128, 128)
    assert tuple(arr[85, 50, :]) == (192, 128, 128)
    assert tuple(arr[95, 50, :]) == (255, 128, 128)


JPGB_08_08_3_1F_YBR_FULL = PixelReference("SC_rgb_jpeg_lossy_gdcm.dcm", "u1", test)


# JPGE, (16, 12), (1, 1024, 256, 1), OB, MONOCHROME2, 0
# Bad file - scan stop has invalid value
def test(ref, arr, **kwargs):
    # pylibjpeg won't decode due to invalid value scan stop value
    # gdcm won't decode due to 12-bit
    assert 244 == arr[420, 140]
    assert 95 == arr[230, 120]


JPGE_BAD = PixelReference("JPEG-lossy.dcm", "u2", test)


# JPGE, (16, 12), (1, 1024, 256, 1), OB, MONOCHROME2,
# Fixed version of JPEG_BAD
def test(ref, arr, **kwargs):
    # pylibjpeg, gdcm
    assert 244 == arr[420, 140]
    assert 95 == arr[230, 120]


JPGE_16_12_1_0_1F_M2 = PixelReference("JPGExtended.dcm", "u2", test)


# JPGS, (8, 8), (1, 768, 1024, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    # pylibjpeg
    assert tuple(arr[300, 512:520]) == (26, 26, 25, 22, 19, 16, 14, 15)
    assert tuple(arr[600, 512:520]) == (45, 43, 41, 38, 33, 30, 26, 21)


JPGS_08_08_1_0_1F = PixelReference("JPGLosslessP14SV1_1s_1f_8b.dcm", "u1", test)


# JPGS, (16, 16), (1, 1024, 256, 1), OB, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    # pylibjpeg
    assert tuple(arr[400, 124:132]) == (60, 58, 61, 68, 59, 65, 64, 67)
    assert tuple(arr[600, 124:132]) == (3, 1, 2, 0, 2, 1, 2, 0)


JPGS_16_16_1_1_1F_M2 = PixelReference("JPEG-LL.dcm", "<i2", test)


# JPGS, (8, 8), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    assert tuple(arr[5, 50, :]) == (255, 0, 0)
    assert tuple(arr[15, 50, :]) == (255, 128, 128)
    assert tuple(arr[25, 50, :]) == (0, 255, 0)
    assert tuple(arr[35, 50, :]) == (128, 255, 128)
    assert tuple(arr[45, 50, :]) == (0, 0, 255)
    assert tuple(arr[55, 50, :]) == (128, 128, 255)
    assert tuple(arr[65, 50, :]) == (0, 0, 0)
    assert tuple(arr[75, 50, :]) == (64, 64, 64)
    assert tuple(arr[85, 50, :]) == (192, 192, 192)
    assert tuple(arr[95, 50, :]) == (255, 255, 255)


JPGS_08_08_3_1F_RGB = PixelReference("SC_rgb_jpeg_gdcm.dcm", "u1", test)


PIXEL_REFERENCE[JPEGBaseline8Bit] = [
    JPGB_08_08_3_0_1F_YBR_FULL,
    JPGB_08_08_3_0_1F_RGB_NO_APP14,
    JPGB_08_08_3_0_1F_RGB_APP14,
    JPGB_08_08_3_0_1F_RGB_DCMD_APP14,
    JPGB_08_08_3_0_120F_YBR_FULL_422,
    JPGB_08_08_3_1F_YBR_FULL,
    JPGB_08_08_3_0_1F_YBR_FULL_422_411,
    JPGB_08_08_3_0_1F_YBR_FULL_422_422,
    JPGB_08_08_3_0_1F_YBR_FULL_411,
    JPGB_08_08_3_0_1F_YBR_FULL_422,
    JPGB_08_08_3_0_1F_YBR_FULL_444,
    JPGB_08_08_3_0_1F_RGB,
    JPGB_08_08_3_1F_YBR_FULL,
]
PIXEL_REFERENCE[JPEGExtended12Bit] = [JPGE_BAD, JPGE_16_12_1_0_1F_M2]
PIXEL_REFERENCE[JPEGLossless] = []
PIXEL_REFERENCE[JPEGLosslessSV1] = [
    JPGS_08_08_1_0_1F,
    JPGS_16_16_1_1_1F_M2,
    JPGS_08_08_3_1F_RGB,
]


# JPEG-LS - ISO/IEC 14495 Standard
# JLSL: JPEGLSLossless
# JLSN: JPEGLSNearLossless
# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.


# JLSL, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# Plane interleaved (ILV 0)
def test(ref, arr, **kwargs):
    assert arr[124:128, 40].tolist() == [
        [115, 109, 91],
        [109, 105, 100],
        [100, 111, 94],
        [192, 53, 172],
    ]


JLSL_08_08_3_0_1F_ILV0 = PixelReference("JLSL_RGB_ILV0.dcm", "u1", test)


# JLSL, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# Line interleaved (ILV 1)
def test(ref, arr, **kwargs):
    assert arr[124:128, 40].tolist() == [
        [115, 109, 91],
        [109, 105, 100],
        [100, 111, 94],
        [192, 53, 172],
    ]


JLSL_08_08_3_0_1F_ILV1 = PixelReference("JLSL_RGB_ILV1.dcm", "u1", test)


# JLSL, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# Sample interleaved (ILV 2)
def test(ref, arr, **kwargs):
    assert arr[124:128, 40].tolist() == [
        [115, 109, 91],
        [109, 105, 100],
        [100, 111, 94],
        [192, 53, 172],
    ]


JLSL_08_08_3_0_1F_ILV2 = PixelReference("JLSL_RGB_ILV2.dcm", "u1", test)


# JLSL, (8, 7), (1, 128, 128, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert arr[59:69, 58].tolist() == [55, 53, 58, 85, 109, 123, 116, 102, 98, 89]


JLSL_08_07_1_0_1F = PixelReference("JLSL_08_07_0_1F.dcm", "u1", test)


# JLSL, (16, 15), (1, 128, 128, 1), OB, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    assert arr[59:65, 58].tolist() == [-2073, -2629, -1167, 5566, 11808, 15604]


JLSL_16_15_1_1_1F = PixelReference("JLSL_16_15_1_1F.dcm", "i2", test)


# JLSL, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    # pylibjpeg, pyjpegls
    assert (422, 319, 361) == tuple(arr[0, 31:34])
    assert (366, 363, 322) == tuple(arr[31, :3])
    assert (1369, 1129, 862) == tuple(arr[-1, -3:])
    assert arr[55:65, 35].tolist() == [170, 193, 191, 373, 1293, 2053, 1879, 1683, 1711]


JLSL_16_16_1_1_1F = PixelReference("MR_small_jpeg_ls_lossless.dcm", "<i2", test)


# JLSL, (16, 12), (10, 64, 64, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("emri_small.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


JLSL_16_12_1_1_10F = PixelReference("emri_small_jpeg_ls_lossless.dcm", "<u2", test)


# JLSN, (8, 8), (1, 45, 10, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert arr[0, 0] == 255
    assert arr[5, 0] == 125
    assert arr[10, 0] == 65
    assert arr[15, 0] == 30
    assert arr[20, 0] == 15
    assert arr[25, 0] == 5
    assert arr[30, 0] == 5
    assert arr[35, 0] == 0
    assert arr[40, 0] == 0


JLSN_08_01_1_0_1F = PixelReference("JPEGLSNearLossless_08.dcm", "u1", test)


# JLSN, (8, 8), (1, 256, 256, 3), OB, RGB, 0
# Plane interleaved (ILV 0), lossy error 3
def test(ref, arr, **kwargs):
    assert arr[124:128, 40].tolist() == [
        [118, 110, 92],
        [110, 103, 99],
        [97, 113, 96],
        [191, 55, 175],
    ]


JLSN_08_08_3_0_1F_ILV0 = PixelReference("JLSN_RGB_ILV0.dcm", "u1", test)


# JLSN, (8, 8), (1, 100, 100, 3), OB, RGB, 0
# Line interleaved (ILV 1)
def test(ref, arr, **kwargs):
    assert arr[0, 0].tolist() == [255, 0, 0]
    assert arr[10, 0].tolist() == [255, 130, 130]
    assert arr[20, 0].tolist() == [0, 255, 0]
    assert arr[30, 0].tolist() == [130, 255, 130]
    assert arr[40, 0].tolist() == [0, 0, 255]
    assert arr[50, 0].tolist() == [130, 130, 255]
    assert arr[60, 0].tolist() == [0, 0, 0]
    assert arr[70, 0].tolist() == [65, 65, 65]
    assert arr[80, 0].tolist() == [190, 190, 190]
    assert arr[90, 0].tolist() == [255, 255, 255]


JLSN_08_08_1_0_3F_LINE = PixelReference("SC_rgb_jls_lossy_line.dcm", "u1", test)


# JLSN, (8, 8), (1, 100, 100, 3), OB, RGB, 0
# Sample interleaved (ILV 2)
def test(ref, arr, **kwargs):
    assert arr[0, 0].tolist() == [255, 0, 0]
    assert arr[10, 0].tolist() == [255, 130, 130]
    assert arr[20, 0].tolist() == [0, 255, 0]
    assert arr[30, 0].tolist() == [130, 255, 130]
    assert arr[40, 0].tolist() == [0, 0, 255]
    assert arr[50, 0].tolist() == [130, 130, 255]
    assert arr[60, 0].tolist() == [0, 0, 0]
    assert arr[70, 0].tolist() == [65, 65, 65]
    assert arr[80, 0].tolist() == [190, 190, 190]
    assert arr[90, 0].tolist() == [255, 255, 255]


JLSN_08_08_1_0_3F_SAMPLE = PixelReference("SC_rgb_jls_lossy_sample.dcm", "u1", test)


# JLSN, (16, 16), (1, 45, 10, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    assert arr[0, 0] == 65535
    assert arr[5, 0] == 32765
    assert arr[10, 0] == 16385
    assert arr[15, 0] == 4095
    assert arr[20, 0] == 1025
    assert arr[25, 0] == 255
    assert arr[30, 0] == 65
    assert arr[35, 0] == 15
    assert arr[40, 0] == 5


JLSN_16_16_1_0_1F = PixelReference("JPEGLSNearLossless_16.dcm", "u2", test)


PIXEL_REFERENCE[JPEGLSLossless] = [
    JLSL_08_08_3_0_1F_ILV0,
    JLSL_08_08_3_0_1F_ILV1,
    JLSL_08_08_3_0_1F_ILV2,
    JLSL_08_07_1_0_1F,
    JLSL_16_15_1_1_1F,
    JLSL_16_16_1_1_1F,
    JLSL_16_12_1_1_10F,
]
PIXEL_REFERENCE[JPEGLSNearLossless] = [
    JLSN_08_01_1_0_1F,
    JLSN_08_08_3_0_1F_ILV0,
    JLSN_08_08_1_0_3F_LINE,
    JLSN_08_08_1_0_3F_SAMPLE,
    JLSN_16_16_1_0_1F,
]


# JPEG 2000 - ISO/IEC 15444 Standard
# J2KR: JPEG2000Lossless
# J2KI: JPEG2000
# HTJR: HTJ2KLossless
# HTJL: HTJ2KLosslessRPCL
# HTJI: HTJ2K


# tsyntax, (bits allocated, stored), (frames, rows, cols, planes), VR, PI, pixel repr.
# 0: J2KR, (8, 8), (1, 480, 640, 3), OB, YBR_RCT, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("US1_UNCR.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_08_08_3_0_1F_YBR_ICT = PixelReference("US1_J2KR.dcm", "u1", test)


# J2KR, (16, 10), (1, 1760, 1760, 1), OB, MONOCHROME1, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("RG3_UNCR.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_10_1_0_1F_M1 = PixelReference("RG3_J2KR.dcm", "<u2", test)


# J2KR, (16, 12), (1, 1024, 1024, 1), OB, MONOCHROME2,
def test(ref, arr, **kwargs):
    ref = get_testdata_file("MR2_UNCR.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_12_1_0_1F_M2 = PixelReference("MR2_J2KR.dcm", "<u2", test)


# J2KR, (16, 15), (1, 1955, 1841, 1), OB, MONOCHROME1, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("RG1_UNCR.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_15_1_0_1F_M1 = PixelReference("RG1_J2KR.dcm", "<u2", test)


# J2KR, (16, 12), (10, 64, 64, 1), OW, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("emri_small.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_12_1_0_10F_M2 = PixelReference("emri_small_jpeg_2k_lossless.dcm", "<u2", test)


# J2KR, (16, 16), (1, 512, 512, 1), OB, MONOCHROME2, 1
# J2K codestream has 14-bit precision
def test(ref, arr, **kwargs):
    ref = get_testdata_file("693_UNCR.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_14_1_1_1F_M2 = PixelReference("693_J2KR.dcm", "<i2", test)


# J2KR, (16, 16), (1, 64, 64, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    ref = get_testdata_file("MR_small.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KR_16_16_1_1_1F_M2 = PixelReference("MR_small_jp2klossless.dcm", "<i2", test)


# J2KR, (16, 13), (1, 512, 512, 1), OB, MONOCHROME2, 1
# Mismatch between J2K sign and dataset Pixel Representation
def test(ref, arr, **kwargs):
    assert -2000 == arr[0, 0]
    assert [621, 412, 138, -193, -520, -767, -907, -966, -988, -995] == (
        arr[47:57, 279].tolist()
    )
    assert [-377, -121, 141, 383, 633, 910, 1198, 1455, 1638, 1732] == (
        arr[328:338, 106].tolist()
    )


J2KR_16_13_1_1_1F_M2_MISMATCH = PixelReference("J2K_pixelrep_mismatch.dcm", "<i2", test)


# J2KR, (8, 8), (1, 400, 400, 3), OB, YBR_RCT, 0
# Non-conformant pixel data -> JP2 header present
def test(ref, arr, **kwargs):
    # Decoding error with pillow, OK in gdcm, pylibjpeg
    assert tuple(arr[45, 140]) == (223, 32, 32)
    assert tuple(arr[46, 140]) == (255, 0, 0)
    assert tuple(arr[350, 195]) == (128, 128, 128)


J2KR_08_08_3_0_1F_YBR_RCT = PixelReference("GDCMJ2K_TextGBR.dcm", "u1", test)


# J2KI, (8, 8), (1, 100, 100, 3), OB, RGB, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("SC_rgb_gdcm2k_uncompressed.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KI_08_08_3_0_1F_RGB = PixelReference("SC_rgb_gdcm_KY.dcm", "u1", test)


# J2KI, (8, 8), (1, 480, 640, 3), OB, YBR_ICT, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("US1_UNCI.dcm", read=True).pixel_array
    assert np.allclose(arr, ref, atol=1)


J2KI_08_08_3_0_1F_YBR_ICT = PixelReference("US1_J2KI.dcm", "u1", test)


# J2KI, (16, 10), (1, 1760, 1760, 1), OB, MONOCHROME1, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("RG3_UNCI.dcm", read=True).pixel_array
    assert np.allclose(arr, ref, atol=1)


J2KI_16_10_1_0_1F_M1 = PixelReference("RG3_J2KI.dcm", "<u2", test)


# J2KI, (16, 12), (1, 1024, 1024, 1), OB, MONOCHROME2, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("MR2_UNCI.dcm", read=True).pixel_array
    assert np.allclose(arr, ref, atol=1)


J2KI_16_12_1_0_1F_M2 = PixelReference("MR2_J2KI.dcm", "<u2", test)


# J2KI, (16, 15), (1, 1955, 1841, 1), OB, MONOCHROME1, 0
def test(ref, arr, **kwargs):
    ref = get_testdata_file("RG1_UNCI.dcm", read=True).pixel_array
    assert np.allclose(arr, ref, atol=1)


J2KI_16_15_1_0_1F_M1 = PixelReference("RG1_J2KI.dcm", "<u2", test)


# J2KI, (16, 14), (1, 512, 512, 1), OW, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    ref = get_testdata_file("693_UNCI.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KI_16_14_1_1_1F_M2 = PixelReference("693_J2KI.dcm", "<i2", test)


# J2KI, (16, 16), (1, 1024, 256, 1), OB, MONOCHROME2, 1
def test(ref, arr, **kwargs):
    ref = get_testdata_file("JPEG2000_UNC.dcm", read=True).pixel_array
    assert np.array_equal(arr, ref)


J2KI_16_16_1_1_1F_M2 = PixelReference("JPEG2000.dcm", "<i2", test)


# HTJR, (8, 8), (1, 480, 640, 3), OB, RBG, 0
def test(ref, arr, **kwargs):
    assert arr[160, 295:305].tolist() == [
        [90, 38, 1],
        [94, 40, 1],
        [97, 42, 5],
        [173, 122, 59],
        [172, 133, 69],
        [169, 135, 75],
        [168, 136, 79],
        [169, 137, 79],
        [169, 137, 81],
        [169, 136, 79],
    ]
    assert arr[275:285, 635].tolist() == [
        [208, 193, 172],
        [238, 228, 215],
        [235, 229, 216],
        [233, 226, 212],
        [239, 231, 218],
        [238, 232, 219],
        [224, 218, 205],
        [239, 234, 223],
        [246, 241, 232],
        [242, 236, 226],
    ]


HTJR_08_08_1_1_1F_RGB = PixelReference("HTJ2KLossless_08_RGB.dcm", "u1", test)


# HTJI, (8, 8), (1, 480, 640, 3), OB, RBG, 0
def test(ref, arr, **kwargs):
    assert arr[160, 295:305].tolist() == [
        [91, 37, 2],
        [94, 40, 1],
        [97, 42, 5],
        [174, 123, 59],
        [172, 132, 69],
        [169, 134, 74],
        [168, 136, 77],
        [168, 137, 80],
        [168, 136, 80],
        [169, 136, 78],
    ]
    assert arr[275:285, 635].tolist() == [
        [207, 193, 171],
        [238, 229, 215],
        [235, 228, 216],
        [233, 226, 213],
        [238, 231, 218],
        [239, 232, 219],
        [225, 218, 206],
        [240, 234, 223],
        [247, 240, 232],
        [242, 236, 227],
    ]


HTJI_08_08_1_1_1F_RGB = PixelReference("HTJ2K_08_RGB.dcm", "u1", test)


PIXEL_REFERENCE[JPEG2000Lossless] = [
    J2KR_08_08_3_0_1F_YBR_ICT,
    J2KR_16_10_1_0_1F_M1,
    J2KR_16_12_1_0_1F_M2,
    J2KR_16_15_1_0_1F_M1,
    J2KR_16_12_1_0_10F_M2,
    J2KR_16_14_1_1_1F_M2,
    J2KR_16_16_1_1_1F_M2,
    J2KR_16_13_1_1_1F_M2_MISMATCH,
    J2KR_08_08_3_0_1F_YBR_RCT,
]
PIXEL_REFERENCE[JPEG2000] = [
    J2KI_08_08_3_0_1F_RGB,
    J2KI_08_08_3_0_1F_YBR_ICT,
    J2KI_16_10_1_0_1F_M1,
    J2KI_16_12_1_0_1F_M2,
    J2KI_16_15_1_0_1F_M1,
    J2KI_16_14_1_1_1F_M2,
    J2KI_16_16_1_1_1F_M2,
]
PIXEL_REFERENCE[HTJ2KLossless] = [HTJR_08_08_1_1_1F_RGB]
PIXEL_REFERENCE[HTJ2KLosslessRPCL] = []
PIXEL_REFERENCE[HTJ2K] = [HTJI_08_08_1_1_1F_RGB]
