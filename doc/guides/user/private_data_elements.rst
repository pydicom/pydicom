.. _private_data_elements:

Private Data Elements
=====================

.. currentmodule:: pydicom.dataset

The DICOM standard allows DICOM dataset creators to use `private data elements`
to store information that is not defined by the DICOM standard itself.

Private data elements are stored in a :class:`~pydicom.dataset.Dataset` just
like other data elements. When reading files with *pydicom*, they will automatically be read
and available for display.  *pydicom* knows descriptive names for some
'well-known' private data elements, but for others it may not be able to
show anything except the tag and the value.

When writing your own private data elements, the DICOM standard requires the
use of 'private creator blocks'.  *pydicom* has some convenience
functions to make creating private blocks and data elements easier.

Displaying private elements
---------------------------

Here are some of the private tags displayed for *pydicom's* example CT dataset::

    >>> from pydicom import examples
    >>> ds = examples.ct
    >>> ds
    Dataset.file_meta -------------------------------
    (0002,0000) File Meta Information Group Length  UL: 192
    (0002,0001) File Meta Information Version       OB: b'\x00\x01'
    (0002,0002) Media Storage SOP Class UID         UI: CT Image Storage
    (0002,0003) Media Storage SOP Instance UID      UI: 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    (0002,0010) Transfer Syntax UID                 UI: Explicit VR Little Endian
    (0002,0012) Implementation Class UID            UI: 1.3.6.1.4.1.5962.2
    (0002,0013) Implementation Version Name         SH: 'DCTOOL100'
    (0002,0016) Source Application Entity Title     AE: 'CLUNIE1'
    -------------------------------------------------
    (0008,0005) Specific Character Set              CS: 'ISO_IR 100'
    (0008,0008) Image Type                          CS: ['ORIGINAL', 'PRIMARY', 'AXIAL']
    ...
    (0009,0010) Private Creator                     LO: 'GEMS_IDEN_01'
    (0009,1001) [Full fidelity]                     LO: 'GE_GENESIS_FF'
    (0009,1002) [Suite id]                          SH: 'CT01'
    ...

The last three lines above show a (gggg,0010) *Private Creator* element followed by
two private data elements. Private creator elements are used to reserve the set of
tags with the same group number for that creator's use. So with the above the reserved group
number is ``0x0009``, so (0009,1001) *[Full fidelity]* and (0009,1002) *[Suite id]* private
elements belong to the ``'GEMS_IDEN_01'`` private element creator.

Since private data elements are not part of the DICOM standard they lack standardized
element keywords, which is indicated by enclosing the element's name in square brackets. They
are also not guaranteed to be unique for a given element tag. Because of this *pydicom*
does not allow you to use a keyword to access them, but they can still be accessed using
the tag:

    >>> elem = d[0x00091001]
    >>> type(elem)
    <class 'pydicom.dataelem.DataElement'>
    >>> elem.value
    'GE_GENESIS_FF'

You can also create a :class:`PrivateBlock` instance and access private elements
through it::

    >>> block = ds.private_block(0x0009, 'GEMS_IDEN_01')
    >>> block[0x01]
    (0009,1001) [Full fidelity]                     LO: 'GE_GENESIS_FF'
    >>> block[0x01].value
    'GE_GENESIS_FF'

Using the private block like this is even more useful when creating your own
private data elements, as shown in the next section.

Adding private elements
-----------------------

The DICOM standard requires a private creator data element to identify and
reserve a section of private tags. That name should be unique, and usually
has the company name as the first part to accomplish that.  *pydicom* provides
convenience functions to manage this::

    >>> block = ds.private_block(0x000b, "My company 001", create=True)
    >>> block.add_new(0x01, "SH", "my value")
    >>> ds
    ...
    (000b, 0010) Private Creator                     LO: 'My company 001'
    (000b, 1001) Private tag data                    SH: 'my value'
    ...

Standard Python operations like ``in`` and ``del`` can also be used when working
with a private block object::

    >>> 0x01 in block
    True
    >>> 0x02 in block
    False
    >>> del block[0x01]
    >>> 0x01 in block
    False

Since v3.0, there's also a convenience method to add a private tag without creating a private
block first::

    >>> ds.add_new_private("My company 001", 0x000B, 0x01, "my value", "SH")
    >>> ds
    ...
    (000b, 0010) Private Creator                     LO: 'My company 001'
    (000b, 1001) Private tag data                    SH: 'my value'
    ...

Note that for known private tags you don't need to provide the VR in this function.

Removing all private elements
-----------------------------

One part of anonymizing a DICOM file is to ensure that private data elements
have been removed, as there is no guarantee as to what kind of information
might be contained in them.  *pydicom* provides a convenience function
:func:`Dataset.remove_private_tags` to recursively remove private elements::

    >>> ds.remove_private_tags()

This can also be helpful during interactive sessions when exploring DICOM
files, to remove a large number of lines from the display of a dataset --
lines which may not provide useful information.

Adding new elements to the DICOM dictionaries
---------------------------------------------
*pydicom* contains a dictionary with all known public elements from the latest DICOM standard,
as well as a separate dictionary with a number of known private elements collected from various
sources.

Sometimes you may encounter elements unknown to *pydicom* - either because they've been defined
by a newer version of the DICOM standard, or because they're private elements that aren't in
the private element dictionary. When this occurs you can add these elements to the corresponding
dictionary before reading or writing a dataset containing them, after that they'll be handled
correctly.

For standard public elements, you can use :func:`~pydicom.datadict.add_dict_entry` or
:func:`~pydicom.datadict.add_dict_entries` (for multiple elements)::

    >>> add_dict_entry(tag=0x888800001, VR="SH", keyword="SomeNewTag", description="Some New Tag")

For private elements, the analogous functions are
:func:`~pydicom.datadict.add_private_dict_entry` and
:func:`~pydicom.datadict.add_private_dict_entries`::

    >>> add_private_dict_entry(private_creator="ACME 1.1", tag=0x004100001, VR="DA", description="Release Date")

Note that unlike public elements, private elements don't have a keyword. As a private element
is defined by the tuple of private creator, group ID and tag, you always have to provide the private
creator to define a new private tag offset.

An example of how to use :func:`~pydicom.datadict.add_private_dict_entries` can
be found in :ref:`this code snippet <sphx_glr_auto_examples_metadata_processing_plot_add_dict_entries.py>`.
