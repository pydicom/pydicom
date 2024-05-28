.. _private_data_elements:

Private Data Elements
=====================

.. rubric:: Accessing or creating private data elements

.. currentmodule:: pydicom.dataset

Introduction
------------

The DICOM standard allows DICOM file creators to use `private data elements`
to store information that is not defined by the DICOM standard itself.

Private data elements are stored in a :class:`~pydicom.dataset.Dataset` just
like other data elements. When reading files with *pydicom*, they will automatically be read
and available for display.  *pydicom* knows descriptive names for some
'well-known' private data elements, but for others it may not be able to
show anything except the tag and the value.

When writing your own private data elements, the DICOM standard requires the
use of 'private creator blocks'.  *pydicom* has some convenience
functions to make creating private blocks and data elements easier.

The sections below outlines accessing and creating private blocks and data
elements using *pydicom*.

Displaying Private Data Elements in *pydicom*
---------------------------------------------

Here is an example of some private tags displayed for *pydicom's* example CT
dataset::

    >>> from pydicom import examples
    >>> ds = examples.ct
    >>> ds
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
    ...
    (0009, 0010) Private Creator                     LO: 'GEMS_IDEN_01'
    (0009, 1001) [Full fidelity]                     LO: 'GE_GENESIS_FF'
    (0009, 1002) [Suite id]                          SH: 'CT01'
    ...

The last two lines in the example above show *pydicom's* display of two private
data elements.  The line preceding those shows the private creator data element
that reserves a section of tag element numbers for that creator's use.

Since the descriptions for private data elements are not part of the DICOM
standard, and are thus not necessarily unique, *pydicom* does not allow you to
access data elements using those names. This is indicated by enclosing the
text in square brackets, to make it clear it is different from DICOM
standard descriptors.

You can still access the private data elements using the tag, remembering that
data elements access by tag number return a full :class:`~pydicom.dataelem.DataElement`
instance, and the `value` attribute is needed to get the value::

    >>> ds[0x00091001].value
    'GE_GENESIS_FF'

You can also create a :class:`PrivateBlock` instance and access elements
through it::

    >>> block = ds.private_block(0x0009, 'GEMS_IDEN_01')
    >>> block[0x01]
    (0009, 1001) [Full fidelity]                     LO: 'GE_GENESIS_FF'
    >>> block[0x01].value
    'GE_GENESIS_FF'

Using the private block like this is even more useful when creating your own
private data elements, as shown in the next section.

Setting Private Data Elements with *pydicom*
--------------------------------------------

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
with block object::

    >>> 0x01 in block
    True
    >>> 0x02 in block
    False
    >>> del block[0x01]
    >>> 0x01 in block
    False

Since v3.0, there's also a convenience method to add a private tag without creating a private block first::

    >>> block = ds.add_new_private("My company 001", 0x000B, 0x01, "my value", VR.SH)
    >>> ds
    ...
    (000b, 0010) Private Creator                     LO: 'My company 001'
    (000b, 1001) Private tag data                    SH: 'my value'
    ...

Note that for known private tags you don't need to provide the VR in this function.

Removing All Private Data Elements
-----------------------------------------------

One part of anonymizing a DICOM file is to ensure that private data elements
have been removed, as there is no guarantee as to what kind of information
might be contained in them.  *pydicom* provides a convenience function
:func:`Dataset.remove_private_tags` to recursively remove private elements::

    >>> ds.remove_private_tags()

This can also be helpful during interactive sessions when exploring DICOM
files, to remove a large number of lines from the display of a dataset --
lines which may not provide useful information.

Adding new entries to the DICOM dictionary
------------------------------------------
*pydicom* contains a dictionary with all known DICOM tags from the latest DICOM standard
at release time. It also contains a dictionary with a number of known private tags
collected from various sources.
Sometimes you may encounter tags unknown to *pydicom* - either tags defined in a newer version
of the standard, or, the more common case, private tags that are not contained
in the private tags dictionary.

In this case, you can add these tags to the DICOM dictionary before reading or writing datasets
containing these tags. After that, *pydicom* will correctly handle the type of these tags, and
can display their description if needed.

For standard tags, you can use :func:`~pydicom.datadict.add_dict_entry` or
:func:`~pydicom.datadict.add_dict_entries` (to add multiple tags at once)::

    >>> add_dict_entry(tag=0x888800001, VR="SH", keyword="SomeNewTag", description="Some New Tag")

For private tags, the analogous functions are
:func:`~pydicom.datadict.add_private_dict_entry` and :func:`~pydicom.datadict.add_private_dict_entries`::

    >>> add_private_dict_entry(private_creator="ACME 1.1", tag=0x004100001, VR="DA", description="Release Date")

Note that private tags do not have a keyword, as they are not registered in the
standard DICOM data dictionary. As a private tag is defined by the tuple of private creator, group ID and tag offset,
you always have to provide the private creator to define a new private tag.

An example of how to use :func:`~pydicom.datadict.add_private_dict_entries` can
be found in :ref:`this code snippet <sphx_glr_auto_examples_metadata_processing_plot_add_dict_entries.py>`.
