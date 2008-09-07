# test_filereader.py
"""unittest tests for dicom.filereader module"""

import os.path
import sys
import unittest
from dicom.filereader import ReadFile
from dicom.tag import Tag

testdir = os.path.dirname(sys.argv[0])

rtplan_name = os.path.join(testdir, "rtplan.dcm")
rtdose_name = os.path.join(testdir, "rtdose.dcm")
ct_name     = os.path.join(testdir, "CT1_UNC.dcm")
mr_name     = os.path.join(testdir, "MR1_UNC.dcm")
us_name     = os.path.join(testdir, "US1_UNC.dcm")


def isClose(a, b, epsilon=0.000001): # compare within some tolerance, to avoid machine roundoff differences
    try:
        a.append  # see if is a list
    except: # (is not)
        return abs(a-b) < epsilon
    else:
        if len(a) != len(b): return 0
        for ai, bi in zip(a, b):
            if abs(ai-bi) > epsilon: return 0
        return 1

class ReaderTests(unittest.TestCase):
    def testRTPlan(self):
        """Returns correct values for sample attributes in test RT Plan file"""
        plan = ReadFile(rtplan_name)
        beam = plan.Beams[0]
        cp0, cp1 = beam.ControlPoints # if not two controlpoints, then this would raise exception
        
        self.assertEqual(beam.TreatmentMachineName, "unit001", "Incorrect unit name")
        self.assertEqual(beam.TreatmentMachineName, beam[0x300a, 0x00b2].value,
                "beam TreatmentMachineName does not match the value accessed by tag number")
        
        cumDoseRef = cp1.ReferencedDoseReferences[0].CumulativeDoseReferenceCoefficient
        self.assert_(isClose(cumDoseRef, 0.9990268),
                "Cum Dose Ref Coeff not the expected value (CP1, Ref'd Dose Ref")
        JawX = cp0.BLDPositions[0].LeafJawPositions
        self.assert_(isClose(JawX[0], -100.0) and isClose(JawX[1], 100.0),
                "X jaws not as expected (control point 0)")
    def testRTDose(self):
        """Returns correct values for sample attributes in test RT Dose file"""
        dose = ReadFile(rtdose_name)
        self.assertEqual(dose.FrameIncrementPointer, Tag((0x3004, 0x000c)),
                "Frame Increment Pointer not the expected value")
        self.assertEqual(dose.FrameIncrementPointer, dose[0x28, 9].value,
                "FrameIncrementPointer does not match the value accessed by tag number")
        
        # try a value that is nested the deepest (so deep I break it into two steps!)
        fract = dose.ReferencedRTPlans[0].ReferencedFractionGroups[0]
        beamnum = fract.ReferencedBeams[0].ReferencedBeamNumber
        self.assertEqual(beamnum, 1, "Beam number not the expected value")
    def testCT(self):
        """Returns correct values for sample attributes in test CT file"""
        ct = ReadFile(ct_name)
        self.assertEqual(ct.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                "ImplementationClassUID not the expected value")
        self.assertEqual(ct.ImplementationClassUID, ct[0x2, 0x12].value,
                "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 512, "Rows not 512")
        self.assertEqual(ct.Columns, 512, "Columns not 512")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 512*512*2, "Pixel data not expected length")
    def testMR(self):
        """Returns correct values for sample attributes in test MR file"""
        mr = ReadFile(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        self.assertEqual(mr.PatientsName, 'CompressedSamples^MR1', "Wrong patient name")
        self.assertEqual(mr.PatientsName, mr[0x10,0x10].value,
                "Name does not match value found when accessed by tag number")
        self.assert_(isClose(mr.PixelSpacing, [0.3125, 0.3125]), "Wrong pixel spacing")
    def testUS(self):
        """Returns correct values for sample attributes in test US file"""
        us = ReadFile(us_name)
        self.assertEqual(us.preamble[:3], "II*", "Preamble doesn't begin with 'II*' as expected")
        self.assertEqual(us.NumberofStages, 1, "Number of stages not 1")
        self.assert_(isClose(us.PatientsWeight, 0.0), "Wrong patient weight")
        
if __name__ == "__main__":
    unittest.main()