============================
Element VRs and Python types
============================

.. currentmodule:: pydicom

DICOM elements can contain anything from strings to unicode text, decimals,
floats, signed and unsigned integers of different byte-depth and even raw
bytes. The format of the value of an element is given by its **Value
Representation** or VR. A list of VRs is given in the DICOM Standard in Part 5,
:dcm:`Table 6.2-1 <part05/sect_6.2.html#table_6.2-1>`.

The question, then, is what Python type should be used with a given VR? When
using pydicom, all element values can be set using a standard Python built-in
type, which is either retained as-is or converted to a pydicom type as given
in the table below.

**Notes**

* All element values can be set empty by using ``None``
* All element values can also be set using their *stored as* type
* All non-**SQ** element values can also be set using a :class:`list` of
  their *set using* type
* All non-**SQ** elements with a Value Multiplicity (VM) > 1 store their values
  as a :class:`~multival.MultiValue` of their *stored as* type
* **AT** element values should be set using the 8-byte integer form of the tag
  such as ``0x00100010`` or a list of 8-byte integers for VM > 1.

+----+------------------+-----------------+-------------------------------------------------+
| VR | Name             | Set using       | Stored as                                       |
+====+==================+=================+=================================================+
| AE | Application      | :class:`str`    | :class:`str`                                    |
|    | Entity           |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| AS | Age String       | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| AT | Attribute Tag    | :class:`int`    | :class:`int`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| CS | Code String      | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| DA | Date             | :class:`str`    | :class:`str` or :class:`~valuerep.DA`\ :sup:`1` |
+----+------------------+-----------------+-------------------------------------------------+
| DS | Decimal String   | :class:`str`,   | :class:`~valuerep.DSfloat` or                   |
|    |                  | :class:`float`, | :class:`~valuerep.DSdecimal`\ :sup:`2`          |
|    |                  | :class:`int`    |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| DT | Date Time        | :class:`str`    | :class:`str` or :class:`~valuerep.DT`\ :sup:`1` |
+----+------------------+-----------------+-------------------------------------------------+
| FL | Floating Point   | :class:`float`  | :class:`float`                                  |
|    | Single           |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| FD | Floating Point   | :class:`float`  | :class:`float`                                  |
|    | Double           |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| IS | Integer String   | :class:`str`,   | :class:`~valuerep.IS`                           |
|    |                  | :class:`int`    |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| LO | Long String      | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| LT | Long Text        | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| OB | Other Byte       | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| OD | Other Double     | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| OF | Other Float      | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| OL | Other Long       | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| OV | Other 64-bit     | :class:`bytes`  | :class:`bytes`                                  |
|    | Very Long        |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| OW | Other Word       | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| PN | Person Name      | :class:`str`    | :class:`str` (Python 2)                         |
|    |                  |                 | or :class:`~valuerep.PersonName3` (Python 3)    |
+----+------------------+-----------------+-------------------------------------------------+
| SH | Short String     | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| SL | Signed Long      | :class:`int`    | :class:`int`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| SQ | Sequence of      | :class:`list`   | :class:`~sequence.Sequence`                     |
|    | Items            |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| SS | Signed Short     | :class:`int`    | :class:`int`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| ST | Short Text       | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| SV | Signed 64-bit    | :class:`int`    | :class:`int`                                    |
|    | Very Long        |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| TM | Time             | :class:`str`    | :class:`str` or :class:`~valuerep.TM`\ :sup:`1` |
+----+------------------+-----------------+-------------------------------------------------+
| UC | Unlimited        | :class:`str`    | :class:`str`                                    |
|    | Characters       |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| UI | Unique           | :class:`str`    | :class:`~uid.UID`                               |
|    | Identifier (UID) |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+
| UL | Unsigned Long    | :class:`int`    | :class:`int`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| UN | Unknown          | :class:`bytes`  | :class:`bytes`                                  |
+----+------------------+-----------------+-------------------------------------------------+
| UR | URI/URL          | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| US | Unsigned Short   | :class:`int`    | :class:`int`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| UT | Unlimited Text   | :class:`str`    | :class:`str`                                    |
+----+------------------+-----------------+-------------------------------------------------+
| UV | Unsigned 64-bit  | :class:`int`    | :class:`int`                                    |
|    | Very Long        |                 |                                                 |
+----+------------------+-----------------+-------------------------------------------------+

| :sup:`1` If :attr:`config.datetime_conversion<config.datetime_conversion>`
  = ``True`` (default ``False``)
| :sup:`2` If :attr:`config.use_DS_decimal<config.use_DS_decimal>`
  = ``True`` (default ``False``)
