Version 0.9.4
=============

Changelog
---------

.. note::

   * there is a *backwards incompatible* change made to storage of file_meta
     info. See item below.
   * pydicom 0.9.4 requires Python 2.4 or higher (pydicom 0.9.3 can run under
     Python 2.3)

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
