=========
Waveforms
=========

This tutorial is about understanding waveforms in DICOM datasets and covers:

* An introduction to DICOM waveforms
* Decoding and displaying *Waveform Data*
* Encoding *Waveform Data*

It's assumed that you're already familiar with the :doc:`dataset basics
<dataset_basics>`.

Pre-requisites
--------------

* `pydicom <https://github.com/pydicom/pydicom>`_ >= v2.1
* `numpy <https://numpy.org/>`_
* `matplotlib <https://matplotlib.org/>`_


Waveforms in DICOM
==================

:dcm:`Waveform IODs<part03/sect_A.34.html>`
:dcm:`Waveform Module<part03/sect_C.10.9.html>`
:dcm:`Waveform Explanatory Information<part17/chapter_C.html>`
:dcm:`Waveform Information Model<part17/sect_C.5.html>`



.. code-block:: python

    from pydicom import dcmread
    from pydicom.data import get_testdata_file

    fpath = get_testdata_file("waveform_ecg.dcm")
    ds = dcmread(fpath)


Decoding *Waveform Data*
========================

.. code-block:: python

.. code-block:: python

    from pydicom import dcmread
    from pydicom.data import get_testdata_file

    fpath = get_testdata_file("waveform_ecg.dcm")
    ds = dcmread(fpath)

    generator = ds.waveform_generator
    arr = next(generator)

    plt.plot(arr[..., 0])
    plt.show()


If you need the raw data you can use the
:func:`~pydicom.waveforms.numpy_handler.generate_multiplex` function with the
*as_raw* parameter:

.. code-block:: python

    from pydicom.waveform_data_handlers import generate_multiplex

    generator = generate_multiplex(ds, as_raw=True)
    arr = next(generator)

On the other hand, if you only need a specific waveform:

.. code-block:: python

    from pydicom.waveform import multiplex_array


Encoding *Waveform Data*
========================

group -> 2 channels -> numpy int16 sin and cosine waves -> encode
