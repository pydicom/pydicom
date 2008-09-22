README for test files:
April 2004

Some of the test code uses publicly available dicom files. The origin of these is:

From ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04/compsamples_refanddir.tar.bz2,
CT1_UNC.dcm    Explicit VR, Little Endian
MR1_UNC.dcm    Explicit VR, Little Endian
US1_UNC.dcm    Explicit VR, Little Endian

Created by a commercial radiotherapy treatment planning system and modified:
plan.dcm       Implicit VR, Little Endian
dose.dcm       Implicit VR, Little Endian

For testing deflated transfer syntax, from http://www.dclunie.com/images/compressed/:
report
report_defl

I couldn't find any public BigEndian files, so BigEndian is untested at present.

If you find files which pydicom cannot read properly, please send them so I can add them
to the test suite. (Please send only files which can be released publicly).

