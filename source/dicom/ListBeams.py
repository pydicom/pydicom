# ListBeams.py
"""Given a plan file, list basic info for the beams in it
"""

usage = """Expected a single dicom filename. E.g.:
   python ListBeams.py rtplan.dcm
   """


def ListBeams(rtplan_filename):
   import dicom
   plan = dicom.ReadFile(rtplan_filename)
   print "%13s %8s %8s %8s" % ("Beam name", "Number", "Gantry", "SSD (cm)")
   for beam in plan.Beams:
      name = beam.BeamName
      num = beam.BeamNumber
      cp = beam.ControlPoints[0]
      g = float(cp.GantryAngle)
      SSD = float(cp.SourcetoSurfaceDistance / 10.0)
      print "%13s %8s %8.1f %8.1f" % (name, str(num), g, SSD)


if __name__ == "__main__":
   import sys
   if len(sys.argv) != 2:
      print usage
      print
      print
      sys.exit(-1)
   ListBeams(sys.argv[1])
   print
   print "Done."