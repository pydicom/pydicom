.. _api_examples:

Example Datasets (:mod:`pydicom.examples`)
==========================================

.. module:: pydicom.examples
.. currentmodule:: pydicom.examples

The ``examples`` module contains the following DICOM datasets:

+-------------------+---------------------------------------+----------------------+
| Module Attribute  | File                                  | SOP Class            |
+===================+=======================================+======================+
| ``ct``            | ``CT_small.dcm``                      | CT Image             |
+-------------------+---------------------------------------+----------------------+
| ``mr``            | ``MR_small.dcm``                      | MR Image             |
+-------------------+---------------------------------------+----------------------+
| ``rt_plan``       | ``rtplan.dcm``                        | RT Plan              |
+-------------------+---------------------------------------+----------------------+
| ``rt_dose``       | ``rtdose.dcm``                        | RT Dose              |
+-------------------+---------------------------------------+----------------------+
| ``rt_ss``         | ``rtstruct.dcm``                      | RT Structure Set     |
+-------------------+---------------------------------------+----------------------+
| ``overlay``       | ``MR-SIEMENS-DICOM-WithOverlays.dcm`` | MR Image             |
+-------------------+---------------------------------------+----------------------+
| ``waveform``      | ``waveform_ecg.dcm``                  | 12 Lead ECG          |
+-------------------+---------------------------------------+----------------------+
| ``rgb_color``     | ``US1_UNCR.dcm``                      | US Image             |
+-------------------+---------------------------------------+----------------------+
| ``palette_color`` | ``OBXXXX1A.dcm``                      | US Image             |
+-------------------+---------------------------------------+----------------------+
| ``ybr_color``     | ``color3d_jpeg_baseline.dcm``         | US Multi-frame Image |
+-------------------+---------------------------------------+----------------------+
| ``jpeg2k``        | ``US1_J2KR.dcm``                      | US Image             |
+-------------------+---------------------------------------+----------------------+
| ``dicomdir``      | ``DICOMDIR``                          | Media Storage        |
+-------------------+---------------------------------------+----------------------+


As well as the utility function:

.. autosummary::
   :toctree: generated/

   get_path


Usage
-----

The module attributes are all normal :class:`~pydicom.dataset.FileDataset`
instances::

  >>> from pydicom import examples
  >>> type(examples.ct)
  <class 'pydicom.dataset.FileDataset'>
  >>> examples.ct.PatientName
  'CompressedSamples^CT1'

Each time the module attribute is accessed a new
:class:`~pydicom.dataset.FileDataset` instance  of the dataset will be returned::

  >>> examples.ct is examples.ct
  False
  >>> examples.ct == examples.ct
  True

Because of this, best practice is to assign the returned dataset to a local
variable::

   >>> ds = examples.ct

The :func:`~pydicom.examples.get_path` function can be used to return the path
to an example dataset as a :class:`pathlib.Path` instance::

   >>> examples.get_path("ct")
   PosixPath('/home/user/pydicom/src/pydicom/data/test_files/CT_small.dcm')
