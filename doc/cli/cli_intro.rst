.. _cli_intro:
.. title:: CLI Introduction

*pydicom* Command-line Interface Introduction
=============================================

.. versionadded:: 2.2

.. currentmodule:: pydicom

.. rubric:: pydicom command-line interface

Introduction
------------

Starting in v2.2, *pydicom* offers a useful command-line interface (CLI) for 
exploring DICOM files, and access to the `codify` option for creating pydicom 
Python code. New subcommands may be added over time.

Example at the command line in a terminal window:

.. code-block:: default

    $ pydicom show rtplan.dcm
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


Combining *pydicom*'s CLI with Others
-------------------------------------

CLIs are useful for general exploration while programming, but also can be 
combined with other command-line filters to make very powerful
abilities. The following is an example of piping the output of the pydicom 
'show' subcommand into 'grep', filtering for lines with 
either "UI:" or "Sequence":

.. code-block:: default

    $ pydicom show rtplan.dcm | grep "UI:\|Sequence"
    (0002, 0002) Media Storage SOP Class UID         UI: RT Plan Storage
    (0002, 0003) Media Storage SOP Instance UID      UI: 1.2.999.999.99.9.9999.9999.20030903150023
    (0002, 0010) Transfer Syntax UID                 UI: Implicit VR Little Endian
    (0002, 0012) Implementation Class UID            UI: 1.2.888.888.88.8.8.8
    (0008, 0016) SOP Class UID                       UI: RT Plan Storage
    (0008, 0018) SOP Instance UID                    UI: 1.2.777.777.77.7.7777.7777.20030903150023
    (0020, 000d) Study Instance UID                  UI: 1.22.333.4.555555.6.7777777777777777777777777777
    (0020, 000e) Series Instance UID                 UI: 1.2.333.444.55.6.7777.8888
    ...
    (300a, 0111)  Control Point Sequence  2 item(s) ----
        (300a, 011a)  Beam Limiting Device Position Sequence  2 item(s) ----
        (300c, 0050)  Referenced Dose Reference Sequence  2 item(s) ----
        (300c, 0050)  Referenced Dose Reference Sequence  2 item(s) ----
    (300a, 0180)  Patient Setup Sequence  1 item(s) ----
    (300c, 0002)  Referenced RT Plan Sequence  1 item(s) ----
    (0008, 1150) Referenced SOP Class UID            UI: RT Plan Storage
    (0008, 1155) Referenced SOP Instance UID         UI: 1.9.999.999.99.9.9999.9999.20030903145128
    (300c, 0060)  Referenced Structure Set Sequence  1 item(s) ----
    (0008, 1150) Referenced SOP Class UID            UI: RT Structure Set Storage
    (0008, 1155) Referenced SOP Instance UID         UI: 1.2.333.444.55.6.7777.88888   


Extending the CLI
-----------------

For developers, you can extend this interface by adding your own sub-commands
in your own packages for whatever behavior you would like. See the section
on extending the CLI.
