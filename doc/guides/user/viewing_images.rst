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
  >>> plt.imshow(ds.pixel_array, cmap=plt.cm.gray) # doctest: +ELLIPSIS
  <matplotlib.image.AxesImage object at ...>

.. image:: ./../../auto_examples/input_output/images/sphx_glr_plot_read_dicom_001.png
   :target: ./../../auto_examples/input_output/plot_printing_dataset.html
   :scale: 60
   :align: center
