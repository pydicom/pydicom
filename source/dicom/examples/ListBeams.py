# ListBeams.py
"""Given an RTPLAN DICOM file, list basic info for the beams in it
"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import dicom

usage = """python ListBeams.py rtplan.dcm"""

def ListBeams(plan_dataset):
    """Return a string summarizing the RTPLAN beam information in the dataset"""
    lines = ["%13s %8s %8s %8s" % ("Beam name", "Number", "Gantry", "SSD (cm)")]
    for beam in plan_dataset.BeamSequence:
        cp0 = beam.ControlPointSequence[0]
        SSD = float(cp0.SourcetoSurfaceDistance / 10)
        lines.append("%13s %8s %8.1f %8.1f" % (beam.BeamName, str(beam.BeamNumber),
                                      cp0.GantryAngle, SSD))
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print usage
        sys.exit(-1)

    rtplan = dicom.read_file(sys.argv[1])
    print ListBeams(rtplan)