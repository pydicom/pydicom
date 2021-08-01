
Introduction
============

Starting in v2.2, *pydicom* offers a useful command-line interface (CLI) for
exploring DICOM files, and access to the `codify` option for creating pydicom
Python code. Additional subcommands may be added over time.

Example at the command line in a terminal window:

.. code-block:: console

    $ pydicom show pydicom::rtplan.dcm
    Dataset.file_meta -------------------------------
    (0002, 0000) File Meta Information Group Length  UL: 156
    (0002, 0001) File Meta Information Version       OB: b'\x00\x01'
    (0002, 0002) Media Storage SOP Class UID         UI: RT Plan Storage
    (0002, 0003) Media Storage SOP Instance UID      UI: 1.2.999.999.99.9.9999.9999.20030903150023
    (0002, 0010) Transfer Syntax UID                 UI: Implicit VR Little Endian
    (0002, 0012) Implementation Class UID            UI: 1.2.888.888.88.8.8.8
    -------------------------------------------------
    (0008, 0012) Instance Creation Date              DA: '20030903'
    (0008, 0013) Instance Creation Time              TM: '150031'
    (0008, 0016) SOP Class UID                       UI: RT Plan Storage
    (0008, 0018) SOP Instance UID                    UI: 1.2.777.777.77.7.7777.7777.20030903150023
    (0008, 0020) Study Date                          DA: '20030716'
    ...

Note that prefixing the file specification with ``pydicom::`` will read the file
from the *pydicom* test data files rather than from the normal file system.
The following examples will use that so that you can replicate these
examples exactly.  In normal use, you would leave the ``pydicom::`` prefix
off when working with your files.

You can also show just parts of the DICOM file by specifying a data element
using the usual *pydicom* keyword notation:

.. code-block:: console

    $ pydicom show pydicom::rtplan.dcm::FractionGroupSequence[0]
    (300a, 0071) Fraction Group Number               IS: "1"
    (300a, 0078) Number of Fractions Planned         IS: "30"
    (300a, 0080) Number of Beams                     IS: "1"
    (300a, 00a0) Number of Brachy Application Setups IS: "0"
    (300c, 0004)  Referenced Beam Sequence  1 item(s) ----
    (300a, 0082) Beam Dose Specification Point       DS: [239.531250000000, 239.531250000000, -751.87000000000]
    (300a, 0084) Beam Dose                           DS: "1.0275401"
    (300a, 0086) Beam Meterset                       DS: "116.0036697"
    (300c, 0006) Referenced Beam Number              IS: "1"
    ---------

You can see the available subcommands by simply typing ``pydicom`` with no
arguments, or with ``pydicom help``:

.. code-block:: console

    $ pydicom help
    Use pydicom help [subcommand] to show help for a subcommand
    Available subcommands: codify, show

And, as noted in the block above, you get help for a particular subcommand
by typing ``pydicom help [subcommand]``.  For example:

.. code-block:: console

    $ pydicom help show
    usage: pydicom show [-h] [-x] [-t] [-q] filespec

    Display all or part of a DICOM file

    positional arguments:
    filespec              File specification, in format [pydicom::]filename[::element]. If `pydicom::`
                            prefix is used, then show the pydicom test file with that name. If `element`
                            is given, use only that data element within the file. Examples:
                            path/to/your_file.dcm, your_file.dcm::StudyDate,
                            pydicom::rtplan.dcm::BeamSequence[0], yourplan.dcm::BeamSequence[0].BeamNumber

    optional arguments:
    -h, --help            show this help message and exit
    -x, --exclude-private
                            Don't show private data elements
    -t, --top             Only show top level
    -q, --quiet           Only show basic information


Installing the pydicom CLI
--------------------------

The ``pydicom`` command should automatically be available after you
`pip install pydicom`.  It should not require any updates to the system
path or environment variables.

If you are helping develop *pydicom* code, and are using git clones,
you will have to ``pip install -e .`` or ``python setup.py develop`` from
the `pydicom` repository root. This has to be repeated for any changes to
`setup.py` (e.g. to add a new subcommand).

If you are developing subcommands within your own package, you will need to
reinstall your package similar to the above as you add entry points.


Combining with other CLIs
-------------------------

CLIs are useful for general exploration while programming, but also can be
combined with other command-line filters for additional functionality. The
following is an example of piping the output of the pydicom
'show' subcommand into 'grep', filtering for lines with
either "Dose" or "Sequence" in them:

.. code-block:: console

    $ pydicom show pydicom::rtplan.dcm | grep "Dose\|Sequence"
    (300a, 0010)  Dose Reference Sequence  2 item(s) ----
    (300a, 0012) Dose Reference Number               IS: "1"
    (300a, 0014) Dose Reference Structure Type       CS: 'COORDINATES'
    (300a, 0016) Dose Reference Description          LO: 'iso'
    (300a, 0018) Dose Reference Point Coordinates    DS: [239.531250000000, 239.531250000000, -741.87000000000]
    (300a, 0020) Dose Reference Type                 CS: 'ORGAN_AT_RISK'
    (300a, 0023) Delivery Maximum Dose               DS: "75.0"
    (300a, 002c) Organ at Risk Maximum Dose          DS: "75.0"
    (300a, 0012) Dose Reference Number               IS: "2"
    (300a, 0014) Dose Reference Structure Type       CS: 'COORDINATES'
    (300a, 0016) Dose Reference Description          LO: 'PTV'
    (300a, 0018) Dose Reference Point Coordinates    DS: [239.531250000000, 239.531250000000, -751.87000000000]
    (300a, 0020) Dose Reference Type                 CS: 'TARGET'
    (300a, 0026) Target Prescription Dose            DS: "30.826203"
    (300a, 0070)  Fraction Group Sequence  1 item(s) ----
    (300c, 0004)  Referenced Beam Sequence  1 item(s) ----
        (300a, 0082) Beam Dose Specification Point       DS: [239.531250000000, 239.531250000000, -751.87000000000]
        (300a, 0084) Beam Dose                           DS: "1.0275401"
    (300a, 00b0)  Beam Sequence  1 item(s) ----
    (300a, 00b6)  Beam Limiting Device Sequence  2 item(s) ----
    (300a, 0111)  Control Point Sequence  2 item(s) ----
        (300a, 0115) Dose Rate Set                       DS: "650.0"
        (300a, 011a)  Beam Limiting Device Position Sequence  2 item(s) ----
        (300c, 0050)  Referenced Dose Reference Sequence  2 item(s) ----
            (300a, 010c) Cumulative Dose Reference Coefficie DS: "0.0"
            (300c, 0051) Referenced Dose Reference Number    IS: "1"
            (300a, 010c) Cumulative Dose Reference Coefficie DS: "0.0"
            (300c, 0051) Referenced Dose Reference Number    IS: "2"
        (300c, 0050)  Referenced Dose Reference Sequence  2 item(s) ----
            (300a, 010c) Cumulative Dose Reference Coefficie DS: "0.9990268"
            (300c, 0051) Referenced Dose Reference Number    IS: "1"
            (300a, 010c) Cumulative Dose Reference Coefficie DS: "1.0"
            (300c, 0051) Referenced Dose Reference Number    IS: "2"
    (300a, 0180)  Patient Setup Sequence  1 item(s) ----
    (300c, 0002)  Referenced RT Plan Sequence  1 item(s) ----
    (300c, 0060)  Referenced Structure Set Sequence  1 item(s) ----

Using the "or Sequence" (```\|Sequence```) regular expression as above allows you
to see any filtered results in relation to their parent Sequences.

See the :ref:`cli_show` section for more examples of the `show`
command, its options, and the ability to show only data elements or sequences
within the file.
