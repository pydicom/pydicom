.. _viewing_images:

Viewing Images
==============

.. rubric:: How to use other packages with pydicom to view DICOM images

Introduction
------------

*pydicom* is mainly concerned with getting at the DICOM data elements in files,
but it is often desirable to view pixel data as an image.
There are several options:

* Use any of the many `DICOM viewer
  <http://www.dclunie.com/medical-image-faq/html/part8.html#DICOMFileConvertorsAndViewers>`_
  programs available
* use pydicom with `matplotlib <https://matplotlib.org/>`_
* use pydicom with Python's stdlib `Tkinter <https://docs.python.org/3.4/library/tkinter.html>`_ module.
* use pydicom with `Pillow <https://python-pillow.org/>`_
* use pydicom with `wxPython <https://www.wxpython.org/>`_

Using pydicom with matplotlib
-----------------------------

`matplotlib <https://matplotlib.org/>`_ can be used with the :class:`numpy.ndarray` from
:attr:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>` to display it::

  >>> import matplotlib.pyplot as plt
  >>> from pydicom import examples
  >>> ds = examples.ct
  >>> plt.imshow(ds.pixel_array, cmap=plt.cm.bone) # doctest: +ELLIPSIS
  <matplotlib.image.AxesImage object at ...>

.. image:: ./../../auto_examples/input_output/images/sphx_glr_plot_read_dicom_001.png
   :target: ./../../auto_examples/input_output/plot_printing_dataset.html
   :scale: 60
   :align: center

Using pydicom with Tkinter
--------------------------

The program :gh:`pydicom_Tkinter.py
<contrib-pydicom/blob/master/viewers/pydicom_Tkinter.py>`
in the ``contrib-pydicom`` repository demonstrates how to show an image using the
Tkinter graphics system, which comes by default with most Python installations.
It creates a Tkinter PhotoImage in a Label widget or a user-supplied widget.

Using pydicom with Python Imaging Library (PIL)
-----------------------------------------------

The module :gh:`pydicom_PIL.py <contrib-pydicom/blob/master/viewers/pydicom_PIL.py>`
in the ``contrib-pydicom`` repository uses PIL's ``Image.show()`` method after
creating an Image instance from the pixel data and some basic information
about it (bit depth, LUTs, etc).

Using pydicom with wxPython
---------------------------

The module :gh:`imViewer-Simple.py <contrib-pydicom/blob/master/viewers/imViewer_Simple.py>`
in the ``contrib-pydicom`` repository uses wxPython (also PIL, but it notes that it
may not be strictly necessary) to display an image from a pydicom dataset.
