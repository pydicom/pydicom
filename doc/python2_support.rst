.. _python2_support:

Python 2 Support Plan for Pydicom
=================================

.. rubric:: Timeline of support for python 2

The python developers have stated that Python 2 will no longer be supported starting Jan 1, 2020.
Numpy is also dropping support for python 2 at that time. Pytest, which pydicom uses for testing,
will support only python 3.5+
starting with the pytest 5.0 release, but are supporting the 4.6 version until mid 2020.

It is clear -- python 2 will become a thing of the past starting Jan 2020.
All packages, including pydicom, need to think of transitioning away from python 2 and
supporting only python 3.

Pydicom code was written with common code for both python 2.7 and python 3 as much as possible.
Where necessary, checks for python 2 have been used to create small blocks of distinct
code.  When the time comes, it should be relatively easy to remove the python 2 blocks and leave
a python-3-only version of pydicom.

After some discusion on github, the proposed plan for pydicom and python 2 support is as follows

* pydicom v1.3 (July 2019) - no changes to python versions supported. Adds a deprecation
  warning (to be deprecated in v1.5) when run under python 2

* pydicom v1.4 (planned for release in December 2019) will support python 2.7,
  with deprecation warning as above.

* pydicom v1.5 (planned for ~April 2020) officially will not support python 2.7,
  but no compatibility code will be removed from pydicom; it will include a stronger 
  'deprecated' (past tense) message.  It will not install using pip, but those who
  choose to do so could download and install themselves; however, we make no guarantees
  that it will function correctly.

* pydicom v1.6 (no date set) will remove python 2 code from pydicom, and officially
  drop python 3.4 support as well. Any new pydicom code afterwards can target
  python 3.5+ features. 

We may consider the possibility of backporting some fixes to pydicom v1.4 for very serious issues,
if users make the case for it.  Generally speaking, however, we encourage all pydicom users to make
the transition to python 3 by early 2020.
