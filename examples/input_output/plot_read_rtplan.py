"""
======================================
Read RTPLAN DICOM and list information
======================================

Given an RTPLAN DICOM file, list basic info for the beams in it.

"""

# authors : Darcy Mason
#           Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

import pydicom
from pydicom.data import get_testdata_file

print(__doc__)


def list_beams(ds: pydicom.Dataset) -> str:
    """Summarizes the RTPLAN beam information in the dataset."""
    lines = [f"{'Beam name':^13s} {'Number':^8s} {'Gantry':^8s} {'SSD (cm)':^11s}"]
    for beam in ds.BeamSequence:
        cp0 = beam.ControlPointSequence[0]
        ssd = float(cp0.SourceToSurfaceDistance / 10)
        lines.append(
            f"{beam.BeamName:^13s} {beam.BeamNumber:8d} {cp0.GantryAngle:8.1f} {ssd:8.1f}"
        )
    return "\n".join(lines)


path = get_testdata_file("rtplan.dcm")
ds = pydicom.dcmread(path)
print(list_beams(ds))
