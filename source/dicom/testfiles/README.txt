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

== DICOMDIR tests ==

dicomdirtests files were from http://www.pcir.org, freely available image sets.
They were downsized to 16x16 images to keep them very small so they
could be added to the source distribution without bloating it. For the 
same reason, many were removed, leaving only samples of the studies,
series, and images.

For the subdirectories ending in "N" (e.g. CT2N, CT5N), the name indicates
the number of images inside the folder, i.e. CT2N has two images,
CT5N has five. This was a memory-aid for use in unit tests.

Below is the hierarchy of Patient, Study, Series, Images that comes from a
straight read of the dicomdirtests DICOMDIR file. The DICOMDIR file itself
was created using the dcmtk program dcmgpdir. It complained about different
Specific Character Set in some of the files, so some with 2022 IR6 were set
to ISO_IR 100.


Patient: 77654033: Doe^Archibald
    Study 2: 20010101: XR C Spine Comp Min 4 Views
        Series 1:  CR: (1 image)
            ['./77654033/CR1/6154']
        Series 2:  CR: (1 image)
            ['./77654033/CR2/6247']
        Series 3:  CR: (1 image)
            ['./77654033/CR3/6278']
    Study 2: 19950903: CT, HEAD/BRAIN WO CONTRAST
        Series 2:  CT: (4 images)
            ['./77654033/CT2/17106',
             './77654033/CT2/17136',
             './77654033/CT2/17166',
             './77654033/CT2/17196']

Patient: 98890234: Doe^Peter
    Study 2: 20010101: 
        Series 4:  CT: (2 images)
            ['./98892001/CT2N/6293',
             './98892001/CT2N/6924']
        Series 5:  CT: (5 images)
            ['./98892001/CT5N/2062',
             './98892001/CT5N/2392',
             './98892001/CT5N/2693',
             './98892001/CT5N/3023',
             './98892001/CT5N/3353']
    Study 428: 20030505: Carotids
        Series 1:  MR: (1 image)
            ['./98892003/MR1/15820']
        Series 2:  MR: (1 image)
            ['./98892003/MR2/15970']
    Study 134: 20030505: Brain
        Series 1:  MR: (1 image)
            ['./98892003/MR1/4919']
        Series 2:  MR: (3 images)
            ['./98892003/MR2/4950',
             './98892003/MR2/5011',
             './98892003/MR2/4981']
    Study 2: 20030505: Brain-MRA
        Series 1:  MR: (1 image)
            ['./98892003/MR1/5641']
        Series 2:  MR: (3 images)
            ['./98892003/MR2/6935',
             './98892003/MR2/6605',
             './98892003/MR2/6273']
        Series 700:  MR: (7 images)
            ['./98892003/MR700/4558',
             './98892003/MR700/4528',
             './98892003/MR700/4588',
             './98892003/MR700/4467',
             './98892003/MR700/4618',
             './98892003/MR700/4678',
             './98892003/MR700/4648']

