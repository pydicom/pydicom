.. _guide_decoder_plugin_opts:

=======================
Decoder Plugins Options
=======================

.. currentmodule:: pydicom.pixels.decoders.base


.. _decoder_plugin_pydicom:

pydicom
=======

+--------------------------+------------------------------------------------------------------------+
| Decoder                  | Options                                                                |
+                          +-----------------------+------------------------------------------------+
|                          | Key                   | Value                                          |
+==========================+=======================+================================================+
|:attr:`RLELosslessDecoder`| ``rle_segment_order`` | ``">"`` for big endian segment order (default) |
|                          |                       | or ``"<"`` for little endian segment order     |
+--------------------------+-----------------------+------------------------------------------------+
