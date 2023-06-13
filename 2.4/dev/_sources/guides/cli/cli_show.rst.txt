
``pydicom show`` command
========================

The `pydicom show` command displays representation of DICOM files or parts of them
from a command-line terminal.

Some examples were already given in the :ref:`cli_intro`, but here we will
show some additional options.

To see the available options, in a command-line terminal, type ``pydicom help show``
or ``pydicom show -h``.

.. code-block:: console

    $ pydicom help show
    usage: pydicom show [-h] [-x] [-t] [-q] filespec

    Display all or part of a DICOM file

    positional arguments:
    filespec              File specification, in format [pydicom::]filename[::element]. If `pydicom::`
                            prefix is present, then use the pydicom test file with that name. If `element`
                            is given, use only that data element within the file. Examples:
                            path/to/your_file.dcm, your_file.dcm::StudyDate,
                            pydicom::rtplan.dcm::BeamSequence[0], yourplan.dcm::BeamSequence[0].BeamNumber

    optional arguments:
    -h, --help            show this help message and exit
    -x, --exclude-private
                            Don't show private data elements
    -t, --top             Only show top level
    -q, --quiet           Only show basic information

The basic command with no options shows all data elements and nested sequences:

.. code-block:: console

    $ pydicom show pydicom::CT_small.dcm
    Dataset.file_meta -------------------------------
    (0002, 0000) File Meta Information Group Length  UL: 192
    (0002, 0001) File Meta Information Version       OB: b'\x00\x01'
    (0002, 0002) Media Storage SOP Class UID         UI: CT Image Storage
    (0002, 0003) Media Storage SOP Instance UID      UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0002, 0010) Transfer Syntax UID                 UI: Explicit VR Little Endian
    (0002, 0012) Implementation Class UID            UI: 1.3.6.1.4.1.5962.2
    (0002, 0013) Implementation Version Name         SH: 'DCTOOL100'
    (0002, 0016) Source Application Entity Title     AE: 'CLUNIE1'
    -------------------------------------------------
    (0008, 0005) Specific Character Set              CS: 'ISO_IR 100'
    (0008, 0008) Image Type                          CS: ['ORIGINAL', 'PRIMARY', 'AXIAL']
    (0008, 0012) Instance Creation Date              DA: '20040119'
    (0008, 0013) Instance Creation Time              TM: '072731'
    (0008, 0014) Instance Creator UID                UI: 1.3.6.1.4.1.5962.3
    (0008, 0016) SOP Class UID                       UI: CT Image Storage
    (0008, 0018) SOP Instance UID                    UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0008, 0020) Study Date                          DA: '20040119'
    .
    .
    .
    (0043, 104b) [DAS xm pattern]                    SL: 0
    (0043, 104c) [TGGC trigger mode]                 SS: 0
    (0043, 104d) [Start scan to X-ray on delay]      FL: 0.0
    (0043, 104e) [Duration of X-ray on]              FL: 10.60060977935791
    (7fe0, 0010) Pixel Data                          OW: Array of 32768 elements
    (fffc, fffc) Data Set Trailing Padding           OB: Array of 126 elements

Note that prefixing the file specification with ``pydicom::`` will read the file
from the *pydicom* test data files rather than from the file system.

You can also show just parts of the DICOM file by specifying a data element
using the usual pydicom keyword notation:

.. code-block:: console

    $ pydicom show pydicom::CT_small.dcm::PatientName
    CompressedSamples^CT1

    $ pydicom show pydicom::rtplan.dcm::FractionGroupSequence
    [(300a, 0071) Fraction Group Number               IS: "1"
    (300a, 0078) Number of Fractions Planned         IS: "30"
    (300a, 0080) Number of Beams                     IS: "1"
    (300a, 00a0) Number of Brachy Application Setups IS: "0"
    (300c, 0004)  Referenced Beam Sequence  1 item(s) ----
    (300a, 0082) Beam Dose Specification Point       DS: [239.531250000000, 239.531250000000, -751.87000000000]
    (300a, 0084) Beam Dose                           DS: "1.0275401"
    (300a, 0086) Beam Meterset                       DS: "116.0036697"
    (300c, 0006) Referenced Beam Number              IS: "1"
    ---------]

The ``-q`` quiet argument shows a minimal version of some of the information in the
file, using just the DICOM keyword and value (not showing the tag numbers
and VR). The example below shows the quiet mode with an image slice::

    pydicom show -q pydicom::ct_small.dcm

    SOPClassUID: CT Image Storage
    PatientName: CompressedSamples^CT1
    PatientID: 1CT1
    StudyID: 1CT1
    StudyDate: 20040119
    StudyTime: 072730
    StudyDescription: e+1
    BitsStored: 16
    Modality: CT
    Rows: 128
    Columns: 128
    SliceLocation: -77.2040634155

And the following example shows an RT Plan in quiet mode::

    pydicom show -q pydicom::rtplan.dcm

    SOPClassUID: RT Plan Storage
    PatientName: Last^First^mid^pre
    PatientID: id00001
    StudyID: study1
    StudyDate: 20030716
    StudyTime: 153557
    StudyDescription: N/A
    Plan Label: Plan1  Plan Name: Plan1
    Fraction Group 1  30 fraction(s) planned
    Brachy Application Setups: 0
    Beam 1 Dose 1.02754010000000 Meterset 116.003669700000
    Beam 1 'Field 1' TREATMENT STATIC PHOTON energy 6.00000000000000 gantry 0.0, coll 0.0, couch 0.0 (0 wedges, 0 comps, 0 boli, 0 blocks)

Quiet modes always show the SOP Class UID, patient and study information as
shown in the above two examples. After those elements, custom values for
different SOP classes are shown. Currently "Image Storage" and "RT Plan Storage"
classes have custom extra information.  Please submit an issue on the *pydicom*
issues list or a pull request to help us expand the list of custom
'quiet' mode SOP Classes.
