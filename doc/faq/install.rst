
FAQ: Installation
=================

What are pydicom's prerequisites?
---------------------------------

*pydicom* requires Python. Other Python libraries are be required when dealing
with JPEG compressed pixel data.


What Python version can I use?
------------------------------

+-----------------+------------------+-------------------------+
| pydicom version |  Release date    | Python versions         |
+=================+==================+=========================+
| 1.0             | May 2018         | 2.7, 3.4, 3.5, 3.6      |
+-----------------+------------------+-------------------------+
| 1.1             | June 2018        | 2.7, 3.4, 3.5, 3.6      |
+-----------------+------------------+-------------------------+
| 1.2             | October 2018     | 2.7, 3.4, 3.5, 3.6      |
+-----------------+------------------+-------------------------+
| 1.3             | July 2019        | 2.7, 3.4, 3.5, 3.6      |
+-----------------+------------------+-------------------------+
| 1.4             | December 2019    | 2.7, 3.5, 3.6, 3.7, 3.8 |
+-----------------+------------------+-------------------------+
| 2.0             | April 2020       | 3.5, 3.6, 3.7, 3.8      |
+-----------------+------------------+-------------------------+

What about support for Python 2.7?
----------------------------------

Python 2.7 reaches end of life on 1st January, 2020 and will no longer be
supported by *pydicom* starting from v2.0 (expected release date is April
2020). If you absolutely require Python 2.7 then your only option is to
install v1.4::

  pip install pydicom==1.4
