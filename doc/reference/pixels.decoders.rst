.. _api_decoders:

Pixel Data Decoders (:mod:`pydicom.pixels.decoders`)
====================================================

.. module:: pydicom.pixels.decoders

:class:`~pydicom.pixels.decoders.base.Decoder` class instances for decoding
native and compressed (7FE0,0010) *Pixel Data*, (7FE0,0008) *Float Pixel Data* and
(7FE0,0009) *Double Float Pixel Data*.

.. currentmodule:: pydicom.pixels.decoders

.. autosummary::
   :toctree: generated/

   ExplicitVRLittleEndianDecoder
   ImplicitVRLittleEndianDecoder
   DeflatedExplicitVRLittleEndianDecoder
   ExplicitVRBigEndianDecoder
   JPEGBaseline8BitDecoder
   JPEGExtended12BitDecoder
   JPEGLosslessDecoder
   JPEGLosslessSV1Decoder
   JPEGLSLosslessDecoder
   JPEGLSNearLosslessDecoder
   JPEG2000LosslessDecoder
   JPEG2000Decoder
   HTJ2KLosslessDecoder
   HTJ2KLosslessRPCLDecoder
   HTJ2KDecoder
   RLELosslessDecoder


Base decoder classes used by all decoders

.. currentmodule:: pydicom.pixels.decoders.base

.. autosummary::
   :toctree: generated/

   DecodeRunner
   Decoder
