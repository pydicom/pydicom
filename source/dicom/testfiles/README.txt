Test Files used for testing pydicom 
-----------------------------------
I obtained images to test the pydicom code, and revised them as follow:
  * images were often downsized to keep the total file size quite small (typically <50K-ish). I wanted unittests for the code where I could run a number of tests quickly, and with files I could include in the source (and binary) distributions without bloating them too much
  * In some cases, the original files have been binary edited to replace anything that looks like a real patient name
  
I believe there is no restriction on using any of these files in this manner.

CT_small.dcm      
  * CT image, Explicit VR, LittleEndian     
  * Downsized to 128x128 from 'CT1_UNC', ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04/

MR_small.dcm
  * MR image, Explicit VR, LittleEndian     
  * Downsized to 64x64 from 'MR1_UNC', ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04/

JPEG2000.dcm      
  * JPEG 2000 small image
  * to test JPEG transfer syntax, eventually JPEG decompression
  * Edited 'NM1_J2KI' from ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04
  
image_dfl.dcm       
  * Compressed (using "deflate" zlib compression) after FileMeta
  * 'image_dfl' from http://www.dclunie.com/images/compressed/
  
ExplVR_BigEnd.dcm 
  * Big Endian test image
  * Also is Samples Per Pixel of 3 (RGB)
  * Downsized to 60x80 from 'US-RGB-8-epicard' at http://www.barre.nom.fr/medical/samples/ 
  
JPEG-LL.dcm
  * NM1_JPLL from ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04/
  * Transfer Syntax 1.2.840.10008.1.2.4.70:  JPEG Lossless Default Process 14 [Selection Value 1]
  
JPEG-lossy.dcm
  * NM1_JPLY from ftp://medical.nema.org/MEDICAL/Dicom/DataSets/WG04/
  * 1.2.840.10008.1.2.4.51 Default Transfer Syntax for Lossy JPEG 12-bit

Created by a commercial radiotherapy treatment planning system and modified:
rtplan.dcm       Implicit VR, Little Endian
rtdose.dcm       Implicit VR, Little Endian


chr*.dcm
  * Character set files for testing (0008,0005) Specific Character Set
  * from http://www.dclunie.com/images/charset/SCS*
  * downsized to 32x32 since pixel data is irrelevant for these (test pattern only)

test_SR.dcm
  * from ftp://ftp.dcmtk.org/pub/dicom/offis/software/dscope/dscope360/support/srdoc103.zip, file "test.dcm"
  * Structured Reporting example, many levels of nesting

priv_SQ.dcm
  * a file with an undefined length SQ item in a private tag.
  * minimal data elements kept from example files in issues 91, 97, 98

zipMR.gz
  * a gzipped version of MR_small.dcm
  * used for checking that deferred read reopens as zip again (issue 103)

