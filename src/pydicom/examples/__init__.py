"""Module to support importing the datasets used by the documentation."""

from typing import Any, cast

from pydicom.data import get_testdata_file
from pydicom.filereader import dcmread


_DATASETS: dict[str, str] = {
    "ct": cast(str, get_testdata_file("CT_small.dcm")),
    "dicomdir": cast(str, get_testdata_file("DICOMDIR")),
    "jpeg2k": cast(str, get_testdata_file("US1_J2KR.dcm")),
    "mr": cast(str, get_testdata_file("MR_small.dcm")),
    "no_meta": cast(str, get_testdata_file("no_meta.dcm")),
    "overlay": cast(str, get_testdata_file("MR-SIEMENS-DICOM-WithOverlays.dcm")),
    "palette_color": cast(str, get_testdata_file("OBXXXX1A.dcm")),
    "rgb_color": cast(str, get_testdata_file("US1_UNCR.dcm")),
    "rt_dose": cast(str, get_testdata_file("rtdose.dcm")),
    "rt_plan": cast(str, get_testdata_file("rtplan.dcm")),
    "rt_ss": cast(str, get_testdata_file("rtstruct.dcm")),
    "waveform": cast(str, get_testdata_file("waveform_ecg.dcm")),
    "ybr_color": cast(str, get_testdata_file("color3d_jpeg_baseline.dcm")),
}


def __getattr__(name: str) -> Any:
    """Return module level attributes."""
    if name in _DATASETS:
        return dcmread(_DATASETS[name], force=True)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
