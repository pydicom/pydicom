"""Unit tests for the pydicom.encoders module and Dataset.compress()."""

import pytest

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import pylibjpeg
    HAVE_PYLJ = True
except ImportError:
    HAVE_PYLJ = False


from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset
from pydicom.encoders import Encoder, parallel_encode, RLELosslessEncoder
from pydicom.pixel_data_handlers.util import get_expected_length
from pydicom.uid import (
    UID, RLELossless, ExplicitVRLittleEndian, JPEG2000MC
)


class TestEncoder:
    """Non-encoding tests for encoders.Encoder"""
    def setup(self):
        self.enc = Encoder(UID('1.2.3'))

    def test_init(self):
        """Test creating a new Encoder"""
        uid = UID('1.2.3')
        enc = Encoder(uid)
        assert {} == enc._available
        assert {} == enc._unavailable
        assert '<' == enc._defaults['byteorder']
        assert uid == enc._defaults['transfer_syntax_uid']

    def test_properties(self):
        """Test Encoder properties"""
        enc = Encoder(RLELossless)
        assert 'RLELosslessEncoder' == enc.name
        assert RLELossless == enc.UID
        assert not enc.is_available

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_add_plugin_available(self):
        """Test adding an available plugin."""
        assert not self.enc.is_available
        self.enc.add_plugin(
            "foo",
            (
                'pydicom.pixel_data_handlers.rle_handler',
                '_wrap_rle_encode_frame'
            ),
            "plugin custom error"
        )
        assert "foo" in self.enc._available
        assert {} == self.enc._unavailable
        assert self.enc.is_available

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_add_plugin_unavailable(self):
        """Test adding an unavailable plugin."""
        enc = Encoder(RLELossless)
        assert not enc.is_available
        enc.add_plugin(
            "foo",
            (
                'pydicom.pixel_data_handlers.rle_handler',
                '_wrap_rle_encode_frame'
            ),
            "plugin custom error"
        )
        assert {} == enc._available
        assert "foo" in enc._unavailable
        assert ("numpy", ) == enc._unavailable["foo"]
        assert not enc.is_available

    def test_add_plugin_module_import_failure(self):
        """Test a module import failure when adding a plugin."""
        enc = Encoder(RLELossless)

        msg = r"No module named 'badpath'"
        with pytest.raises(ModuleNotFoundError, match=msg):
            enc.add_plugin(
                "foo",
                (
                    'badpath.pixel_data_handlers.rle_handler',
                    '_wrap_rle_encode_frame'
                ),
                "plugin custom error"
            )
        assert {} == enc._available
        assert {} == enc._unavailable

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is available")
    def test_add_plugin_function_missing(self):
        """Test encoding function missing when adding a plugin."""
        enc = Encoder(RLELossless)

        msg = (
            r"module 'pydicom.pixel_data_handlers.rle_handler' has no "
            r"attribute 'bad_function_name'"
        )
        with pytest.raises(AttributeError, match=msg):
            enc.add_plugin(
                "foo",
                (
                    'pydicom.pixel_data_handlers.rle_handler',
                    'bad_function_name'
                ),
                "plugin custom error"
            )
        assert {} == enc._available
        assert {} == enc._unavailable

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is unavailable")
    def test_add_plugin_twice(self):
        """Test adding a plugin that already exists."""
        self.enc.add_plugin(
            "foo",
            (
                'pydicom.pixel_data_handlers.rle_handler',
                '_wrap_rle_encode_frame'
            ),
            "plugin custom error"
        )
        assert 'foo' in self.enc._available
        assert {} == self.enc._unavailable

        msg = r"'Encoder' already has a plugin named 'foo'"
        with pytest.raises(ValueError, match=msg):
            self.enc.add_plugin(
                "foo",
                (
                    'pydicom.pixel_data_handlers.rle_handler',
                    '_wrap_rle_encode_frame'
                ),
            )
        assert 'foo' in self.enc._available
        assert {} == self.enc._unavailable

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is unavailable")
    def test_remove_plugin(self):
        """Test removing a plugin."""
        self.enc.add_plugin(
            "foo",
            (
                'pydicom.pixel_data_handlers.rle_handler',
                '_wrap_rle_encode_frame'
            ),
        )
        self.enc.add_plugin(
            "bar",
            (
                'pydicom.pixel_data_handlers.rle_handler',
                '_wrap_rle_encode_frame'
            ),
        )
        assert 'foo' in self.enc._available
        assert 'bar' in self.enc._available
        assert {} == self.enc._unavailable
        assert self.enc.is_available

        self.enc.remove_plugin("foo")
        assert 'bar' in self.enc._available
        assert self.enc.is_available

        self.enc.remove_plugin("bar")
        assert {} == self.enc._available
        assert not self.enc.is_available

    def test_remove_plugin_raises(self):
        """Test removing a plugin that doesn't exist raises exception"""
        msg = r"Unable to remove 'foo', no such plugin"
        with pytest.raises(ValueError, match=msg):
            self.enc.remove_plugin('foo')

    def test_check_kwargs_missing(self):
        """Test _check_kwargs"""
        enc = Encoder(RLELossless)
        kwargs = {
            'rows': 0,
            'columns': 0,
            'samples_per_pixel': 0,
            'bits_allocated': 0,
            'bits_stored': 0,
            'pixel_representation': 0,
            'photometric_interpretation': 'RGB'
        }
        assert enc._check_kwargs(kwargs) is None

        del kwargs['columns']
        del kwargs['bits_allocated']
        msg = r"Missing expected arguments: 'columns', 'bits_allocated'"
        with pytest.raises(TypeError, match=msg):
            enc._check_kwargs(kwargs)

    def test_kwargs_from_ds(self):
        """Test Encoder.kwargs_from_ds()"""
        # Note no NumberOfFrames element
        ds = Dataset()
        ds.Rows = 10
        ds.Columns = 12
        ds.SamplesPerPixel = 1
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = 'RGB'

        enc = Encoder(RLELossless)
        kwargs = enc.kwargs_from_ds(ds)
        assert 1 == kwargs['number_of_frames']
        assert enc._check_kwargs(kwargs) is None

        # Test conversion of empty *Number of Frames*
        ds.NumberOfFrames = None
        kwargs = enc.kwargs_from_ds(ds)
        assert 1 == kwargs['number_of_frames']

        # Test already present *Number of Frames* is unaffected
        ds.NumberOfFrames = 10
        kwargs = enc.kwargs_from_ds(ds)
        assert 10 == kwargs['number_of_frames']

        # Test missing elements
        del ds.Columns
        del ds.BitsAllocated

        msg = (
            r"The following required elements are missing from the dataset: "
            r"'Columns', 'BitsAllocated'"
        )
        with pytest.raises(AttributeError, match=msg):
            enc.kwargs_from_ds(ds)

        # Test VM 0
        ds.Columns = None
        ds.BitsAllocated = None

        msg = (
            r"The following required dataset elements have a VM of 0: "
            r"'Columns', 'BitsAllocated'"
        )
        with pytest.raises(AttributeError, match=msg):
            enc.kwargs_from_ds(ds)

    @pytest.mark.skipif(HAVE_NP, reason="Numpy available")
    def test_missing_dependencies(self):
        """Test the required encoder being unavailable."""
        enc = RLELosslessEncoder
        s = enc.missing_dependencies
        assert (
            "pylibjpeg - requires numpy, pylibjpeg and pylibjpeg-rle" == s[0]
        )
        assert "pydicom - requires numpy" == s[1]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncoder_Encode:
    """Tests for Encoder.encode() and related methods."""
    def setup(self):
        self.enc = RLELosslessEncoder
        self.ds = get_testdata_file("CT_small.dcm", read=True)
        self.ds_enc = get_testdata_file("MR_small_RLE.dcm", read=True)
        self.ds_enc_mf = get_testdata_file("emri_small_RLE.dcm", read=True)
        self.bytes = self.ds.PixelData
        self.arr = self.ds.pixel_array
        self.kwargs = self.enc.kwargs_from_ds(self.ds)

    def test_invalid_type_raises(self):
        """Test exception raised if passing invalid type."""
        enc = RLELosslessEncoder
        msg = (
            r"'src' must be bytes, numpy.ndarray or pydicom.dataset.Dataset, "
            rf"not 'str'"
        )
        with pytest.raises(TypeError, match=msg):
            enc.encode('abc')

    # Passing bytes
    def test_bytes(self):
        """Test encoding bytes"""
        assert 32768 == len(self.bytes)
        out = self.enc.encode(self.bytes, **self.kwargs)
        assert len(self.bytes) > len(out)

    def test_bytes_specific(self):
        """Test encoding bytes with a specific encoder"""
        out = self.enc.encode(
            self.bytes, encoding_plugin='pydicom', **self.kwargs
        )
        assert 21098 == len(out)

    def test_bytes_short_raises(self):
        """Test encoding bytes with short data raises exception"""
        msg = (
            r"Unable to encode as the actual length of the frame \(32767 "
            r"bytes\) is less than the expected length of 32768 bytes"
        )
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.bytes[:-1], **self.kwargs)

    def test_bytes_padded(self):
        """Test encoding bytes with padded data"""
        out = self.enc.encode(
            self.bytes + b'\x00\x00', encoding_plugin='pydicom', **self.kwargs
        )
        assert 21098 == len(out)

    def test_bytes_multiframe(self):
        """Test encoding multiframe bytes with idx"""
        out = self.enc.encode(
            self.bytes * 2, idx=0, encoding_plugin='pydicom', **self.kwargs
        )
        assert 21098 == len(out)

    def test_bytes_multiframe_no_idx_raises(self):
        """Test encoding multiframe bytes without idx raises exception"""
        msg = r"The frame 'idx' is required for multi-frame pixel data"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.bytes * 2, **self.kwargs)

    # Passing ndarray
    def test_array(self):
        """Test encode with an array"""
        out = self.enc.encode(self.arr, **self.kwargs)
        assert len(self.arr.tobytes()) > len(out)

    def test_array_specific(self):
        """Test encoding with a specific plugin"""
        out = self.enc.encode(
            self.arr, encoding_plugin='pydicom', **self.kwargs
        )
        assert 21098 == len(out)

    def test_array_multiframe(self):
        """Test encoding a multiframe array with idx"""
        arr = np.stack((self.arr, self.arr))
        assert (2, 128, 128) == arr.shape
        self.kwargs['number_of_frames'] = 2
        out = self.enc.encode(
            arr, idx=0, encoding_plugin='pydicom', **self.kwargs
        )
        assert 21098 == len(out)

    def test_array_invalid_dims_raises(self):
        """Test encoding an array with too many dimensions raises"""
        arr = np.zeros((1, 2, 3, 4, 5))
        assert (1, 2, 3, 4, 5) == arr.shape
        msg = r"Unable to encode 5D ndarrays"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(arr, **self.kwargs)

    def test_array_multiframe_no_idx_raises(self):
        """Test encoding a multiframe array without idx raises"""
        arr = np.stack((self.arr, self.arr))
        assert (2, 128, 128) == arr.shape
        self.kwargs['number_of_frames'] = 2
        msg = r"The frame 'idx' is required for multi-frame pixel data"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(arr, **self.kwargs)

    # Passing Dataset
    def test_unc_dataset(self):
        """Test encoding an uncompressed dataset"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(self.ds)
        assert len(self.ds.PixelData) > len(out)

    def test_unc_dataset_specific(self):
        """Test encoding an uncompressed dataset with specific plugin"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(self.ds, encoding_plugin='pydicom')
        assert 21098 == len(out)

    def test_unc_dataset_multiframe(self):
        """Test encode(Dataset, idx) for an uncompressed tsyntax"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        self.ds.NumberOfFrames = 2
        self.ds.PixelData = self.ds.PixelData * 2
        out = self.enc.encode(self.ds, idx=0)
        assert len(self.ds.PixelData) > len(out)

    def test_unc_dataset_multiframe_no_idx_raises(self):
        """Test encode(Dataset) raises if no idx"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        self.ds.NumberOfFrames = 2
        self.ds.PixelData = self.ds.PixelData * 2
        msg = r"The frame 'idx' is required for multi-frame pixel data"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(self.ds)

    def test_enc_dataset(self):
        """Test encoding a compressed dataset"""
        ds = self.ds_enc
        assert ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(ds)
        uncompressed_len = get_expected_length(ds, 'bytes')
        assert uncompressed_len > len(out)

    def test_enc_dataset_specific_enc(self):
        """Test encoding a compressed dataset with specified encoder plugin"""
        ds = self.ds_enc
        assert ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(ds, encoding_plugin='pydicom')
        assert 6072 == len(out)

    def test_enc_dataset_specific_dec(self):
        """Test encoding a compressed dataset with specified decoder plugin"""
        ds = self.ds_enc
        assert ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(
            ds,
            encoding_plugin='pydicom',
            decoding_plugin='rle_handler'
        )
        assert 6072 == len(out)

    def test_enc_dataset_multiframe(self):
        """Test encoding a multiframe compressed dataset"""
        ds = self.ds_enc_mf
        assert ds.file_meta.TransferSyntaxUID.is_compressed
        out = self.enc.encode(ds, idx=0)
        uncompressed_len = get_expected_length(ds, 'bytes')
        assert uncompressed_len / ds.NumberOfFrames > len(out)

    def test_enc_dataset_multiframe_no_idx_raises(self):
        """Test encoding a multiframe compressed dataset raises if no idx"""
        ds = self.ds_enc_mf
        assert ds.file_meta.TransferSyntaxUID.is_compressed
        msg = r"The frame 'idx' is required for multi-frame pixel data"
        with pytest.raises(ValueError, match=msg):
            self.enc.encode(ds)

    def test_dataset_missing_elem_raises(self):
        """Test encode raises if missing required element"""
        assert not self.ds.file_meta.TransferSyntaxUID.is_compressed
        del self.ds.Rows
        msg = r"required elements are missing from the dataset: 'Rows'"
        with pytest.raises(AttributeError, match=msg):
            self.enc.encode(self.ds)



@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestEncoder_Preprocess:
    """Tests for Encoder._preprocess()."""
    def setup(self):
        self.e = Encoder(RLELossless)
        self.ds = ds = Dataset()
        ds.Rows = 1
        ds.Columns = 3
        ds.SamplesPerPixel = 1
        ds.PixelRepresentation = 0
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.NumberOfFrames = 1
        ds.PhotometricInterpretation = 'RGB'

        self.arr_3s = np.asarray(
            [
                [[ 1,  2,  3], [ 4,  5,  6]],
                [[ 7,  8,  9], [10, 11, 12]],
                [[13, 14, 15], [16, 17, 18]],
                [[19, 20, 21], [22, 23, 24]],
            ],
            '|u1'
        )
        assert (4, 2, 3) == self.arr_3s.shape

    def test_invalid_arr_shape_raises(self):
        """Test that an array size and dataset mismatch raise exceptions"""
        # 1D arrays
        arr = np.asarray((1, 2, 3, 4))
        msg = (
            r"Unable to encode as the shape of the ndarray \(4,\) "
            r"doesn't match the values for the rows, columns and samples "
            r"per pixel"
        )

        kwargs = self.e.kwargs_from_ds(self.ds)
        assert (4, ) == arr.shape
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        # 2D arrays
        arr = np.asarray([[1, 2, 3, 4]])
        assert (1, 4) == arr.shape
        msg = r"Unable to encode as the shape of the ndarray \(1, 4\) "
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        self.ds.Rows = 2
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3
        arr = np.asarray([[1, 2], [3, 4]])
        assert (2, 2) == arr.shape
        msg = r"Unable to encode as the shape of the ndarray \(2, 2\) "
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        # 3D arrays
        self.ds.Rows = 3
        arr = np.asarray([[[1, 2, 1], [3, 4, 1]]])
        assert (1, 2, 3) == arr.shape
        msg = r"Unable to encode as the shape of the ndarray \(1, 2, 3\) "
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

    def test_invalid_arr_dtype_raises(self):
        """Test an invalid arr dtype raises exception."""
        arr = np.asarray(('a', 'b', 'c'))
        msg = (
            r"Unable to encode as the ndarray's dtype '<U1' is not supported"
        )

        kwargs = self.e.kwargs_from_ds(self.ds)
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

    def test_invalid_pixel_representation_raises(self):
        """Test exception raised if pixel representation/dtype mismatch"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        kwargs = self.e.kwargs_from_ds(self.ds)

        arr = np.asarray([1, 2, 3], dtype='|i1')
        msg = (
            r"Unable to encode as the ndarray's dtype 'int8' is not "
            r"consistent with pixel representation '0' \(unsigned int\)"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        arr = np.asarray([1, 2, 3], dtype='|u1')
        kwargs['pixel_representation'] = 1
        msg = (
            r"Unable to encode as the ndarray's dtype 'uint8' is not "
            r"consistent with pixel representation '1' \(signed int\)"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

    def test_invalid_bits_allocated_raises(self):
        """Test exception raised for invalid Bits Allocated"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        kwargs = self.e.kwargs_from_ds(self.ds)

        arr = np.asarray([1, 2, 3], dtype='|u1')
        kwargs['bits_stored'] = 9
        msg = (
            r"Unable to encode as the bits stored value is greater than the "
            r"bits allocated value"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        kwargs['bits_stored'] = 8
        kwargs['bits_allocated'] = 9

        msg = (
            r"Unable to encode as a bits allocated value of 9 is not "
            r"supported \(must be 8, 16, 32 or 64\)"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        kwargs['bits_allocated'] = 16
        msg = (
            r"Unable to encode as the ndarray's dtype 'uint8' is not "
            r"consistent with a bits allocated value of 16"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

    def test_invalid_samples_per_pixel_raises(self):
        """Test exception raised spp is invalid"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 2
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 2
        self.ds.Columns = 2
        kwargs = self.e.kwargs_from_ds(self.ds)

        arr = np.asarray([1, 2, 3], dtype='|i1')
        msg = (
            r"Unable to encode as a samples per pixel value of 2 is not "
            r"supported \(must be 1 or 3\)"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

        arr = np.asarray([[1, 2], [1, 3]], dtype='|i1')
        kwargs['samples_per_pixel'] = 3
        msg = (
            r"Unable to encode as the shape of the ndarray \(2, 2\) is not "
            r"consistent with a samples per pixel value of 3"
        )
        with pytest.raises(ValueError, match=msg):
            self.e._preprocess(arr, **kwargs)

    def test_u08_1s(self):
        """Test processing u8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([1, 2, 3], dtype='|u1')
        assert 1 == arr.dtype.itemsize
        kwargs = self.e.kwargs_from_ds(self.ds)
        out = self.e._preprocess(arr, **kwargs)
        assert 3 == len(out)
        assert b"\x01\x02\x03" == out

    def test_u08_3s(self):
        """Test processing u8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3

        arr = self.arr_3s.astype('|u1')
        assert 1 == arr.dtype.itemsize
        kwargs = self.e.kwargs_from_ds(self.ds)
        out = self.e._preprocess(arr, **kwargs)
        assert 24 == len(out)
        assert bytes(range(1, 25)) == out

    def test_i08_1s(self):
        """Test processing i8/1s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3

        arr = np.asarray([-128, 0, 127], dtype='|i1')
        assert 1 == arr.dtype.itemsize
        kwargs = self.e.kwargs_from_ds(self.ds)
        out = self.e._preprocess(arr, **kwargs)
        assert 3 == len(out)
        assert b"\x80\x00\x7f" == out

    def test_u08_3s(self):
        """Test processing i8/3s"""
        self.ds.BitsAllocated = 8
        self.ds.BitsStored = 8
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2
        self.ds.SamplesPerPixel = 3

        arr = self.arr_3s.astype('|i1')
        assert 1 == arr.dtype.itemsize
        kwargs = self.e.kwargs_from_ds(self.ds)
        out = self.e._preprocess(arr, **kwargs)
        assert 24 == len(out)
        assert bytes(range(1, 25)) == out

    def test_u16_1s(self):
        """Test processing u16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in ('>u2', '<u2', '=u2'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 6 == len(out)
            assert b"\x01\x00\x02\x00\x03\x00" == out

    def test_u16_3s(self):
        """Test processing u16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        for dtype in ('>u2', '<u2', '=u2'):
            arr = self.arr_3s.astype(dtype)
            assert 2 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 48 == len(out)
            assert ref == out

    def test_i16_1s(self):
        """Test processing i16/1s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3
        self.ds.SamplesPerPixel = 1

        for dtype in ('>i2', '<i2', '=i2'):
            arr = np.asarray([-128, 0, 127], dtype=dtype)
            assert 2 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 6 == len(out)
            assert b"\x80\xff\x00\x00\x7f\x00" == out

    def test_i16_3s(self):
        """Test processing i16/3s"""
        self.ds.BitsAllocated = 16
        self.ds.BitsStored = 16
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2
        ref = b''.join([bytes([b]) + b'\x00' for b in bytes(range(1, 25))])

        for dtype in ('>i2', '<i2', '=i2'):
            arr = self.arr_3s.astype(dtype)
            assert 2 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 48 == len(out)
            assert ref == out

    def test_u32_1s(self):
        """Test processing u32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00"

        for dtype in ('>u4', '<u4', '=u4'):
            arr = np.asarray([1, 2, 3], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 12 == len(out)
            assert ref == out

    def test_u32_3s(self):
        """Test processing u32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 0
        self.ds.Rows = 4
        self.ds.Columns = 2

        ref = b''.join([bytes([b]) + b'\x00' * 3 for b in bytes(range(1, 25))])

        for dtype in ('>u4', '<u4', '=u4'):
            arr = self.arr_3s.astype(dtype)
            assert 4 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 96 == len(out)
            assert ref == out

    def test_i32_1s(self):
        """Test processing i32/1s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 1
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 1
        self.ds.Columns = 3
        ref = b"\x80\xff\xff\xff\x00\x00\x00\x00\x7f\x00\x00\x00"

        for dtype in ('>i4', '<i4', '=i4'):
            arr = np.asarray([-128, 0, 127], dtype=dtype)
            assert 4 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 12 == len(out)
            assert ref == out

    def test_i32_3s(self):
        """Test processing i32/3s"""
        self.ds.BitsAllocated = 32
        self.ds.BitsStored = 32
        self.ds.SamplesPerPixel = 3
        self.ds.PixelRepresentation = 1
        self.ds.Rows = 4
        self.ds.Columns = 2

        ref = b''.join([bytes([b]) + b'\x00' * 3 for b in bytes(range(1, 25))])

        for dtype in ('>i4', '<i4', '=i4'):
            arr = self.arr_3s.astype(dtype)
            assert 4 == arr.dtype.itemsize
            kwargs = self.e.kwargs_from_ds(self.ds)
            out = self.e._preprocess(arr, **kwargs)
            assert 96 == len(out)
            assert ref == out


class TestEncoder_Process:
    """Tests for Encoder._process."""
    @pytest.mark.skipif(HAVE_NP, reason="Numpy available")
    def test_no_plugins(self):
        """Test with no available plugins"""
        msg = (
            r"Unable to encode because the encoding plugins are missing "
            r"dependencies:\n    pylibjpeg - requires numpy, pylibjpeg and "
            r"pylibjpeg-rle\n    pydicom - requires numpy"
        )
        with pytest.raises(RuntimeError, match=msg):
            RLELosslessEncoder._process(b'')

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_specify_plugin(self):
        """Test with specific plugin"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        enc = RLELosslessEncoder
        kwargs = enc.kwargs_from_ds(ds)
        out = enc._process(ds.PixelData, plugin='pydicom', **kwargs)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_specify_invalid_plugin_raises(self):
        """Test an invalid plugin raises exception"""
        msg = (
            r"No plugin named 'foo' has been added to the 'RLELosslessEncoder'"
        )
        with pytest.raises(ValueError, match=msg):
            RLELosslessEncoder._process(b'', plugin='foo')

    @pytest.mark.skipif(
        not HAVE_NP or HAVE_PYLJ,
        reason="Numpy unavailable or pylibjpeg available"
    )
    def test_specify_plugin_unavailable_raises(self):
        """Test with specific unavailable plugin"""
        enc = RLELosslessEncoder
        assert enc.is_available
        msg = (
            r"Unable to encode with the 'pylibjpeg' encoding plugin because "
            r"it's missing dependencies - requires numpy, pylibjpeg and "
            r"pylibjpeg-rle"
        )
        with pytest.raises(RuntimeError, match=msg):
            enc._process(b'', plugin='pylibjpeg')

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_specify_plugin_encoding_exception(self):
        """Test an encoding exception occurring with a specific plugin"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        enc = RLELosslessEncoder
        kwargs = enc.kwargs_from_ds(ds)
        kwargs['bits_allocated'] = []

        msg = (
            r"Unable to encode as an exception was raised by the 'pydicom' "
            r"plugin's encoding function"
        )
        with pytest.raises(RuntimeError, match=msg):
            enc._process(ds.PixelData, plugin='pydicom', **kwargs)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy unavailable")
    def test_encoding_exceptions(self):
        """Test an encoding exception occurring in all plugins"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        enc = RLELosslessEncoder
        kwargs = enc.kwargs_from_ds(ds)
        kwargs['bits_allocated'] = []

        msg = (
            r"Unable to encode as exceptions were raised by all the available "
            r"plugins:\n"
        )
        with pytest.raises(RuntimeError, match=msg):
            enc._process(ds.PixelData, **kwargs)


class TestDatasetCompress:
    """Tests for Dataset.compress()."""
    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_compress_inplace(self):
        """Test encode with a dataset."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        ds.compress(RLELossless, encoding_plugin='pydicom')
        assert RLELossless == ds.file_meta.TransferSyntaxUID
        assert 21118 == len(ds.PixelData)
        assert 1 == ds.PlanarConfiguration

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_compress_arr(self):
        """Test encode with a dataset."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        arr = ds.pixel_array
        del ds.PixelData
        ds.compress(RLELossless, arr, encoding_plugin='pydicom')
        assert RLELossless == ds.file_meta.TransferSyntaxUID
        assert 21118 == len(ds.PixelData)
        assert 1 == ds.PlanarConfiguration

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    def test_encoder_unavailable(self):
        """Test the required encoder being unavailable."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        msg = (
            r"The 'RLE Lossless' encoder is unavailable because its encoding "
            r"plugins are missing dependencies:\n    pylibjpeg - requires "
            r"numpy, pylibjpeg and pylibjpeg-rle\n    pydicom - requires numpy"
        )
        with pytest.raises(RuntimeError, match=msg):
            ds.compress(RLELossless)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_uid_not_supported(self):
        """Test the UID not having any encoders."""
        ds = get_testdata_file("CT_small.dcm", read=True)

        msg = (
            r"No pixel data encoders have been implemented for "
            r"'JPEG 2000 Part 2 Multi-component Image Compression'"
        )
        with pytest.raises(NotImplementedError, match=msg):
            ds.compress(JPEG2000MC)

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_encapsulate_extended(self):
        """Test forcing extended encapsulation."""
        ds = get_testdata_file("CT_small.dcm", read=True)
        assert 'ExtendedOffsetTable' not in ds
        assert 'ExtendedOffsetTableLengths' not in ds

        ds.compress(
            RLELossless, encapsulate_ext=True, encoding_plugin='pydicom'
        )
        assert RLELossless == ds.file_meta.TransferSyntaxUID
        assert 21114 == len(ds.PixelData)
        assert 1 == ds.PlanarConfiguration
        assert b'\x00' * 8 == ds.ExtendedOffsetTable
        assert b'\x6a\x52' + b'\x00' * 6 == ds.ExtendedOffsetTableLengths

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
    def test_round_trip(self):
        """Test an encoding round-trip"""
        ds = get_testdata_file("MR_small_RLE.dcm", read=True)
        original = ds.PixelData
        arr = ds.pixel_array
        del ds.PixelData
        ds.compress(RLELossless, arr, encoding_plugin="pydicom")
        assert id(arr) != id(ds.pixel_array)
        assert np.array_equal(arr, ds.pixel_array)
