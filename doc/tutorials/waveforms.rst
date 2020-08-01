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

.. code-block:: bash

    python -m pip install -U pydicom>=2.1 numpy matplotlib

.. code-block:: bash

    conda install pydicom>=2.1 numpy matplotlib

:dcm:`Waveform Explanatory Information<part17/chapter_C.html>`
:dcm:`Waveform Information Model<part17/sect_C.5.html>`

Waveforms in DICOM
==================

There are a number of DICOM :dcm:`Information Object Definitions
<part03/sect_A.34.html>` (IODs) that contain
waveforms, such as :dcm:`12-Lead ECG<part03/sect_A.34.3.html>`,
:dcm:`Respiratory Waveform<part03/sect_A.34.9.html>` and
:dcm:`Real-Time Audio Waveform<part03/sect_A.34.11.html>`.

The waveform information model

Every waveform IOD
uses the :dcm:`Waveform Module <part03/sect_C.10.9.html>` to represent one or
more multi-channel time-based digitized waveforms, sampled at constant time
intervals.

All waveforms within a dataset are items within the (5400,0100) *Waveform
Sequence* element:

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> fpath = get_testdata_file("waveform_ecg.dcm")
    >>> ds = dcmread(fpath)
    >>> ds.SOPClassUID.name
    '12-lead ECG Waveform Storage'
    >>> waveforms = ds.WaveformSequence
    >>> len(waveforms)
    2

Each item in the sequence is a *multiplex group*, which is a group of related
waveforms that are synchronised at common sampling frequency (in Hz).

.. code-block:: python

    >>> multiplex = waveforms[0]
    >>> multiplex.MultiplexGroupLabel
    'RHYTHM'
    >>> multiplex.SamplingFrequency
    "1000.0"
    >>> multiplex.NumberOfWaveformChannels
    12
    >>> multiplex.NumberOfWaveformSamples
    10000

So the first multiplex group has 12 channels, each with 10,000 samples. Since
the sampling frequency is 1 kHz, this represents 10 seconds of data. The
defining information for each channel is available in the (5400,0200)
*Channel Definition Sequence*:

.. code-block:: python

    >>> for ii, channel in enumerate(multiplex.ChannelDefinitionSequence):
    ...     source = channel.ChannelSourceSequence[0].CodeMeaning
    ...     units = 'unitless'
    ...     if 'ChannelSensitivity' in channel:  # Type 1C, may be absent
    ...         units = channel.ChannelSensitivityUnitsSequence[0].CodeMeaning
    ...     print(f"Channel {ii + 1}: {source} ({units})")
    ...
    Channel 1: Lead I (Einthoven) (microvolt)
    Channel 2: Lead II (microvolt)
    Channel 3: Lead III (microvolt)
    Channel 4: Lead aVR (microvolt)
    Channel 5: Lead aVL (microvolt)
    Channel 6: Lead aVF (microvolt)
    Channel 7: Lead V1 (microvolt)
    Channel 8: Lead V2 (microvolt)
    Channel 9: Lead V3 (microvolt)
    Channel 10: Lead V4 (microvolt)
    Channel 11: Lead V5 (microvolt)
    Channel 12: Lead V6 (microvolt)


Decoding *Waveform Data*
========================

The combined sample data is stored in the (5400,1010) *Waveform Data* element
within each multiplex:

.. code-block:: python

   >>> multiplex.WaveformBitsAllocated
   16
   >>> multiplex.WaveformSampleInterpretation
   'SS'
   >>> len(multiplex.WaveformData)
   240000

The data in this multiplex consists of :dcm:`signed 16-bit samples
<part03/sect_C.10.9.html#table_C.10-10>`. Waveform data is encoded with the
channels interleaved, so for our case the data is ordered as:

.. code-block:: text

    (Ch 1, Sample 1), (Ch 2, Sample 1), ..., (Ch 12, Sample 1),
    (Ch 1, Sample 2), (Ch 2, Sample 2), ..., (Ch 12, Sample 2),
    ...,
    (Ch 1, Sample 10,000), (Ch 2, Sample 10,000), ..., (Ch 12, Sample 10,000)

To decode the raw multiplex waveform data to a numpy :class:`~numpy.ndarray`
you can use the :func:`~pydicom.waveforms.numpy_handler.multiplex_array`
function:

.. code-block:: python

    >>> import matplotlib.pyplot as plt
    >>> from pydicom.waveforms import multiplex_array
    >>> raw = multiplex_array(ds, index=0, as_raw=True)
    >>> raw[0, 0]
    80

This will decode and return the raw waveforms from the multiplex at *index*
``0`` within the *Waveform Sequence*.

If (003A,0210) *Channel Sensitivity* is present within the multiplex's *Channel
Definition Sequence* then the raw sample data needs to be corrected before it's
in the quantity it represents. The correction is given by (sample + *Channel
Baseline*) x *Channel Sensitivity* x *Channel Sensitivity Correction Factor*
and will be applied when `as_raw` is ``False`` or when using the
:meth:`Dataset.waveform_array<pydicom.dataset.Dataset.waveform_array>`
function:

    >>> arr = ds.waveform_array(index=0)
    >>> arr[0, 0]
    >>> 100.0
    >>> fig, (ax1, ax2) = plt.subplots(2)
    >>> ax1.plot(raw[:, 0])
    >>> ax1.set_ylabel("unitless")
    >>> ax2.plot(arr[:, 0])
    >>> ax2.set_ylabel("μV")
    >>> fig.show()


When processing large amounts of waveform data it might be useful to use the
:func:`~pydicom.waveforms.numpy_handler.generate_multiplex` function instead,
as it yields an :class:`~numpy.ndarray` for each multiplex group within the
*Waveform Sequence*:

.. code-block:: python

    >>> from pydicom.waveforms import generate_multiplex
    >>> for arr in generate_multiplex(ds, as_raw=False):
    ...     print(arr.shape)
    ...
    (10000, 12)
    (1200, 12)


Encoding *Waveform Data*
========================

group -> 2 channels -> numpy int16 sin and cosine waves -> encode
