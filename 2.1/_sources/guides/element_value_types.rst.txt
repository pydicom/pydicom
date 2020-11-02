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
* To ensure **AT** elements are encoded correctly, their values should be set
  using the 8-byte integer form of the tag - such as ``0x00100020`` for the tag
  (0010,0020) - and not as a 2-tuple or 2-list.


+----+------------------+-----------------+-----------------------------------+
| VR | Name             | Set using       | Stored as                         |
+====+==================+=================+===================================+
| AE | Application      | :class:`str`    | :class:`str`                      |
|    | Entity           |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| AS | Age String       | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| AT | Attribute Tag    | :class:`int`    | :class:`int`                      |
+----+------------------+-----------------+-----------------------------------+
| CS | Code String      | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| DA | Date             | :class:`str`    | :class:`str` or                   |
|    |                  |                 | :class:`~valuerep.DA`\ :sup:`1`   |
+----+------------------+-----------------+-----------------------------------+
| DS | Decimal String   | :class:`str`,   | :class:`~valuerep.DSfloat` or     |
|    |                  | :class:`float`  | :class:`~valuerep.DSdecimal`\     |
|    |                  | or :class:`int` | :sup:`2`                          |
+----+------------------+-----------------+-----------------------------------+
| DT | Date Time        | :class:`str`    | :class:`str` or                   |
|    |                  |                 | :class:`~valuerep.DT`\ :sup:`1`   |
+----+------------------+-----------------+-----------------------------------+
| FL | Floating Point   | :class:`float`  | :class:`float`                    |
|    | Single           |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| FD | Floating Point   | :class:`float`  | :class:`float`                    |
|    | Double           |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| IS | Integer String   | :class:`str`    | :class:`~valuerep.IS`             |
|    |                  | or :class:`int` |                                   |
+----+------------------+-----------------+-----------------------------------+
| LO | Long String      | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| LT | Long Text        | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| OB | Other Byte       | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| OD | Other Double     | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| OF | Other Float      | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| OL | Other Long       | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| OV | Other 64-bit     | :class:`bytes`  | :class:`bytes`                    |
|    | Very Long        |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| OW | Other Word       | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| PN | Person Name      | :class:`str`    | :class:`~valuerep.PersonName`     |
+----+------------------+-----------------+-----------------------------------+
| SH | Short String     | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| SL | Signed Long      | :class:`int`    | :class:`int`                      |
+----+------------------+-----------------+-----------------------------------+
| SQ | Sequence of      | :class:`list`   | :class:`~sequence.Sequence`       |
|    | Items            |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| SS | Signed Short     | :class:`int`    | :class:`int`                      |
+----+------------------+-----------------+-----------------------------------+
| ST | Short Text       | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| SV | Signed 64-bit    | :class:`int`    | :class:`int`                      |
|    | Very Long        |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| TM | Time             | :class:`str`    | :class:`str` or                   |
|    |                  |                 | :class:`~valuerep.TM`\ :sup:`1`   |
+----+------------------+-----------------+-----------------------------------+
| UC | Unlimited        | :class:`str`    | :class:`str`                      |
|    | Characters       |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| UI | Unique           | :class:`str`    | :class:`~uid.UID`                 |
|    | Identifier (UID) |                 |                                   |
+----+------------------+-----------------+-----------------------------------+
| UL | Unsigned Long    | :class:`int`    | :class:`int`                      |
+----+------------------+-----------------+-----------------------------------+
| UN | Unknown          | :class:`bytes`  | :class:`bytes`                    |
+----+------------------+-----------------+-----------------------------------+
| UR | URI/URL          | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| US | Unsigned Short   | :class:`int`    | :class:`int`                      |
+----+------------------+-----------------+-----------------------------------+
| UT | Unlimited Text   | :class:`str`    | :class:`str`                      |
+----+------------------+-----------------+-----------------------------------+
| UV | Unsigned 64-bit  | :class:`int`    | :class:`int`                      |
|    | Very Long        |                 |                                   |
+----+------------------+-----------------+-----------------------------------+

| :sup:`1` If :attr:`config.datetime_conversion<config.datetime_conversion>`
  = ``True`` (default ``False``)
| :sup:`2` If :attr:`config.use_DS_decimal<config.use_DS_decimal>`
  = ``True`` (default ``False``)
