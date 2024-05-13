"""Tests for encoding pixel data with pyjpegls."""

import importlib

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import Dataset, examples
from pydicom.encaps import encapsulate, get_frame
from pydicom.pixels.encoders import (
    JPEGLSLosslessEncoder,
    JPEGLSNearLosslessEncoder,
)
from pydicom.pixels.decoders import (
    JPEGLSLosslessDecoder,
    JPEGLSNearLosslessDecoder,
)
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.utils import _get_jpg_parameters
from pydicom.uid import JPEGLSLossless, JPEGLSNearLossless
from pydicom.pixel_data_handlers.gdcm_handler import get_pixeldata


HAVE_JLS = bool(importlib.util.find_spec("jpeg_ls"))
HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_GDCM = bool(importlib.util.find_spec("gdcm"))

SKIP_TEST = not (HAVE_NP and HAVE_JLS)


@pytest.mark.skipif(SKIP_TEST, reason="Missing required dependencies")
class TestJpegLSLossless:
    """Tests for JPEGLSLosslessEncoder with pyjpegls."""

    def setup_method(self):
        ds = examples.ct
        arr = ds.pixel_array

        # Rescale to (0, 1)
        arr = arr.astype("float32")
        arr -= arr.min()
        arr /= arr.max()
        self.ref = arr

        ds = examples.rgb_color
        arr = ds.pixel_array

        arr = arr.astype("float32")
        arr -= arr.min()
        arr /= arr.max()
        self.ref3 = arr

    def test_arr_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # CharLS can't encode 16-bits allocated with bits stored less than 9
        #   the container size has to match the sample depth
        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_i1_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-128, 127)
            ref = ref.astype("int8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-(2**15), 2**15 - 1)
            ref = ref.astype("int16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # CharLS can't encode 16-bits allocated with bits stored less than 9
        #   the container size has to match the sample depth
        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 6

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_i1_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 8,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-128, 127)
            ref = ref.astype("int8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-(2**15), 2**15 - 1)
            ref = ref.astype("int16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEGLSLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored in (6, 7):
                    continue

                out, _ = JPEGLSLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_jls_error_raises(self):
        """Test 'jls_error' is ignored if using JPEG-LS Lossless"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "jls_error": 127,
        }

        ref = self.ref * (2**8 - 1)
        ref = ref.clip(0, 255)
        ref = ref.astype("uint8")

        msg = (
            "Unable to encode as exceptions were raised by all available plugins:\n  "
            "pyjpegls: A 'jls_error' value of '127' is being used with a "
            "transfer syntax of 'JPEG-LS Lossless' - did you mean to use "
            "'JPEG-LS Near Lossless' instead?"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEGLSLosslessEncoder.encode(ref, encoding_plugin="pyjpegls", **opts)


@pytest.mark.skipif(SKIP_TEST, reason="Missing required dependencies")
class TestJpegLSNearLossless:
    """Tests for JPEGLSNearLosslessEncoder with pyjpegls."""

    def setup_method(self):
        ds = examples.ct
        arr = ds.pixel_array

        # Rescale to (0, 1)
        arr = arr.astype("float32")
        arr -= arr.min()
        arr /= arr.max()
        self.ref = arr

        ds = examples.rgb_color
        arr = ds.pixel_array

        arr = arr.astype("float32")
        arr -= arr.min()
        arr /= arr.max()
        self.ref3 = arr

    def test_arr_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                # GDCM fails to decode low precision lossy JPEG-LS
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_arr_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_arr_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_arr_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_arr_i1_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            # Clip within the min/max values for the given bits_stored
            ref = ref.clip(-(2 ** (bits_stored - 1)) + 1, 2 ** (bits_stored - 1) - 2)
            ref = ref.astype("int8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )

                if bits_stored == 2:
                    assert np.array_equal(out, ref)
                else:
                    assert not np.array_equal(out, ref)

                assert np.allclose(out, ref, atol=1)

    def test_arr_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            # Clip within the min/max values for the given bits_stored
            ref = ref.clip(-(2 ** (bits_stored - 1)) + 1, 2 ** (bits_stored - 1) - 2)
            ref = ref.astype("int16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                if bits_stored == 2:
                    assert np.array_equal(out, ref)
                else:
                    assert not np.array_equal(out, ref)

                assert np.allclose(out, ref, atol=1)

    def test_buffer_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                # GDCM fails to decode low precision lossy JPEG-LS
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_buffer_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (2, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_buffer_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_buffer_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (2, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        # Planar Configuration 0
        opts["planar_configuration"] = 0
        for bits_stored in range(2, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 6

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

        # Planar Configuration 1
        opts["planar_configuration"] = 1
        for bits_stored in range(2, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                ref, encoding_plugin="pyjpegls", **opts
            )
            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=1)

    def test_buffer_i1_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            # Clip within the min/max values for the given bits_stored
            ref = ref.clip(-(2 ** (bits_stored - 1)) + 1, 2 ** (bits_stored - 1) - 2)
            ref = ref.astype("int8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )

                if bits_stored == 2:
                    assert np.array_equal(out, ref)
                else:
                    assert not np.array_equal(out, ref)

                assert np.allclose(out, ref, atol=1)

    def test_buffer_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (2, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "jls_error": 1,
        }

        plugins = ["pyjpegls"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PYLJ:
            plugins.append("pylibjpeg")

        for bits_stored in range(2, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            # Clip within the min/max values for the given bits_stored
            ref = ref.clip(-(2 ** (bits_stored - 1)) + 1, 2 ** (bits_stored - 1) - 2)
            ref = ref.astype("int16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEGLSNearLosslessEncoder.encode(
                buffer, encoding_plugin="pyjpegls", **opts
            )

            for plugin in plugins:
                if plugin == "gdcm" and bits_stored < 8:
                    continue

                out, _ = JPEGLSNearLosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                if bits_stored == 2:
                    assert np.array_equal(out, ref)
                else:
                    assert not np.array_equal(out, ref)

                assert np.allclose(out, ref, atol=1)
