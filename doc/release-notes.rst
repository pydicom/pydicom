.. currentmodule:: pydicom

===============
Release history
===============

Version 1.0.0 (under development)
=================================

Highlights
----------

This is a major release, with major changes, including backwards-incompatible
changes.

Changelog
---------

Enhancements
............

* fully python3 compatible -- one code-base for both python 2 and python 3
* package name and the import name match -- now use ``import pydicom`` rather
  than ``import dicom``
* optional GDCM support for reading files with compressed pixel data
* optional Pillow, jpeg_ls support for reading some compressed pixel data files
* cleaned up dicom dictionary code, old non-dicom-keyword code removed
* dicom dictionary updated to 2017c

Documentation
.............

* Documentation refactorization with examples. :issue:`472`.

Maintenance
...........

* Remove :class:`pydicom.filereader.DicomIter` since it is
  unused. :issue:`493`.

Maintenance
...........

* Remove ``python-dateutil`` dependency by backporting ``datetime.timezone``
  from Python 3.6 to Python 2.7. :issue:`435`.

Other changes
.............

* updated doc strings for common functions
* UID.py now uid.py to match python style guide
* added util/fixer.py -- callbacks available to fix dicom non-compliant values
  before exceptions thrown
* added PyPy support
* added util/leanread.py -- very bare-bones reading (for fastest possible speed)
* added misc/is_dicom function -- return True if a dicom file
* added context management methods to Dataset
* added date/time converters :issue:`143`
* fixed pixel handling for ``PlanarConfiguration=0``
* updated uid generation to ensure uniqueness
* added some heuristics to accept files with missing preamble and file_meta
* added ``from_name()`` method to UID class, to generate UID instance from
  descriptive name
* added ability to add custom dicom dictionary items via ``add_dict_entry()``
  and ``add_dict_entries()``
* more methods for DataElement -- keyword, is_retired, etc.
* some support for pickle, cpickle
* fixes/additions for some character set encodings

Version 0.9.9
=============

Changelog
---------

In addition to bug fixes, pydicom 0.9.9 contains updates for all dicom
dictionaries.  New features include DICOMDIR handling, and a utility module
which produces python/pydicom source code to recreate a dicom file.

Enhancements
............

* All dicom dictionaries updated (standard dictionary, UID dictionary, and
  private dictionaries)
* Dicom commands also added to dictionary
* Ability to work with DICOMDIR: ``read_dicomdir()`` function and ``DicomDir``
  class. Example file ``show_dicomdir.py`` file added to examples subdirectory.
* ``codify.py``: Produce python/pydicom source code from a dicom file.
* a number of python 3 compatibility enhancements
* setup.py uses ez_setup only if setuptools not already installed
* exceptions carry tag info with them, to aid in debugging

Contrib file changes
....................

* pydicom_series:  force parameter added (Nil Goyette)
* dcm_qt_tree: switch to OrderedDict to preserve ordering of tags (Padraig Looney)

Other Contributors
..................

Other than Jonathan and myself, other contributors were: Rickard Holmberg,
Julien Lamy, Yaroslav Halchenko, Mark White, Matthew Brett, Dimitri
Papadopoulos, videan42 ...(sorry if I've missed anyone).

Version 0.9.8
=============

Changelog
---------

pydicom 0.9.8 is mainly a consolidation step before moving to official python 3
compatibility in pydicom 1.0.  It also reverts the change to using Decimal for
VR of DS (in pydicom 0.9.7), due to performance issues. DS as Decimal is still
available, but is off by default.

Major changes
.............

* Requires python 2.6 or later, in preparation for python 3 compatibility
* experimental python 3 compatibility (unofficial at this point) -- uncomment
  the two indicated lines in setup.py to use it. Please provide feedback to the
  issues list.
* DS values reverted to using float as default (issue 114) due to slow
  performance using python Decimal. Speed tests show approx factor of 10
  improvement compared with pydicom 0.9.7 (several revisions up to
  r78ba350a3eb8)
* streamlined much code internally taking advantage of modern python
  constructs: decorators, generators, etc

Bug fixes
.........

* Fix for duplicate logger from Gunnar Schaefer. Fixes issue 107 (revision
  774b7a55db33)
* Fix rewind behavior in find_bytes (issue 60, revision 6b949a5b925b)
* Fix error in nested private sequences (issue 113, revision 84af4b240add)


Enhancements
............

* UID generator added (Félix C. Morency) (revisions 0197b5846bb5 and
  3678b1be6aca, tests in f1ae573d9de5, 0411bab7c985)
* new PersonName3 class for python 3: (revision 9b92b336e7d4)

Contrib file changes
....................

* Fix for pydicom_series for DS decimal (revision e830f30b6781)
* new dcm_qt_tree.py module - tree display of dicom files using PySide and
  Qt. Contributed by Padraig Looney.

Special acknowledgement to Jonathan Suever who contributed most of the python 3
work and many bug fixes.

Version 0.9.7
=============

Changelog
---------

pydicom 0.9.7 resolves some remaining bugs before moving to python 3
compatibility. ** It is the last version which will run with python < 2.6 **
(it will run with python2.4 to python2.7)

Major changes
.............

* Added DICOM 2011 keywords. Old "named tags" still work, but will be
deprecated in future versions. Most names are identical, but some have changed.
For example:
* SamplesperPixel becomes SamplesPerPixel (capital 'P' on 'Per')
* Beams becomes BeamSequence (and similar for all sequences)
* Decimal and integer strings handled much better (revisions 4ed698a7bfbe and
  c313d2befb08).
* New classes for VR of types DS and IS (DS is derived from python Decimal)
* New MultiValue class, enforcing all values of same type
* New config.py file with user-definable parameters:
* allow_DS_float (default False) for controlling whether float values can be
  used to construct DS or IS strings.
* enforce_valid_values (default True) for ensuring IS, DS meet DICOM standard
  limits To change these, use 'import dicom.config, then
  dicom.config.<parameter>={True|False}' before setting values of data elements

Users are encouraged to switch to the official DICOM keywords, as these are now
part of the standard, and promote consistency across programming languages and
libraries.

Bug fixes
.........

* New way to read file meta information, not using the group length, instead
  reading until end of group 2 data elements. If group length dose not match,
  log a warning (revision b6b3658f3b14).
* Fix bug in copying raw private data elements (issue 98)
* Force logging level to warning on 'import dicom' (issue 102)
* Deferred read fixed to work with gzipped files (issue 103)
* Setting individual items in a DS or IS list now saves to file correctly
* Japanese and Korean encoding fixes (issue 110)

Other Enhancements
..................

* New Sequence class which verifies items are Datasets (issue 52)
* Assignment to SQ data element checks value is a Sequence or can be converted
  to one (issue 111)
* dir(ds) now includes methods and properties as well as DICOM named tags. Work
  only on Python >= 2.6 as previous versions do not call __dir__ method
  (issue 95)
* Added much more debugging info and simplified reading of data elements
  (revision b6b3658f3b14)
* updated example files to DICOM 2011 keywords; fixed bugs

Many of the bug fixes/enhancements were submitted by users. Many thanks to
those who contributed.

Version 0.9.6
=============

Changelog
---------

pydicom 0.9.6 updates the dictionary to the DICOM 2011 standard, and has a
number of bug fixes

Major changes
.............

* updated the dictionary to the DICOM 2011 standard's dictionary.

Bug fixes
.........

* Fixed bug in Dataset.file_metadata() and deprecated in favor of FileDataset
  (issue 93)
* Fixed UID comparisons against non-string values (issue 96)
* catch exceptions on reading undefined length private data elements (issue 91,
  issue 97)
* Fixed bug in raising exception for unknown tag

Other
.....

* added example file write_new.py to show how to create DICOM files from scratch
* updated other example files
* more PEP-8 style changes

Version 0.9.5
=============

Changelog
---------

pydicom 0.9.5 is primarily a bug-fix release but includes some contrib files
also.

Major fixes in this release
...........................

* fix for incorrect pixel integer types which could lead to numeric errors
  (issue 79)
* By default an InvalidDicomError will be raised when trying to read a
  non-DICOM file (unless read_file keyword arg {{{force}}} is True) (revision
  fc790f01f5)
* fix recursion error on private data elements (issue 81, issue 84)

Other fixes in this release
...........................

* Fix for unicode decode failing with VM > 1 (issue 78)
* fix for fail of DicomIter on files with Explicit VR Transfer Syntax UID
  (issue 82)
* Fix for python 2.5 and 'with' statement (revision 1c32791bf0)
* Handle 'OB/OW' VR as well as 'OW/OB' (revision e3ee934bbc)
* Fix dataset.get(tag) so returns same as dataset[tag] (issue 88)

New 'Contrib' files
...................

* dicom_dao.py by Mike Wallace -- CouchDB storage of DICOM info and binary data
* pydicom_series.py by Almar Klein -- Reads files and separates into distinct
  series.

Other
.....

* switch to Distribute for packaging
* preliminary work on python 3 compatiblity
* preliminary work on using sphinx for documentation
* preliminary work on better writing of files from scratch

Version 0.9.4
=============

Changelog
---------

.. note::

   * there is a *backwards incompatible* change made to storage of file_meta
     info. See item below.
   * pydicom 0.9.4 requires python 2.4 or higher (pydicom 0.9.3 can run under
     python 2.3)

Major changes/additions in this version
.......................................

* file reading code reorganized substantially
* significant speed increase for reading DICOM files -- approx 3 times faster
  than 0.9.3
* partial file reading available -- in particular, new optional argument to
  read_file(), stop_before_pixels, will stop before getting to the pixel data,
  not reading those into memory. Saves a little time for small images, but
  could be quite helpful for very large images when the pixel data is not
  needed.
* read_file() now returns a !FileDataset object, instead of a plain
  Dataset. Most user code will not see much difference (except see next
  bullet on file meta information) but now the information stored in the
  object has been made explicit -- e.g. the endian-ness and whether the file
  syntax was explicit VR or implicit VR.
* file meta info has been separated from the main dataset. Logically, this
  makes more sense, as the file meta is not really part of the dataset, but is
  specific to the method of storage. This is a backwards-incompatible change,
  but is easily fixed by changing any references to file-meta data elements
  from {{{dataset.<name>}}} to {{{dataset.file_meta.<name>}}}. The file_meta is
  a dataset like any other, all the usual methods for viewing, changing data
  elements work on it also.
* private dictionaries file now generated from the GDCM library's private
  dictionary -- code to convert formats contributed by Daniel Nanz.
* license has returned to an MIT-based license (with the compatible GDCM also
  noted for the private dictionary component).
* contributed files with example code for viewing using wxPython or Tkinter
  (and PIL) -- in dicom.contrib folder. Thanks to Dave Witten, Daniel Nanz and
  Adit Panchal for these contributions.
* updates to pydicom's DICOM data dictionary contributed by Adit Panchal:
  CP805/916; Supp 43 and 117 (and UID dict), Supp 119 and 122

Other changes and bug fixes
...........................

* Tag is now a factory function; the class is called !BaseTag. This was part of
  the file reading speed-up process -- a new class !TupleTag was also created,
  for faster file reading
* passing a file object to read_file() now works correctly, and also the file
  closing works as it should (caller needs to close any files passed in)
  (issue 73)
* Fix for issue 72 : dataset.get() fails when passed type other than string or
  Tag. Patch contributed by !NikitaTheSpider
* Fix for issue 58 : error opening file with unicode. Fix contributed by Pierre
  Raybaut
* Fix for issue 42 : catch !AttributeError in property and give proper error
  message
* Fix for issue 55 : UI type changed with string operations
* Tag fixes and enhancements : can create tags with hex string (group,
  elem). Allow lists as well as tuples (issue 47). Fix arg2=0 bug (issue 64).

Version 0.9.3
=============

Changelog
---------

Major changes
.............

* changed to MIT-style license
* option to defer reading of large data element values using read_file()'s new
  defer_size argument (r102, r103)
* dictionary of private tags added -- descriptive text shown when available
  (issue36, r97, r110)
* more conversion to PEP-8 style. Should now use read_file(), save_as(),
  pixel_array rather than !ReadFile(), !SaveAs(), !PixelArray. Old names kept
  for now as aliases.

Other Enhancements
..................

* added DicomFileLike class to simplify and generalize access. Any object that
  has read, write, seek, tell, and close can now be used. (r105)
* added dataset.iterall() function to iterate through all items (including
  inside sequences) (r105)
* added dataset.formatted_lines() generator to allow custom formatting (r91,
  r113)
* made reading tolerant of truncated files -- gives a warning, but returns
  dataset read to that point (r95)

Bug Fixes
.........

* fixed issue38, name collision for 'Other Patient Ids' as both data element
  and sequence name in DICOM standard (r95, r96)
* fixed issue40, blank VRs in some DICOM dictionary entries caused
  NotImplementError on reading (r100)
* fixed issue41, reading VRs of 'US or SS' and similar split on backslash
  character (r104)
* fixed bug where TransferSyntaxUID not present when reading file without DICOM
  header (r109)
* fixed print recursion bug when printing a UID (r111)

Other
.....

* many of the example files updated
* updated anonymize example file to also deal with 'OtherPatientIDs' and
  'PatientsBirthDate' (r98)

Version 0.9.2
=============

Changelog
---------

Major changes
.............

* Renamed Attribute class and related modules to !DataElement. Old code will
  continue to work until pydicom 1.0, but with a !DeprecationWarning (issue22,
  r72, r73)
* Added support for character sets through Specific Character Set (0008,0005),
  using python unicode. Thus foreign languages can display names in Greek,
  Japanese, Chinese etc characters in environments which support unicode
  (demonstrated in dicomtree.py example using Tkinter GUI) (r64, r65)

Other Enhancements
..................

* Added support for auto-completion of dataset elements in ipython; also all
  environments using python 2.6 (r69, r70)
* Added __iter__() to Dataset so returns data elements in DICOM order with "for
  data_elem in dataset:" (r68)
* Added dicomtree.py example program showing a DICOM file in a GUI window
  (Tkinter/Tix).
* Added !PersonName class to parse components of names more easily (r55)
* Added UID class to handle UID values. Name rather than UID number shown,
  UID_dictionary used (r51).
* Code tested under python 2.6
* Added !DataElement.name property; synonym for !DataElement.description()
  function

Bug Fixes
.........

* Fixed issue27, sequence with a single empty item read incorrectly
* Fixed bug that read_OW did not handle !UndefinedLength (r50)
* Fixed bugs in example files anonymize.py, !DicomInfo.py, and dicomtree.py
  (r51)
* Fixed issue33, VR=UN being split on backslash (r70)
* Fixed issue18, util directory not installed (r45)

Other
.....

* Added example file myprint.py -- shows how to custom format DICOM file
  information (r67)
* Reorganized test files and added various new tests
* added preliminary work on encapsulated data (r50)
* added some simple files to view or work with pixel data (r46)
* Dataset.!PixelDataArray() Numpy array changed to property Dataset.!PixelArray
* changed to setuptools for packaging rather than distutils
