
from pathlib import Path
from typing import Tuple, Dict, TYPE_CHECKING, Optional, List, Any

import pytest

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.data import get_testdata_file
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLosslessP14,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

class TestDataset:
    def __init__(
        self,
        path: Path,
        dtype: str,
        unc_path: Optional[Path] = None,
        samples: Optional[List[Any]] = None,
    ) -> None:
        self.path = Path(get_testdata_file(path)).resolve(strict=True)
        self.dtype = dtype

        self.unc_path = (
            Path(get_testdata_file(unc_path)).resolve(strict=True)
        ) if unc_path else None

        self.sample = None

        self._ds = None

    def ds(self, force: bool = False) -> "Dataset":
        return dcmread(self.path, force=force)

    @property
    def info(self):
        if self._ds is None:
            self._ds = dcmread(self.path, force=True)

        print(self.path)
        try:
            print(ds.file_meta.TransferSyntaxUID)
        except Exception:
            print("Transfer Syntax UID not available")

        for elem in ds.group_dataset(0x0028):
            print(elem)

    @property
    def properties(self) -> Dict[str, Any]:
        if self._ds is None:
            self._ds = dcmread(self.path, force=True)

        keywords = [
            "Rows",
            "Columns",
            "SamplesPerPixel",
            "PlanarConfiguration",
            "NumberOfFrames",
            "PixelRepresentation",
            "BitsAllocated",
            "BitsStored",
            "PhotometricInterpretation",
        ]
        return {k: self._ds.get(kw) for kw in keywords}

    @property
    def shape(self) -> Tuple[int, ...]:
        p = self.properties
        r = p["Rows"]
        c = p["Columns"]
        f = int(p["NumberOfFrames"] or 1)
        s = p["SamplesPerPixel"]

        shape = [r, c]
        if f > 1:
            shape.insert(0, f)
        if s > 1:
            shape.append(s)

        return shape

    def sample_equal(self, arr: "numpy.ndarray") -> bool:
        if not self.sample:
            raise ValueError(
                f"The test dataset @ {self.path} has no sample pixel data set"
            )

        for (indices, values) in self.sample:
            if not (arr[indices] == values).all():
                return False

        return True

    def uncompressed_equal(self, arr: "numpy.ndarray") -> bool:
        if not self.unc_path:
            raise ValueError(
                f"The test dataset @ {self.path} has no matching uncompressed "
                "dataset set"
            )

        unc = dcmread(self.unc_path, force=True)
        return np.array_equal(arr, unc.pixel_array)


# Implicit VR Little Endian
IMPL_U2_16_1S_1F = TestDataset(
    path="MR_small_implicit.dcm",
    dtype="u2",
)
IMPL_U4_32_1S_1F = TestDataset(
    path="rtdose_1frame.dcm",
    dtype="u4",
)
IMPL_U4_32_1S_15F = TestDataset(
    path="rtdose.dcm",
    dtype="u4",
)

REFERENCE_IMPL = [
    IMPL_U2_16_1S_1F,
    IMPL_U4_32_1S_1F,
    IMPL_U4_32_1S_15F,
]

# Explicit VR Little Endian
EXPL_U1_01_1S_1F = TestDataset(
    path="liver_1frame.dcm",
    dtype="u1",
)
EXPL_U1_01_1S_3F = TestDataset(
    path="liver.dcm",
    dtype="u1",
)
EXPL_U1_08_1S_1F = TestDataset(
    path="OBXXXX1A.dcm",
    dtype="u1",
)
EXPL_U1_08_1S_2F = TestDataset(
    path="OBXXXX1A_2frame.dcm",
    dtype="u1",
)
EXPL_U1_08_3S_1F = TestDataset(
    path="SC_rgb.dcm",
    dtype="u1",
)
EXPL_U1_08_3S_1F_ODD = TestDataset(
    path="SC_rgb_small_odd.dcm",
    dtype="u1",
)
EXPL_U1_08_3S_1F_YBR422 = TestDataset(
    path="SC_ybr_full_422_uncompressed.dcm",
    dtype="u1",
)
EXPL_U1_08_3S_1F_YBR = TestDataset(
    path="SC_ybr_full_uncompressed.dcm",
    dtype="u1",
)
EXPL_U1_08_1S_2F = TestDataset(
    path="SC_rgb_2frame.dcm",
    dtype="u1",
)
EXPL_I2_16_1S_1F = TestDataset(
    path="MR_small.dcm",
    dtype="i2",
)
EXPL_U2_16_1S_1F_PAD = TestDataset(
    path="MR_small_padded.dcm",
    dtype="u2",
)
EXPL_U2_16_1S_10F = TestDataset(
    path="emri_small.dcm",
    dtype="u2",
)
EXPL_U2_16_3S_1F = TestDataset(
    path="SC_rgb_16bit.dcm",
    dtype="u2",
)
EXPL_U2_16_3S_2F = TestDataset(
    path="SC_rgb_16bit_2frame.dcm",
    dtype="u2",
)
EXPL_U4_32_3S_1F = TestDataset(
    path="SC_rgb_32bit.dcm",
    dtype="u4",
)
EXPL_U4_32_3S_2F = TestDataset(
    path="SC_rgb_32bit_2frame.dcm",
    dtype="u4",
)

REFERENCE_EXPL = [
    EXPL_U1_08_1S_1F,
    EXPL_U1_08_1S_3F,
    EXPL_U1_08_1S_1F,
    EXPL_U1_08_1S_2F,
    EXPL_U1_08_3S_1F,
    EXPL_U1_08_3S_1F_ODD,
    EXPL_U1_08_3S_1F_YBR422,
    EXPL_U1_08_3S_1F_YBR,
    EXPL_U1_08_1S_2F,
    EXPL_I2_16_1S_1F,
    EXPL_U2_16_1S_1F_PAD,
    EXPL_U2_16_1S_10F,
    EXPL_U2_16_3S_1F,
    EXPL_U2_16_3S_2F,
    EXPL_U4_32_3S_1F,
    EXPL_U4_32_3S_2F,
]

# Explicit VR Big Endian
EXPB_U1_01_1S_1F = TestDataset(
    path="liver_expb_1frame.dcm",
    dtype="u1",
)
EXPB_U1_01_1S_3F = TestDataset(
    path="liver_expb.dcm",
    dtype="u1",
)
EXPB_U1_08_1S_1F = TestDataset(
    path="OBXXXX1A_expb.dcm",
    dtype="u1",
)
EXPB_U1_08_1S_2F = TestDataset(
    path="OBXXXX1A_expb_2frame.dcm",
    dtype="u1",
)
EXPB_U1_08_3S_1F = TestDataset(
    path="SC_rgb_expb.dcm",
    dtype="u1",
)
EXPB_U1_08_3S_2F = TestDataset(
    path="SC_rgb_expb_2frame.dcm",
    dtype="u1",
)
EXPB_U2_16_1S_1F = TestDataset(
    path="MR_small_expb.dcm",
    dtype="u2",
)
EXPB_U2_16_1S_10F = TestDataset(
    path="emri_small_big_endian.dcm",
    dtype="u2",
)
EXPB_U2_16_3S_1F = TestDataset(
    path="SC_rgb_expb_16bit.dcm",
    dtype="u2",
)
EXPB_U2_16_3S_2F = TestDataset(
    path="SC_rgb_expb_16bit_2frame.dcm",
    dtype="u2",
)
EXPB_U4_32_1S_1F = TestDataset(
    path="rtdose_expb_1frame.dcm",
    dtype="u4",
)
EXPB_U4_32_1S_15F = TestDataset(
    path="rtdose_expb.dcm",
    dtype="u4",
)
EXPB_U4_32_3S_1F = TestDataset(
    path="SC_rgb_expb_32bit.dcm",
    dtype="u4",
)
EXPB_U4_32_3S_2F = TestDataset(
    path="SC_rgb_expb_32bit_2frame.dcm",
    dtype="u4",
)

REFERENCE_EXPB = [
    EXPB_U1_01_1S_1F,
    EXPB_U1_01_1S_3F,
    EXPB_U1_08_1S_1F,
    EXPB_U1_08_1S_2F,
    EXPB_U1_08_3S_1F,
    EXPB_U1_08_3S_2F,
    EXPB_U2_16_1S_1F,
    EXPB_U2_16_1S_10F,
    EXPB_U2_16_3S_1F,
    EXPB_U2_16_3S_2F,
    EXPB_U4_32_1S_1F,
    EXPB_U4_32_1S_15F,
    EXPB_U4_32_3S_1F,
    EXPB_U4_32_3S_2F,
]

# Deflated Explicit VR Little Endian
DEFL_U1_08_1S_1F = TestDataset(
    path="image_dfl.dcm",
    dtype="u1",
)

REFERENCE_DEFL = [DEFL_U1_08_1S_1F]

# RLE Lossless
RLEL_U1_08_1S_1F = TestDataset(
    path="OBXXXX1A_rle.dcm",
    dtype="u1",
    unc_path="OBXXXX1A.dcm",
    sample=[
        ((300, slice(491, 494)), (1, -10, 1)),
    ],
)
RLEL_U1_08_1S_2F = TestDataset(
    path="OBXXXX1A_RLEL_2frame.dcm",
    dtype="u1",
    unc_path="OBXXXX1A_2frame.dcm",
    sample=[
        ((0, 300, slice(491, 494)), (1, -10, 1)),
    ],
)
RLEL_U1_08_3S_1F = TestDataset(
    path="SC_rgb_rle.dcm",
    dtype="u1",
    unc_path="SC_rgb.dcm",
)
RLEL_U1_08_3S_2F = TestDataset(
    path="SC_rgb_RLEL_2frame.dcm",
    dtype="u1",
    unc_path="SC_rgb_2frame.dcm",
)
RLEL_I2_16_1S_1F = TestDataset(
    path="MR_small_RLE.dcm",
    dtype="i2",
    unc_path="MR_small.dcm",
)
RLEL_U2_16_1S_10F = TestDataset(
    path="emri_small_RLE.dcm",
    dtype="u2",
    unc_path="emri_small.dcm",
)
RLEL_U2_16_3S_1F = TestDataset(
    path="SC_rgb_RLEL_16bit.dcm",
    dtype="u2",
    unc_path="SC_rgb_16bit.dcm",
)
RLEL_U2_16_3S_10F = TestDataset(
    path="SC_rgb_RLEL_16bit_2frame.dcm",
    dtype="u2",
    unc_path="SC_rgb_16bit_2frame.dcm",
)
RLEL_U4_32_1S_1F = TestDataset(
    path="rtdose_RLEL_1frame.dcm",
    dtype="u4",
    unc_path="rtdose_1frame.dcm",
)
RLEL_U4_32_1S_15F = TestDataset(
    path="rtdose_rle.dcm",
    dtype="u4",
    unc_path="rtdose.dcm",
)
RLEL_U4_32_3S_1F = TestDataset(
    path="SC_rgb_RLEL_32bit.dcm",
    dtype="u4",
    unc_path="SC_rgb_32bit.dcm",
)
RLEL_U4_32_3S_2F = TestDataset(
    path="SC_rgb_RLEL_32bit_2frame.dcm",
    dtype="u4",
    unc_path="SC_rgb_32bit_2frame.dcm",
)

REFERENCE_RLEL = [
    RLEL_U1_08_1S_1F,
    RLEL_U1_08_1S_2F,
    RLEL_U1_08_3S_1F,
    RLEL_U1_08_3S_2F,
    RLEL_U2_16_1S_1F,
    RLEL_U2_16_1S_10F,
    RLEL_U2_16_3S_1F,
    RLEL_U2_16_3S_10F,
    RLEL_U4_32_1S_1F,
    RLEL_U4_32_1S_15F,
    RLEL_U4_32_3S_1F,
    RLEL_U4_32_3S_2F,
]

# JPEG Baseline
JBSL_U1_01_3S_1F_YBR_FULL = TestDataset(
    path="SC_rgb_small_odd_jpeg.dcm",
    dtype="u1",
)
JBSL_U1_01_3S_1F_YBR_FULL_422 = TestDataset(
    path="color3d_jpeg_baseline.dcm",
    dtype="u1",
)
# Different subsampling 411, 422, 444
JBSL_U1_01_3S_1F_YBR_FULL_422_411 = TestDataset(
    path="SC_rgb_dcmtk_+eb+cy+np.dcm",
    dtype="u1",
)
JBSL_U1_01_3S_1F_YBR_FULL_422_422 = TestDataset(
    path="SC_rgb_dcmtk_+eb+cy+s2.dcm",
    dtype="u1",
)
JBSL_U1_01_3S_1F_YBR_FULL_411 = TestDataset(
    path="SC_rgb_dcmtk_+eb+cy+n1.dcm",
    dtype="u1",
    comment="411 sub-sampling",
)
JBSL_U1_01_3S_1F_YBR_FULL_422 = TestDataset(
    path="SC_rgb_dcmtk_+eb+cy+n2.dcm",
    dtype="u1",
    comment="422 sub-sampling",
)
JBSL_U1_01_3S_1F_YBR_FULL_444 = TestDataset(
    path="SC_rgb_dcmtk_+eb+cy+s4.dcm",
    dtype="u1",
    comment="444 sub-sampling",
)
JBSL_U1_01_3S_1F_RGB = TestDataset(
    path="SC_jpeg_no_color_transform.dcm",
    dtype="u1",
    comment="RGB source, no JPEG color space flags",
)
JBSL_U1_01_3S_1F_RGB_APP14 = TestDataset(
    path="SC_jpeg_no_color_transform_2.dcm",
    dtype="u1",
    comment="RGB source, JPEG APP14 marker",
)

REFERENCE_JBSL  = [
    JBSL_U1_01_3S_1F_YBR_FULL,
    JBSL_U1_01_3S_1F_YBR_FULL_422,
    JBSL_U1_01_3S_1F_YBR_FULL_422_411,
    JBSL_U1_01_3S_1F_YBR_FULL_422_422,
    JBSL_U1_01_3S_1F_YBR_FULL_411,
    JBSL_U1_01_3S_1F_YBR_FULL_422,
    JBSL_U1_01_3S_1F_YBR_FULL_444,
    JBSL_U1_01_3S_1F_RGB,
    JBSL_U1_01_3S_1F_RGB_APP14,
]

# JPEG Extended
JEXT_U2_12_1S_1F_BAD = TestDataset(
    path="JPEG-lossy.dcm",
    dtype="u2",
    comment="Bad JPEG codestream",
)
JEXT_U2_12_1S_1F = TestDataset(
    path="JPGExtended.dcm",
    dtype="u2",
    comment="Fixed version of JPEG-lossy.dcm",
)

REFERENCE_JEXT = [JEXT_U2_12_1S_1F_BAD, JEXT_U2_12_1S_1F]

# JPEG Lossless (Process 14)
REFERENCE_JP14 = []

# JPEG Lossless (Process 14, Selection Value 1)
JP14_U1_08_1S_1F = TestDataset(
    path="JPGLosslessP14SV1_1s_1f_8b.dcm",
    dtype="u1",
)
JP14_U2_16_1S_1F = TestDataset(
    path="JPEG-LL.dcm",
    dtype="u2",
)

REFERENCE_JSV1 = [JP14_U1_08_1S_1F, JP14_U2_16_1S_1F]

# JPEG LS Lossless
JLSR_I2_16_1S_1F = TestDataset(
    path="MR_small_jpeg_ls_lossless.dcm",
    dtype="i2",
)

REFERENCE_JLSR = [JLSR_I2_16_1S_1F]

# JPEG LS Near Lossless
REFERENCE_JLSI = []

# JPEG 2000
J2KI_U1_08_3S_1F_RGB = TestDataset(
    path="SC_rgb_gdcm_KY.dcm",
    dtype="u1",
)
J2KI_U1_08_3S_1F = TestDataset(
    path="US1_J2KI.dcm",
    dtype="u1",
)
J2KI_U2_10_1S_1F = TestDataset(
    path="RG3_J2KI.dcm",
    dtype="u2",
)
J2KI_U2_12_1S_1F = TestDataset(
    path="MR2_J2KI.dcm",
    dtype="u2",
)
J2KI_U2_15_1S_1F = TestDataset(
    path="RG1_J2KI.dcm",
    dtype="u2",
)
J2KI_I2_14_1S_1F = TestDataset(
    path="693_J2KI.dcm",
    dtype="i2",
)
J2KI_I2_16_1S_1F = TestDataset(
    path="JPEG2000.dcm",
    dtype="i2",
)

REFERENCE_J2KI = [
    J2KI_U1_08_3S_1F_RGB,
    J2KI_U1_08_3S_1F,
    J2KI_U2_10_1S_1F,
    J2KI_U2_12_1S_1F,
    J2KI_U2_15_1S_1F,
    J2KI_I2_14_1S_1F,
    J2KI_I2_16_1S_1F,
]

# JPEG 2000 Lossless
J2KR_U1_08_1S_1F_JP2 = TestDataset(
    path="GDCMJ2K_TextGBR.dcm",
    dtype="u1",
    comment="JP2 header present",
)
J2KR_U1_08_3S_1F = TestDataset(
    path="US1_J2KR.dcm",
    dtype="u1",
)
J2KR_U2_10_1S_1F = TestDataset(
    path="RG3_J2KR.dcm",
    dtype="u2",
)
J2KR_U2_12_1S_1F = TestDataset(
    path="MR2_J2KR.dcm",
    dtype="u2",
)
J2KR_U2_15_1S_1F = TestDataset(
    path="RG1_J2KR.dcm",
    dtype="u2",
)
J2KR_U2_16_1S_1F = TestDataset(
    path="emri_small_jpeg_2k_lossless.dcm",
    dtype="u2",
)
J2KR_I2_14_1S_1F = TestDataset(
    path="693_J2KR.dcm",
    dtype="i2",
)
J2KR_I2_16_1S_1F = TestDataset(
    path="MR_small_jp2klossless.dcm",
    dtype="i2",
)
J2KR_I2_13_1S_1F = TestDataset(
    path="J2K_pixelrep_mismatch.dcm",
    dtype="i2",
)

REFERENCE_J2KR = [
    J2KR_U1_08_1S_1F_JP2,
    J2KR_U1_08_3S_1F,
    J2KR_U2_10_1S_1F,
    J2KR_U2_12_1S_1F,
    J2KR_U2_15_1S_1F,
    J2KR_U2_16_1S_1F,
    J2KR_I2_14_1S_1F,
    J2KR_I2_16_1S_1F,
    J2KR_I2_13_1S_1F,
]


REFERENCE_DATA = {
    ImplicitVRLittleEndian: REFERENCE_IMPL,
    ExplicitVRLittleEndian: REFERENCE_EXPL,
    DeflatedExplicitVRLittleEndian: REFERENCE_DEFL,
    ExplicitVRBigEndian: REFERENCE_EXPB,
    JPEGBaseline8Bit: REFERENCE_JBSL,
    JPEGExtended12Bit: REFERENCE_JEXT,
    JPEGLosslessP14: REFERENCE_JP14,
    JPEGLosslessSV1: REFERENCE_JSV1,
    JPEGLSLossless: REFERENCE_JLSL,
    JPEGLSNearLossless: REFERENCE_JLSN,
    JPEG2000: REFERENCE_J2KI,
    JPEG2000Lossless: REFERENCE_J2KR,
    RLELossless: REFERENCE_RLEL,
}
