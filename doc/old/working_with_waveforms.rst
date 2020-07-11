.. _working_with_waveform_data:
.. title:: Working with Waveform Data

Working with Waveform Data
==========================

.. currentmodule:: pydicom

.. rubric:: How to work with waveform data in pydicom.

Introduction
------------

Some DICOM SOP classes such as :dcm:`Basic Voice Audio Waveform
<part03/sect_A.34.2.html>` and :dcm:`12-Lead ECG<part03/sect_A.34.3.html>`
contain a (5400,0100) *Waveform Sequence* element,
where each item in the sequence is a related group of waveforms (a multiplex).
The requirements of the sequence is given by the :dcm:`Waveform
module <part03/sect_C.10.9.html>` in Part 3, Annex C.10.9 of the DICOM
Standard.

Each multiplex consists of one or more channels synchronised at a
common sampling frequency (in Hz), which is given by the (003A,001A) *Sampling
Frequency*. The waveform data for each multiplex is encoded in the
corresponding (5400,1010) *Waveform Data* element.

>>> from pydicom import dcmread
>>> from pydicom.data import get_testdata_file
>>> fpath = get_testdata_file("waveform_ecg.dcm")
>>> ds = dcmread(fpath)
>>> ds.WaveformSequence
<Sequence, length 2>
>>> multiplex = ds.WaveformSequence[0]
>>> multiplex.NumberOfWaveformChannels
12
>>> multiplex.SamplingFrequency
"1000.0"
>>> multiplex['WaveformData']
(5400, 1010) Waveform Data                       OW: Array of 240000 elements


``Dataset.waveform_generator``
------------------------------

.. warning::

   :attr:`Dataset.waveform_generator
   <pydicom.dataset.Dataset.waveform_generator>` requires `NumPy
   <http://numpy.org/>`_.

The *Waveform Data* element contains the raw bytes exactly as found in the
file. To get the waveforms in a more useful form you can use the
:attr:`~pydicom.dataset.Dataset.waveform_generator` property to return a
`generator object
<https://docs.python.org/3/glossary.html#term-generator-iterator>`_ that yields
a :class:`numpy.ndarray` with shape (samples, channels) for each multiplex
group in the *Waveform Sequence*.

  >>> generator = ds.waveform_generator
  >>> multiplex_1 = next(generator)
  >>> multiplex_1
  array([[  80,   90,   10, ...,  -20,  -55,  -40],
         [  65,   85,   20, ...,  -20,  -60,  -40],
         [  50,   80,   30, ...,  -20,  -65,  -40],
         ...,
         [  20,  105,   85, ..., -110, -120,  -80],
         [  17,  110,   93, ..., -110, -120,  -85],
         [  20,  110,   90, ..., -110, -120,  -90]], dtype=float)
  >>> multiplex_1.shape
  (10000, 12)
  >>> multiplex_2 = next(generator)
  >>> multiplex_2.shape
  (1200, 12)
  >>> next(generator)
  Traceback (most recent call last):
    File "<stdin>", line 1, in <module>
  StopIteration

If the *Channel Sensitivity Correction Factor* is available for a given channel
then it will be applied to the raw channel data. If you need the raw data
without any corrections then you can use the
:func:`~pydicom.waveform_data_handlers.numpy_handler.generate_multiplex`
function with the *as_raw* keyword parameter instead:

  >>> from pydicom.waveform_generator.numpy_handler import generate_multiplex
  >>> generator = generate_multiplex(ds, as_raw=True)
