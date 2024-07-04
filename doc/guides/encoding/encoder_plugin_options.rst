.. _guide_encoder_plugin_opts:

=======================
Encoder Plugins Options
=======================

.. currentmodule:: pydicom.pixels.encoders


.. _encoder_plugin_pydicom:

pydicom
=======

+--------------------------+----------+--------+-------------+
| Encoder                  | Options                         |
+                          +----------+--------+-------------+
|                          | Key      | Value  | Description |
+==========================+==========+========+=============+
|:attr:`RLELosslessEncoder`| (none available)                |
+--------------------------+----------+--------+-------------+

.. _encoder_plugin_gdcm:

gdcm
=====

+--------------------------+----------+--------+-------------+
| Encoder                  | Options                         |
+                          +----------+--------+-------------+
|                          | Key      | Value  | Description |
+==========================+==========+========+=============+
|:attr:`RLELosslessEncoder`| (none available)                |
+--------------------------+----------+--------+-------------+


.. _encoder_plugin_pylibjpeg:

pylibjpeg
=========

+--------------------------------+----------------------------+-------------+-------------------------------+
| Encoder                        | Options                                                                  |
+                                +----------------------------+-------------+-------------------------------+
|                                | Key                        | Value       | Description                   |
+================================+============================+=============+===============================+
|:attr:`JPEG2000LosslessEncoder` | ``'use_mct'``              | bool        | Enable MCT for RGB pixel data |
|                                |                            |             | (default ``True``)            |
+--------------------------------+----------------------------+-------------+-------------------------------+
|:attr:`JPEG2000Encoder`         | ``'use_mct'``              | bool        | Enable MCT for RGB pixel data |
|                                |                            |             | (default ``True``)            |
|                                +----------------------------+-------------+-------------------------------+
|                                | ``compression_ratios``     | list[float] | The compression ratio for     |
|                                |                            |             | each quality layer            |
|                                +----------------------------+-------------+-------------------------------+
|                                | ``signal_to_noise_ratios`` | list[float] | The peak signal-to-noise      |
|                                |                            |             | ratio for each quality layer  |
+--------------------------------+----------------------------+-------------+-------------------------------+
|:attr:`RLELosslessEncoder`      | ``'byteorder'``            | ``'<'``,    | The byte order of `src` may   |
|                                |                            | ``'>'``     | be little- or big-endian      |
+--------------------------------+----------------------------+-------------+-------------------------------+

.. _encoder_plugin_pyjpegls:

pyjpegls
========

+---------------------------------+-----------------------+--------+-------------------------------------------------+
| Encoder                         | Options                                                                          |
+                                 +-----------------------+--------+-------------------------------------------------+
|                                 | Key                   | Value  | Description                                     |
+=================================+=======================+========+=================================================+
|:attr:`JPEGLSLosslessEncoder`    | ``'interleave_mode'`` | int    | The interleave mode used by the image data, 0   |
|                                 |                       |        | for color-by-plane, 2 for color-by-pixel        |
+---------------------------------+-----------------------+--------+-------------------------------------------------+
|:attr:`JPEGLSNearLosslessEncoder`| ``'lossy_error'``     | int    | The absolute error in pixel intensity units     |
|                                 +-----------------------+--------+-------------------------------------------------+
|                                 | ``'interleave_mode'`` | int    | The interleave mode used by the image data, 0   |
|                                 |                       |        | for color-by-plane, 2 for color-by-pixel        |
+---------------------------------+-----------------------+--------+-------------------------------------------------+
