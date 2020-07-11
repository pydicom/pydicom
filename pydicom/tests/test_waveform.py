# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
import pytest

import pydicom
from pydicom.data import get_testdata_file
from pydicom.filereader import dcmread
from pydicom.tests._handler_common import ALL_TRANSFER_SYNTAXES
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    from pydicom.waveform_data_handlers import numpy_handler as NP_HANDLER
    from pydicom.waveform_data_handlers.numpy_handler import generate_multiplex
except ImportError:
    NP_HANDLER = None


ECG = get_testdata_file('waveform_ecg.dcm')


@pytest.mark.skipif(HAVE_NP, reason="Numpy available")
def test_waveform_generator_raises():
    """Test overlay_array raises exception for all syntaxes."""
    ds = dcmread(ECG)
    msg = r"The waveform data handler requires numpy"
    with pytest.raises(NotImplementedError, match=msg):
        ds.waveform_generator


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestDataset:
    """Tests for dataset.waveform_generator"""
    def test_simple(self):
        """Simple functionality test."""
        ds = dcmread(ECG)
        gen = ds.waveform_generator
        arr = next(gen)
        arr = next(gen)
        with pytest.raises(StopIteration):
            next(gen)

    def test_unsupported_syntax_raises(self):
        """Test that an unsupported syntax raises exception."""
        ds = dcmread(ECG)
        ds.file_meta.TransferSyntaxUID = '1.2.3.4'
        msg = r"Unable to decode waveform data with a transfer syntax UID"
        with pytest.raises(NotImplementedError, match=msg):
            ds.waveform_generator


@pytest.mark.skipif(not HAVE_NP, reason="Numpy not available")
class TestHandler:
    """Tests for the waveform numpy_handler."""
    def test_unsupported_syntax_raises(self):
        """Test that an unsupported syntax raises exception."""
        ds = dcmread(ECG)
        ds.file_meta.TransferSyntaxUID = '1.2.3.4'
        msg = (
            r"Unable to convert the waveform data as the transfer syntax "
            r"is not supported by the waveform data handler"
        )
        gen = generate_multiplex(ds)
        with pytest.raises(NotImplementedError, match=msg):
            next(gen)

    def test_no_waveform_sequence(self):
        """Test that missing waveform sequence raises exception."""
        ds = dcmread(ECG)
        del ds.WaveformSequence
        msg = (
            r"No \(5400,0100\) Waveform Sequence element found in the dataset"
        )
        gen = generate_multiplex(ds)
        with pytest.raises(AttributeError, match=msg):
            next(gen)

    def test_missing_required(self):
        """Test that missing required element in sequence raises exception."""
        ds = dcmread(ECG)
        item = ds.WaveformSequence[0]
        del item.NumberOfWaveformSamples
        msg = (
            f"Unable to convert the waveform multiplex group with index "
            f"0 as the following required elements are missing from "
            f"the sequence item: NumberOfWaveformSamples"
        )
        gen = generate_multiplex(ds)
        with pytest.raises(AttributeError, match=msg):
            next(gen)

    def test_as_raw(self):
        """Test that as_raw=True works as expected."""
        ds = dcmread(ECG)
        item = ds.WaveformSequence[0]
        ch_seq = item.ChannelDefinitionSequence
        ch_seq[0].ChannelSensitivityCorrectionFactor = 0.5
        gen = generate_multiplex(ds, as_raw=True)
        arr = next(gen)
        assert [80, 65, 50, 35, 37] == arr[0:5, 0].tolist()
        assert [90, 85, 80, 75, 77] == arr[0:5, 1].tolist()
        assert arr.dtype == 'int16'
        assert arr.flags.writeable
        assert (10000, 12) == arr.shape

    def test_not_as_raw_no_channel_cf(self):
        """Test that as_raw=False works as expected with no sensitivity CF."""
        ds = dcmread(ECG)
        item = ds.WaveformSequence[0]
        for item in item.ChannelDefinitionSequence:
            del item.ChannelSensitivityCorrectionFactor
        gen = generate_multiplex(ds, as_raw=False)
        arr = next(gen)
        assert [80, 65, 50, 35, 37] == arr[0:5, 0].tolist()
        assert [90, 85, 80, 75, 77] == arr[0:5, 1].tolist()
        assert arr.dtype == 'float'
        assert arr.flags.writeable
        assert (10000, 12) == arr.shape

    def test_not_as_raw(self):
        """Test that as_raw=False works as expected."""
        ds = dcmread(ECG)
        item = ds.WaveformSequence[0]
        ch_seq = item.ChannelDefinitionSequence
        ch_seq[0].ChannelSensitivityCorrectionFactor = 0.5
        gen = generate_multiplex(ds, as_raw=False)
        arr = next(gen)
        assert [40, 32.5, 25, 17.5, 18.5] == arr[0:5, 0].tolist()
        assert [90, 85, 80, 75, 77] == arr[0:5, 1].tolist()
        assert arr.dtype == 'float'
        assert arr.flags.writeable
        assert (10000, 12) == arr.shape
