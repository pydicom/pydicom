"""Module to support importing the datasets used by the documentation."""

from typing import Any, cast
from pathlib import Path

from pydicom.data import get_testdata_file
from pydicom.filereader import dcmread


# All datasets included here must be available in the package itself
#   NOT via the pydicom-data download method
_DATASETS: dict[str, str] = {
    "ct": cast(str, get_testdata_file("CT_small.dcm", download=False)),
    "dicomdir": cast(str, get_testdata_file("DICOMDIR", download=False)),
    "jpeg2k": cast(str, get_testdata_file("examples_jpeg2k.dcm", download=False)),
    "mr": cast(str, get_testdata_file("MR_small.dcm", download=False)),
    "no_meta": cast(str, get_testdata_file("no_meta.dcm", download=False)),
    "overlay": cast(str, get_testdata_file("examples_overlay.dcm", download=False)),
    "palette_color": cast(str, get_testdata_file("examples_palette.dcm", download=False)),
    "rgb_color": cast(str, get_testdata_file("examples_rgb_color.dcm", download=False)),
    "rt_dose": cast(str, get_testdata_file("rtdose.dcm", download=False)),
    "rt_plan": cast(str, get_testdata_file("rtplan.dcm", download=False)),
    "rt_ss": cast(str, get_testdata_file("rtstruct.dcm", download=False)),
    "waveform": cast(str, get_testdata_file("waveform_ecg.dcm", download=False)),
    "ybr_color": cast(str, get_testdata_file("examples_ybr_color.dcm", download=False)),
}


def _get_path(name: str) -> Path:
    """Return the path to the example dataset with the attribute name `name` as
    :class:`pathlib.Path`.
    """
    if name in _DATASETS:
        return Path(_DATASETS[name])

    raise ValueError(f"No example dataset exists with the name '{name}'")


def __getattr__(name: str) -> Any:
    """Return module level attributes."""
    if name in _DATASETS:
        return dcmread(_DATASETS[name], force=True)

    if name == "get_path":
        return _get_path

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
