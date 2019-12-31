:orphan:

=====================
Writing documentation
=====================

Types of documentation
======================

* **Tutorials**: take a reader unfamiliar with *pydicom* through a series of
  steps to achieve something useful
* **How-to/examples**: more advanced versions of tutorials, for readers that
  already have some understanding of how *pydicom* works
* **Guides**: aim to explain a subject at a fairly high level
* **Reference**: contain technical reference information for the *pydicom* API
  for a reader that has some familiarity with *pydicom* but needs to learn or
  be reminded about a specific part of it

General style guidelines
========================

* **pydicom** - italicized lowercase: *pydicom*
* **DICOM**, **DICOM Standard** - uppercase DICOM, and S on Standard
* **Python** - capitalize Python
* **itemize**, etc - use the American English spelling
* **(7FE0,0010) Pixel Data** - use uppercase hex, no space between the comma
  and element number, and italicize the element name, e.g. (7FE0,0010) *Pixel
  Data*. When referring to an element name by itself then use italics: *Bits
  Allocated*
* **ds**, **elem**, **seq**, **arr** - when writing examples try to use ``ds``
  as the variable name for :class:`~pydicom.dataset.Dataset`, ``elem`` for
  :class:`~pydicom.dataelem.DataElement`, ``seq`` for sequences and ``arr``
  for numpy arrays.
* **them**, **they**, **their** - use gender neutral pronouns when referring to
  a hypothetical person
* Use the double back-tick markup \``0xB4\`` when referring to:

  * A Python built-in value such as ``True``, ``False``, ``None``
  * When referring to a value passed by a parameter: If `fragments_per_frame`
    is not ``1`` then...
  * When writing a hex value ``0xB4``
  * When referring to a class, function, variable, etc and you haven't
    used semantic markup: ``Dataset`` when not using
    :class:`~pydicom.dataset.Dataset`
* Use a single back-tick \`italics\` for parameter names: If
  `fragments_per_frame` is not...
* For the API reference documentation, follow the `NumPy docstring guide
  <https://numpydoc.readthedocs.io/en/latest/format.html>`_


Guidelines for reStructuredText
===============================

* In section titles, capitalize only initial words and proper nouns
* Documentation should be wrapped at 80 characters unless there's a good reason
  not to
* Because Sphinx will automatically link to the corresponding API
  documentation, the more semantic markup you can add, the better. So this::

    :attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` returns a :class:`numpy.ndarray`

  which produces: ":attr:`Dataset.pixel_array
  <pydicom.dataset.Dataset.pixel_array>` returns a :class:`numpy.ndarray`",
  is better than this::

    ``Dataset.pixel_array`` returns a numpy ``ndarray``

  which produces: "``Dataset.pixel_array`` returns a numpy ``ndarray``"


* Targets can be prefixed with **~** so that the last bit of the path gets used
  as the link title. So ``:class:`~pydicom.dataset.Dataset``` will show as a
  :class:`~pydicom.dataset.Dataset`.
* Python and NumPy objects can also be referenced: ``:class:`float```,
  ``:class:`numpy.dtype```
* Use ``:dcm:`` to link to the CHTML version of the DICOM Standard. For
  example, ``:dcm:`this section<part05/sect_6.2.html>``` will link to
  :dcm:`this section<part05/sect_6.2.html>` of the Standard. The link target
  should be the part of the URL after
  ``http://dicom.nema.org/medical/dicom/current/output/chtml/``
* Use these heading styles::

    ===
    One
    ===

    Two
    ===

    Three
    -----

    Four
    ~~~~

    Five
    ^^^^

* Use ``.. note::`` and ``.. warning::`` and similar boxes sparingly
* New features should be documented with ``.. versionadded:: X.Y`` at the top
  of the first section and changes to existing features with
  ``..versionchanged:: X.Y`` at the bottom of the first section::

    .. versionchanged:: 1.4

        The ``handler`` keyword argument was added
