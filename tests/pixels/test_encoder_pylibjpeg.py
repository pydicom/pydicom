"""Tests for encoding pixel data with pylibjpeg."""

import importlib
from struct import unpack

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread, examples
from pydicom.data import get_testdata_file
from pydicom.encaps import encapsulate, get_frame
from pydicom.pixels.encoders import (
    JPEG2000LosslessEncoder,
    JPEG2000Encoder,
)
from pydicom.pixels.decoders import (
    JPEG2000LosslessDecoder,
    JPEG2000Decoder,
)
from pydicom.pixels.encoders.pylibjpeg import is_available
from pydicom.pixels.utils import as_pixel_options
from pydicom.pixels.utils import get_expected_length, get_j2k_parameters
from pydicom.uid import RLELossless, JPEG2000


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_OJ = bool(importlib.util.find_spec("openjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))
HAVE_GDCM = bool(importlib.util.find_spec("gdcm"))
HAVE_PIL = bool(importlib.util.find_spec("PIL"))

SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)
SKIP_J2K = not (HAVE_NP and HAVE_PYLJ and HAVE_OJ)

IMPL = get_testdata_file("MR_small_implicit.dcm")
EXPL = get_testdata_file("OBXXXX1A.dcm")


@pytest.mark.skipif(SKIP_RLE, reason="no -rle plugin")
class TestRLEEncoding:
    def test_encode(self):
        """Test encoding"""
        ds = dcmread(EXPL)
        assert "PlanarConfiguration" not in ds
        expected = get_expected_length(ds, "bytes")
        assert expected == len(ds.PixelData)
        ref = ds.pixel_array
        del ds.PixelData
        del ds._pixel_array
        ds.compress(RLELossless, ref, encoding_plugin="pylibjpeg")
        assert expected > len(ds.PixelData)
        assert np.array_equal(ref, ds.pixel_array)
        assert ref is not ds.pixel_array

    def test_encode_big(self):
        """Test encoding big-endian src"""
        ds = dcmread(IMPL)
        ref = ds.pixel_array
        del ds._pixel_array
        ds.compress(
            RLELossless, ds.PixelData, byteorder=">", encoding_plugin="pylibjpeg"
        )
        ref = ref.view(ref.dtype.newbyteorder(">"))
        assert np.array_equal(ref, ds.pixel_array)
        assert ref is not ds.pixel_array


def parse_j2k(buffer):
    # SOC -> SIZ -> COD
    # soc = buffer[:2]  # SOC box, 0xff 0x4f
    # siz = buffer[2:4]  # 0xff 0x51
    c_siz = buffer[40:42]
    nr_components = unpack(">H", c_siz)[0]

    o = 42
    for component in range(nr_components):
        ssiz = buffer[o]
        # xrsiz = buffer[o + 1]
        # yrsiz = buffer[o + 2]
        o += 3

    # Should be at the start of the COD marker
    # cod = buffer[o : o + 2]
    sg_cod = buffer[o + 5 : o + 9]

    nr_layers = sg_cod[1:3]
    mct = sg_cod[3]  # 0 for none, 1 for applied

    param = {}
    if ssiz & 0x80:
        param["precision"] = (ssiz & 0x7F) + 1
        param["is_signed"] = True
    else:
        param["precision"] = ssiz + 1
        param["is_signed"] = False

    param["components"] = nr_components
    param["mct"] = bool(mct)
    param["layers"] = unpack(">H", nr_layers)[0]

    return param


@pytest.mark.skipif(SKIP_J2K, reason="no -openjpeg plugin")
class TestJ2KLosslessEncoding:
    """Tests for JPEG2000LosslessEncoder with pylibjpeg."""

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
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )

            for plugin in plugins:
                # Pillow doesn't decode 9-bit J2K correctly
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u4_spp1(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
        }
        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 25):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**24 - 1)
            ref = ref.astype("uint32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "planar_configuration": 0,
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "planar_configuration": 0,
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_u4_spp3(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "planar_configuration": 0,
        }

        for bits_stored in range(1, 25):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**24 - 1)
            ref = ref.astype("uint32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            out, _ = JPEG2000LosslessDecoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-128, 127)
            ref = ref.astype("int8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )

            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_i2_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 16), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-32768, 32767)
            ref = ref.astype("int16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )

            for plugin in plugins:
                # Pillow doesn't decode 9-bit J2K correctly
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_arr_i4_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 32,
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 25):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-8388608, 8388607)
            ref = ref.astype("int32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                ref, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 65535)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u4_spp1(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
        }

        for bits_stored in range(1, 25):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**24 - 1)
            ref = ref.astype("uint32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            out, _ = JPEG2000LosslessDecoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert np.array_equal(out, ref)

    def test_buffer_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "planar_configuration": 0,
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 255)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "planar_configuration": 0,
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**16 - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3 * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_u4_spp3(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "planar_configuration": 0,
        }

        for bits_stored in range(1, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**24 - 1)
            ref = ref.astype("uint32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3 * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            out, _ = JPEG2000LosslessDecoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-128, 127)
            ref = ref.astype("int8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )

            for plugin in plugins:
                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (1, 16), samples per pixel 1"""
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

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-(2**15), 2**15 - 1)
            ref = ref.astype("int16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )

            for plugin in plugins:
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000LosslessDecoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert np.array_equal(out, ref)

    def test_buffer_i4_spp1(self):
        """Test signed bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 32,
        }

        for bits_stored in range(1, 25):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            ref = ref.clip(-(2**23), 2**23 - 1)
            ref = ref.astype("int32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000LosslessEncoder.encode(
                buffer, encoding_plugin="pylibjpeg", **opts
            )
            out, _ = JPEG2000LosslessDecoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert np.array_equal(out, ref)

    def test_mct(self):
        """Test that MCT is used correctly"""
        # If RGB then no MCT
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
        }

        cs = JPEG2000LosslessEncoder.encode(arr, encoding_plugin="pylibjpeg", **opts)
        info = parse_j2k(cs)
        assert info["mct"] is False

        # If YBR_RCT then MCT
        opts["photometric_interpretation"] = "YBR_RCT"
        cs = JPEG2000LosslessEncoder.encode(arr, encoding_plugin="pylibjpeg", **opts)
        info = parse_j2k(cs)
        assert info["mct"] is True

    def test_lossy_kwargs_raise(self):
        """Test that lossy kwargs raise an exception"""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
            "j2k_cr": [20, 5],
            "j2k_psnr": [80, 200],
            "compression_ratios": [20, 5],
            "signal_noise_ratios": [80, 200],
        }

        msg = (
            "Unable to encode as exceptions were raised by all available plugins:\n  "
            "pylibjpeg: A lossy configuration option is being used with a transfer "
            "syntax of 'JPEG 2000 Lossless' - did you mean to use 'JPEG 2000' instead?"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEG2000LosslessEncoder.encode(arr, encoding_plugin="pylibjpeg", **opts)

    def test_bits_stored_25_raises(self):
        """Test that bits stored > 24 raises an exception."""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "bits_stored": 25,
            "planar_configuration": 0,
        }
        arr = arr.astype("u4")

        msg = (
            "Unable to encode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: Invalid 'bits_stored' value '25', must be "
            r"in the range \[1, 24\]"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEG2000LosslessEncoder.encode(arr, encoding_plugin="pylibjpeg", **opts)


@pytest.mark.skipif(SKIP_J2K, reason="no -openjpeg plugin")
class TestJ2KEncoding:
    """Tests for JPEG2000Encoder with pylibjpeg."""

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
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_arr_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)

            for plugin in plugins:
                # Pillow doesn't decode 9-bit J2K correctly
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_arr_u4_spp1(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "j2k_cr": [2],
        }
        atols = [1, 1, 1, 1, 2, 2, 2, 2]
        atols.extend([2, 2, 2, 4, 5, 8, 10, 16])
        atols.extend([23, 31, 52, 63, 122, 2928854, 7404089, 10080970])
        for bits_stored, atol in zip(range(1, 20), atols):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

    def test_arr_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_arr_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_arr_u4_spp3(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }
        # 21+ bits stored gives horrible results
        atols = [1, 2, 2, 2, 2, 2, 2, 2]
        atols.extend([2, 2, 1, 1, 1, 2, 3, 4])
        atols.extend([8, 15, 30, 60, 2097151, 4194303, 8388607, 16777215])
        for bits_stored, atol in zip(range(1, 20), atols):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

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
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int8")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)

            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_arr_i2_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int16")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)

            for plugin in plugins:
                # Pillow doesn't decode 9-bit J2K correctly
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_arr_i4_spp1(self):
        """Test signed bits allocated 8, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "j2k_cr": [2],
        }

        atols = [1, 1, 1, 2, 2, 2, 2, 2]
        atols.extend([2, 2, 2, 4, 5, 9, 11, 16])
        atols.extend([25, 32, 55, 67, 114, 2928849, 7404094, 10080970])
        for bits_stored, atol in zip(range(1, 21), atols):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int32")

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(ref, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

    def test_buffer_u1_spp1(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_buffer_u2_spp1(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_buffer_u4_spp1(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "j2k_cr": [2],
        }

        atols = [1, 1, 1, 1, 2, 2, 2, 2]
        atols.extend([2, 2, 2, 4, 5, 8, 10, 16])
        atols.extend([23, 31, 52, 63, 122, 2928854, 7404089, 10080970])
        for bits_stored, atol in zip(range(1, 21), atols):
            ref = self.ref * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

    def test_buffer_u1_spp3(self):
        """Test unsigned bits allocated 8, bits stored (1, 8), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_buffer_u2_spp3(self):
        """Test unsigned bits allocated 16, bits stored (1, 16), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")

        for bits_stored in range(1, 17):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3 * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_buffer_u4_spp3(self):
        """Test unsigned bits allocated 32, bits stored (1, 24), samples per pixel 3"""
        ds = examples.rgb_color
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        atols = [1, 2, 2, 2, 2, 2, 2, 2]
        atols.extend([2, 2, 1, 1, 1, 2, 3, 4])
        atols.extend([8, 15, 30, 60, 2097151, 4194303, 8388607, 16777215])
        for bits_stored, atol in zip(range(1, 20), atols):
            ref = self.ref3 * (2**bits_stored - 1)
            ref = ref.clip(0, 2**bits_stored - 1)
            ref = ref.astype("uint32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 3 * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )

            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

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
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 9):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int8")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)

            for plugin in plugins:
                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=2)

    def test_buffer_i2_spp1(self):
        """Test signed bits allocated 16, bits stored (1, 16), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 16,
            "j2k_cr": [2],
        }

        plugins = ["pylibjpeg"]
        if HAVE_GDCM:
            plugins.append("gdcm")
        if HAVE_PIL:
            plugins.append("pillow")

        for bits_stored in range(1, 17):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int16")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 2

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)

            for plugin in plugins:
                if plugin == "pillow" and bits_stored == 9:
                    continue

                out, _ = JPEG2000Decoder.as_array(
                    encapsulate([cs]),
                    decoding_plugin=plugin,
                    **opts,
                )
                assert not np.array_equal(out, ref)
                assert np.allclose(out, ref, atol=16)

    def test_buffer_i4_spp1(self):
        """Test signed bits allocated 32, bits stored (1, 24), samples per pixel 1"""
        ds = examples.ct
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": ds.PhotometricInterpretation,
            "pixel_representation": 1,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "j2k_cr": [2],
        }

        atols = [1, 1, 1, 2, 2, 2, 2, 2]
        atols.extend([2, 2, 2, 4, 5, 9, 11, 16])
        atols.extend([25, 32, 55, 67, 114, 2928849, 7404094, 10080970])
        for bits_stored, atol in zip(range(1, 21), atols):
            ref = self.ref * (2**bits_stored - 1)
            ref -= 2 ** (bits_stored - 1)
            minimum = -(2 ** (bits_stored - 1))
            maximum = 2 ** (bits_stored - 1) - 1
            ref = ref.clip(minimum, maximum)
            ref = ref.astype("int32")

            buffer = ref.tobytes()
            assert len(buffer) == ds.Rows * ds.Columns * 4

            opts["bits_stored"] = bits_stored
            cs = JPEG2000Encoder.encode(buffer, encoding_plugin="pylibjpeg", **opts)
            out, _ = JPEG2000Decoder.as_array(
                encapsulate([cs]),
                decoding_plugin="pylibjpeg",
                **opts,
            )
            assert not np.array_equal(out, ref)
            assert np.allclose(out, ref, atol=atol)

    def test_j2k_psnr(self):
        """Test compression using j2k_psnr"""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
            "j2k_psnr": [80],
        }

        cs = JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)
        out, _ = JPEG2000Decoder.as_array(
            encapsulate([cs]),
            decoding_plugin="pylibjpeg",
            **opts,
        )
        assert not np.array_equal(out, arr)
        assert np.allclose(out, arr, atol=2)

    def test_mct(self):
        """Test that MCT is used correctly"""
        # If RGB then no MCT
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }

        cs = JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)
        info = parse_j2k(cs)
        assert info["mct"] is False

        # If YBR_ICT then MCT
        opts["photometric_interpretation"] = "YBR_ICT"
        cs = JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)
        info = parse_j2k(cs)
        assert info["mct"] is True

    def test_both_lossy_kwargs_raises(self):
        """Test that having both lossy kwargs raises an exception"""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
            "j2k_cr": [20, 5],
            "j2k_psnr": [80, 200],
        }

        msg = (
            "Unable to encode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: Multiple lossy configuration options are "
            "being used with the 'JPEG 2000' transfer syntax, please specify "
            "only one"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)

    def test_neither_lossy_kwargs_raises(self):
        """Test that having neither lossy kwarg raises an exception"""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 8,
            "bits_stored": 8,
            "planar_configuration": 0,
        }

        msg = (
            "Unable to encode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: The 'JPEG 2000' transfer syntax requires "
            "a lossy configuration option such as 'j2k_cr' or 'j2k_psnr'"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)

    def test_bits_stored_25_raises(self):
        """Test that bits stored > 24 raises an exception."""
        ds = examples.rgb_color
        arr = ds.pixel_array
        opts = {
            "rows": ds.Rows,
            "columns": ds.Columns,
            "samples_per_pixel": ds.SamplesPerPixel,
            "photometric_interpretation": "RGB",
            "pixel_representation": 0,
            "number_of_frames": 1,
            "bits_allocated": 32,
            "bits_stored": 25,
            "planar_configuration": 0,
            "j2k_cr": [2],
        }
        arr = arr.astype("u4")

        msg = (
            "Unable to encode as exceptions were raised by all available "
            "plugins:\n  pylibjpeg: Invalid 'bits_stored' value '25', must be "
            r"in the range \[1, 24\]"
        )
        with pytest.raises(RuntimeError, match=msg):
            JPEG2000Encoder.encode(arr, encoding_plugin="pylibjpeg", **opts)


def test_is_available_unknown_uid():
    """Test is_available() with an unsupported UID."""
    assert is_available("1.2.3.4") is False
