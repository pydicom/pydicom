# test_filereader.py
"""unittest tests for dicom.filereader module"""
# Copyright 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details

import sys
import os
import os.path
import unittest
from dicom.filereader import ReadFile
from dicom.tag import Tag

rtplan_name = "rtplan.dcm"
rtdose_name = "rtdose.dcm"
ct_name     = "CT_small.dcm"
mr_name     = "MR_small.dcm"
jpeg2000_name   = "JPEG2000.dcm"
jpeg_lossy_name   = "JPEG-lossy.dcm"
jpeg_lossless_name   = "JPEG-LL.dcm"
deflate_name = "image_dfl.dcm"
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()

def isClose(a, b, epsilon=0.000001): # compare within some tolerance, to avoid machine roundoff differences
    try:
        a.append  # see if is a list
    except: # (is not)
        return abs(a-b) < epsilon
    else:
        if len(a) != len(b): 
            return False
        for ai, bi in zip(a, b):
            if abs(ai-bi) > epsilon: 
                return False
        return True

class ReaderTests(unittest.TestCase):
    def testRTPlan(self):
        """Returns correct values for sample data elements in test RT Plan file"""
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
        """Returns correct values for sample data elements in test RT Dose file"""
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
        """Returns correct values for sample data elements in test CT file"""
        ct = ReadFile(ct_name)
        self.assertEqual(ct.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                "ImplementationClassUID not the expected value")
        self.assertEqual(ct.ImplementationClassUID, ct[0x2, 0x12].value,
                "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128*128*2, "Pixel data not expected length")
    def testMR(self):
        """Returns correct values for sample data elements in test MR file"""
        mr = ReadFile(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        self.assertEqual(mr.PatientsName, 'CompressedSamples^MR1', "Wrong patient name")
        self.assertEqual(mr.PatientsName, mr[0x10,0x10].value,
                "Name does not match value found when accessed by tag number")
        self.assert_(isClose(mr.PixelSpacing, [0.3125, 0.3125]), "Wrong pixel spacing")
    def testDeflate(self):
        """Returns correct values for sample data elements in test compressed (zlib deflate) file"""
        # Everything after group 2 is compressed. If we can read anything else, the decompression must have been ok.
        ds = ReadFile(deflate_name)
        got = ds.ConversionType
        expected = "WSD"
        self.assertEqual(got, expected, "Attempted to read deflated file data element Conversion Type, expected '%s', got '%s'" % (expected, got))

class JPEG2000Tests(unittest.TestCase):
    def setUp(self):
        self.jpeg = ReadFile(jpeg2000_name)
    def testJPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements..........."""
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)] # XX also tests multiple-valued AT data element
        got = self.jpeg.FrameIncrementPointer
        self.assertEqual(got, expected, "JPEG2000 file, Frame Increment Pointer: expected %s, got %s" % (expected, got))

        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG200 file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEG2000PixelArray(self):
        """JPEG2000: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)
    
class JPEGlossyTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = ReadFile(jpeg_lossy_name)
    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements........."""
        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG-lossy file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)
        
class JPEGlosslessTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = ReadFile(jpeg_lossless_name)
    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements..........."""
        got = self.jpeg.SourceImages[0].PurposeofReferenceCodes[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(got, expected, "JPEG-lossless file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)        

if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need to switch there
    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir("../testfiles")
    unittest.main()
    os.chdir(save_dir)