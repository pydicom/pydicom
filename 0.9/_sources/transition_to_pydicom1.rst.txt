.. _transition_to_pydicom1:

=========================
Transition to pydicom 1.x
=========================

.. rubric:: Important information on differences in pydicom post 1.0 vs pre-1.0

Introduction
============

As is often the case for major software version number changes, pydicom 1.0 breaks with the 
previous release of pydicom (0.9.9) in several ways.  These require changes to user code 
to target the pydicom >= 1.0 package, or to check and deal with the differences between
the versions.

Backwards-compatible changes post 1.0
  * the library is no longer ``dicom`` but is ``pydicom``, to match the package name 
  * short-form names such as ``Beams`` are no longer allowed;  use the full keyword e.g. ``BeamSequence``
  * some less-used modules within pydicom have been renamed, e.g. ``dicom.UID`` is now ``pydicom.uid``
  
Why was the package name changed?  Yes, this will cause some confusion for a while, and I apologize for this, but it
will fade over time.  There are several reasons for this change:

  * it is standard python practice for the package and the installed library to have the same name
  * first time users expect to be able to type ``import pydicom`` rather than ``import dicom``, which has caused confusion
  * it makes sense for search engines - with the correct name it is much easier to find relevant questions and example code online
  
The decision wasn't taken lightly, but with a great deal of discussion on the github issues list.  Having made the leap,
the rest of this guide should help smooth the way...

For authors of packages requiring pydicom < 1.0
========================================================
If you have authored code targeting the "old" dicom library, you have three options (at least):

  # update the code base to target pydicom >1.0
  # update your dependencies to point to package ``dicom`` rather than ``pydicom``
  # update dependencies to explictly target pydicom < 1, e.g. pydicom=0.9.9
  
The first option can be relatively simple for most projects.  If you only use
basic pydicom features, e.g. to read and write files, simply changing ``import dicom``
to ``import pydicom`` everywhere may be all that is needed.

The second and third options will get the same library installed.  The second is preferred,
as this will point to a repository explicit to the old ``dicom`` code.  This makes it clear
that your code has not been updated for pydicom 1, and allows people to install ``pydicom`` and ``dicom``
completely independently.

Error messages relating to the pydicom transition
=================================================
This section is here in the hopes of people getting redirected to this page on searches.  If that's you,
then welcome!  Hopefully the information here can get things going quickly for you.

For those with pydicom < 1.0 installed, on trying to import pydicom, they will get an ImportError message:

    >>> import pydicom
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    ImportError: No module named pydicom
    >>>
    
Your choice then is to update to pydicom >=1.0 (see Installing pydicom section), or to instead
use ``import dicom`` and follow old-style pydicom syntax.

Conversely, if pydicom >= 1.0 is installed, the error message for ``import dicom`` will look like:

    >>> import dicom
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    ImportError: No module named dicom
    >>> 

In this case you likely have installed pydicom >= 1.0, and so ``dicom`` library does
not exist.  You can simply ``import pydicom`` instead, and continue with the new pydicom, or, 
if you really need the old pydicom, then you should:

  pip install dicom
  
and you should be good to go.
  
