============================
Element VRs and Python types
============================

.. currentmodule:: pydicom

DICOM elements can contain anything from ASCII strings to unicode text,
decimals, floats, signed and unsigned integers of different byte-depth and
even encoded data. The format of the value of an element is given by its
:dcm:`Value Representation<part05/sect_6.2.html>` or VR, and a list of VRs is
given in the DICOM Standard in Part 5,
:dcm:`Table 6.2-1 <part05/sect_6.2.html#table_6.2-1>`.

So when using *pydicom*, what Python type should be used with a given VR to
ensure that the value gets written correctly?

* Elements of any VR:

  * Can be set as empty by using ``None``
  * Can have their values set using their *set using* or *stored as* type from
    the table below

* Non-**SQ** element values:

  * Can also be set using a :class:`list` of their *set using* type - for
    :dcm:`Value Multiplicity<part05/sect_6.4.html>` (VM) > 1, the value will
    be stored as a :class:`~multival.MultiValue` of their *stored as* type
  * However, according to the DICOM Standard, elements with VR **LT**, **OB**,
    **OD**, **OF**, **OL**, **OW**, **ST**, **UN**, **UR** and **UT** should
    never have a VM greater than 1.

* **SQ** element values should be set using a :class:`list` of zero or more
  :class:`~dataset.Dataset` instances.


+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| VR | Name             | Set using                  | Stored as (T)                     | Type hint for element value |
+====+==================+============================+===================================+=============================+
| AE | Application      | :class:`str`               | :class:`str`                      | None | T |                  |
|    | Entity           |                            |                                   | MutableSequence[T]          |
+----+------------------+----------------------------+-----------------------------------+                             |
| AS | Age String       | :class:`str`               | :class:`str`                      |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| AT | Attribute Tag    | Tag\ :sup:`1`              | :class:`~tag.BaseTag`             |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| CS | Code String      | :class:`str`               | :class:`str`                      |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| DA | Date             | :class:`str`               | :class:`str` or                   |                             |
|    |                  |                            | :class:`~valuerep.DA`\ :sup:`2`   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| DS | Decimal String   | :class:`str`,              | :class:`~valuerep.DSfloat` or     |                             |
|    |                  | :class:`float`             | :class:`~valuerep.DSdecimal`\     |                             |
|    |                  | or :class:`int`            | :sup:`3`                          |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| DT | Date Time        | :class:`str`               | :class:`str` or                   |                             |
|    |                  |                            | :class:`~valuerep.DT`\ :sup:`2`   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| FL | Floating Point   | :class:`float`             | :class:`float`                    |                             |
|    | Single           |                            |                                   |                             |
+----+------------------+                            |                                   |                             |
| FD | Floating Point   |                            |                                   |                             |
|    | Double           |                            |                                   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| IS | Integer String   | :class:`str`               | :class:`~valuerep.IS`             |                             |
|    |                  | or :class:`int`            |                                   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| LO | Long String      | :class:`str`               | :class:`str`                      |                             |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| LT | Long Text        | :class:`str`               | :class:`str`                      | None | T                    |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| OB | Other Byte       | :class:`bytes` or          | :class:`bytes` or                 | None | T                    |
+----+------------------+ :class:`io.BufferedIOBase` | :class:`io.BufferedIOBase`        |                             |
| OD | Other Double     | \ :sup:`4`                 |                                   |                             |
+----+------------------+                            |                                   |                             |
| OF | Other Float      |                            |                                   |                             |
+----+------------------+                            |                                   |                             |
| OL | Other Long       |                            |                                   |                             |
+----+------------------+                            |                                   |                             |
| OV | Other 64-bit     |                            |                                   |                             |
|    | Very Long        |                            |                                   |                             |
+----+------------------+                            |                                   |                             |
| OW | Other Word       |                            |                                   |                             |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| PN | Person Name      | :class:`str`               | :class:`~valuerep.PersonName`     | None | T |                  |
+----+------------------+----------------------------+-----------------------------------+ MutableSequence[T]          |
| SH | Short String     | :class:`str`               | :class:`str`                      |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| SL | Signed Long      | :class:`int`               | :class:`int`                      |                             |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| SQ | Sequence of      | :class:`list`              | :class:`~sequence.Sequence`       | MutableSequence[            |
|    | Items            |                            |                                   | :class:`~dataset.Dataset`]  |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| SS | Signed Short     | :class:`int`               | :class:`int`                      | None | T |                  |
|    |                  |                            |                                   | MutableSequence[T]          |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| ST | Short Text       | :class:`str`               | :class:`str`                      | None | T                    |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| SV | Signed 64-bit    | :class:`int`               | :class:`int`                      | None | T |                  |
|    | Very Long        |                            |                                   | MutableSequence[T]          |
+----+------------------+----------------------------+-----------------------------------+                             |
| TM | Time             | :class:`str`               | :class:`str` or                   |                             |
|    |                  |                            | :class:`~valuerep.TM`\ :sup:`2`   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| UC | Unlimited        | :class:`str`               | :class:`str`                      |                             |
|    | Characters       |                            |                                   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| UI | Unique           | :class:`str`               | :class:`~uid.UID`                 |                             |
|    | Identifier (UID) |                            |                                   |                             |
+----+------------------+----------------------------+-----------------------------------+                             |
| UL | Unsigned Long    | :class:`int`               | :class:`int`                      |                             |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| UN | Unknown          | :class:`bytes`             | :class:`bytes`                    | None | T                    |
+----+------------------+----------------------------+-----------------------------------+                             |
| UR | URI/URL          | :class:`str`               | :class:`str`                      |                             |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| US | Unsigned Short   | :class:`int`               | :class:`int`                      | None | T |                  |
|    |                  |                            |                                   | MutableSequence[T]          |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| UT | Unlimited Text   | :class:`str`               | :class:`str`                      | None | T                    |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+
| UV | Unsigned 64-bit  | :class:`int`               | :class:`int`                      | None | T |                  |
|    | Very Long        |                            |                                   | MutableSequence[T]          |
+----+------------------+----------------------------+-----------------------------------+-----------------------------+

| :sup:`1` Any type accepted by :func:`~tag.Tag` can be used
| :sup:`2` If :attr:`config.datetime_conversion<config.datetime_conversion>`
  = ``True`` (default ``False``)
| :sup:`3` If :attr:`config.use_DS_decimal<config.use_DS_decimal>`
  = ``True`` (default ``False``)
| :sup:`4` See notes for bufferable O* VRs below


Bufferable O* VRs
-----------------

The value for elements with O\* VRs (**OB**, **OD**, **OF**, **OL**, **OV** and
**OW**) can be set using an object that inherits from :class:`io.BufferedIOBase` such
as the :class:`io.BufferedReader` instances returned by the :func:`open` built-in when
in read mode. This allows you to avoid having to read a large amount of data into
memory when creating datasets::

    from pydicom import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    with open("a_large_amount_of_data", "rb") as f:
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.PixelData = f
        ds.save_as("large_dataset.dcm")

To use a buffered *Pixel Data* value with a dataset that has a compressed transfer
syntax such as *JPEG 2000 Lossles*, the :func:`~pydicom.encaps.encapsulate_buffer` and
:func:`~pydicom.encaps.encapsulate_extended_buffer` functions can be used to encapsulate
the buffered frames::

    from pydicom import Dataset, FileMetaDataset
    from pydicom.encaps import encapsulate_buffer
    from pydicom.uid import JPEG2000Lossless

    with open("a_large_jpeg2000_file.j2k", "rb") as f:
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = JPEG2000Lossless
        ds.PixelData = encapsulate_buffer([f])
        ds.save_as("large_compressed_dataset.dcm")

However, be aware that Datasets containing buffered objects that don't normally work
with :mod:`pickle` or :func:`~copy.deepcopy` such as
:class:`~io.BufferedReader` are not able to be pickled or deepcopied.
