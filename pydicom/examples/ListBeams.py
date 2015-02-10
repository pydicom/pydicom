# ListBeams.py
"""Given an RTPLAN DICOM file, list basic info for the beams in it
"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from __future__ import print_function
import pydicom

usage = """python ListBeams.py rtplan.dcm"""


def ListBeams(plan_dataset):
    """Return a string summarizing the RTPLAN beam information in the dataset"""
    lines = ["{name:^13s} {num:^8s} {gantry:^8s} {ssd:^11s}".format(
        name="Beam name", num="Number", gantry="Gantry", ssd="SSD (cm)")]
    for beam in plan_dataset.BeamSequence:
        cp0 = beam.ControlPointSequence[0]
        SSD = float(cp0.SourcetoSurfaceDistance / 10)
        lines.append("{b.BeamName:^13s} {b.BeamNumber:8d} "
                     "{gantry:8.1f} {ssd:8.1f}".format(b=beam,
                                                       gantry=cp0.GantryAngle, ssd=SSD))
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(usage)
        sys.exit(-1)

    rtplan = pydicom.read_file(sys.argv[1])
    print(ListBeams(rtplan))
