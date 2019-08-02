.. _Python2_support:

Python 2 Support Plan for Pydicom
=================================

.. rubric:: Timeline of support for Python 2

The Python developers have stated that Python 2 will no longer be supported
starting Jan 1, 2020. Numpy is also dropping support for Python 2 at that time.
Pytest, which pydicom uses for testing, will support only Python 3.5+ starting
with the pytest 5.0 release, but are supporting the 4.6 version until mid 2020.

It is clear -- Python 2 will become a thing of the past starting Jan 2020.
All packages, including pydicom, need to think of transitioning away from
Python 2 and supporting only Python 3.

Pydicom code was written with common code for both Python 2.7 and Python 3 as
much as possible. Where necessary, checks for Python 2 have been used to
create small blocks of distinct code.  When the time comes, it should be
relatively easy to remove the Python 2 blocks and leave a Python-3-only
version of pydicom.

After some discussion on github, the proposed plan for pydicom and Python 2
support is as follows

* pydicom v1.3 (July 2019) - no changes to Python versions supported. Adds a
  deprecation warning (to be deprecated in v1.5) when run under Python 2
* pydicom v1.4 (planned for release ~December 2019) will support Python 2.7,
  with deprecation warning as above.
* pydicom v1.5 (planned for ~April 2020) will be Python 3.5+ only
* pydicom v1.6 (no date set) will be Python 3.6+

We may consider the possibility of backporting some fixes to pydicom v1.4 for
very serious issues, if users make the case for it.  Generally speaking,
however, we encourage all pydicom users to make the transition to Python 3 by
early 2020.
