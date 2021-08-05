
``pydicom codify`` command
==========================

The ``pydicom codify`` command takes a DICOM file and produces Python code to
recreate that file, or, optionally a subset within that file.

See :ref:`writing_files_using_codify` for full details of writing a complete
file.  Here we will review the command-line options in more detail than
in that section, and show how to export a dataset within a DICOM file that has
sequences.

.. Warning::

  The code produced by ``codify`` will contain all the information in the original
  file, which may include private health information or other sensitive
  information.

A simple example
----------------

A simple example of using the ``codify`` command would be::

    $ pydicom codify pydicom::rtplan.dcm

    # Coded version of DICOM file 'C:\git\pydicom\pydicom\data\test_files\rtplan.dcm'
    # Produced by pydicom codify utility script
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.sequence import Sequence

    # Main data elements
    ds = Dataset()
    ds.InstanceCreationDate = '20030903'
    ds.InstanceCreationTime = '150031'
    ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5'
    ds.SOPInstanceUID = '1.2.777.777.77.7.7777.7777.20030903150023'
    ds.StudyDate = '20030716'
    ds.StudyTime = '153557'
    .
    .
    .

Note that prefixing the file specification with ``pydicom::`` will read the file
from the *pydicom* test data files rather than from the file system.


Command options
---------------

In the above example, the output was directed to screen, because no output file
was specified. To see the available command options, use the ``help`` command:

.. code-block::

    pydicom help codify

    usage: pydicom codify [-h] [-e EXCLUDE_SIZE] [-p] [-s SAVE_AS] filespec [outfile]

    Read a DICOM file and produce the *pydicom* (Python) code which can create that file

    positional arguments:
    filespec              File specification, in format [pydicom::]filename[::element]. If `pydicom::`
                            prefix is used, then use the pydicom test file with that name. If `element`
                            is given, use only that data element within the file. Examples:
                            path/to/your_file.dcm, your_file.dcm::StudyDate,
                            pydicom::rtplan.dcm::BeamSequence[0],
                            yourplan.dcm::BeamSequence[0].BeamNumber
    outfile               Filename to write python code to. If not specified, code is written to
                            stdout

    optional arguments:
    -h, --help            show this help message and exit
    -e EXCLUDE_SIZE, --exclude-size EXCLUDE_SIZE
                            Exclude binary data larger than specified (bytes). Default is 100 bytes
    -p, --include-private
                            Include private data elements (default is to exclude them)
    -s SAVE_AS, --save-as SAVE_AS
                            Specify the filename for ds.save_as(save_filename); otherwise the input name
                            + '_from_codify' will be used

    Binary data (e.g. pixels) larger than --exclude-size (default 100 bytes) is not included. A dummy
    line with a syntax error is produced. Private data elements are not included by default.


For example::

    pydicom codify -s savename.dcm dicomfile.dcm pythoncode.py

would read the DICOM file "dicomfile.dcm" and write the Python code
to file "pythoncode.py".  In that code, near the end of the file
would be a ``ds.save_as("savename.dcm", ...)`` line.

.. Note::

    By default, any private data elements within the file are not translated
    to code.  If you want to include them, use the ``-p`` parameter.


Codifying a part of a DICOM file
--------------------------------

Note that the ``filespec`` argument to the ``codify`` command, as for
:ref:`the show command<cli_show>`, allows you to specify a data element within the file,
rather than the whole file::

    pydicom codify pydicom::rtplan.dcm::FractionGroupSequence[0]

    # Coded version of non-file dataset
    ...

    # Main data elements
    ds = Dataset()
    ds.FractionGroupNumber = "1"
    ds.NumberOfFractionsPlanned = "30"
    ds.NumberOfBeams = "1"
    ds.NumberOfBrachyApplicationSetups = "0"

    # Referenced Beam Sequence
    refd_beam_sequence = Sequence()
    ds.ReferencedBeamSequence = refd_beam_sequence

    # Referenced Beam Sequence: Referenced Beam 1
    refd_beam1 = Dataset()
    refd_beam1.BeamDoseSpecificationPoint = [239.531250000000, 239.531250000000, -751.87000000000]
    ...

Currently, only a data element which is a :class:`~pydicom.dataset.Dataset`
(an item within a :class:`~pydicom.sequence.Sequence`) is accepted.
The resulting code would not on its own produce a correct DICOM file,
but could be useful as a model when creating
more complete code.  For example, issuing code for one item in a
``Sequence`` could be the starting point towards a loop
producing a number of sequence items.
