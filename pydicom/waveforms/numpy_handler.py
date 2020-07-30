# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Use the `numpy <https://numpy.org/>`_ package to convert supported *Waveform
Data* to a :class:`numpy.ndarray`.

.. versionadded:: 2.1

**Supported transfer syntaxes**

* 1.2.840.10008.1.2 : Implicit VR Little Endian
* 1.2.840.10008.1.2.1 : Explicit VR Little Endian
* 1.2.840.10008.1.2.1.99 : Deflated Explicit VR Little Endian
* 1.2.840.10008.1.2.2 : Explicit VR Big Endian

**Supported data**

The numpy handler supports the conversion of data in the (5400,0100)
*Waveform Sequence* element to an :class:`~numpy.ndarray` provided the
related :dcm:`Waveform<part03/sect_C.10.9.html>` module elements have values
given in the table below.

+-------------+------------------------------+------+-------------------------+
| Element                                           | Supported               |
+-------------+------------------------------+------+ values                  |
| Tag         | Keyword                      | Type |                         |
+=============+==============================+======+=========================+
| (003A,0005) | NumberOfWaveformChannels     | 1    | N > 0                   |
+-------------+------------------------------+------+-------------------------+
| (003A,0010) | NumberOfWaveformSamples      | 1    | N > 0                   |
+-------------+------------------------------+------+-------------------------+
| (5400,1004) | WaveformBitsAllocated        | 1    | 8, 16, 32, 64           |
+-------------+------------------------------+------+-------------------------+
| (5400,1006) | WaveformSampleInterpretation | 1    | SB, UB, MB, AB, SS, US, |
|             |                              |      | SL, UL, SV, UV          |
+-------------+------------------------------+------+-------------------------+

"""

from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from pydicom.dataset import Dataset

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

import pydicom.uid
from pydicom.uid import UID


HANDLER_NAME = 'Numpy Waveform'
DEPENDENCIES = {'numpy': ('http://www.numpy.org/', 'NumPy')}
SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.ExplicitVRLittleEndian,
    pydicom.uid.ImplicitVRLittleEndian,
    pydicom.uid.DeflatedExplicitVRLittleEndian,
    pydicom.uid.ExplicitVRBigEndian,
]
WAVEFORM_DTYPES = {
    (8, 'SB'): 'int8',
    (8, 'UB'): 'uint8',
    (8, 'MB'): 'uint8',
    (8, 'AB'): 'uint8',
    (16, 'SS'): 'int16',
    (16, 'US'): 'uint16',
    (32, 'SL'): 'int32',
    (32, 'UL'): 'uint32',
    (64, 'SV'): 'int64',
    (64, 'UV'): 'uint64',
}


def is_available() -> bool:
    """Return ``True`` if the handler has its dependencies met.

    .. versionadded:: 2.1
    """
    return HAVE_NP


def supports_transfer_syntax(transfer_syntax: UID) -> bool:
    """Return ``True`` if the handler supports the `transfer_syntax`.

    .. versionadded:: 2.1

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


def generate_multiplex(ds: "Dataset", as_raw: bool = True) -> Generator["np.ndarray", None, None]:  # noqa
    """Yield an :class:`~numpy.ndarray` for each multiplex group in the
    *Waveform Sequence*.

    .. versionadded:: 2.1

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The :class:`Dataset` containing a :dcm:`Waveform
        <part03/sect_C.10.9.html>` module and the *Waveform Sequence* to be
        converted.
    as_raw : bool, optional
        If ``True`` (default), then yield the raw unitless waveform data. If
        ``False`` then attempt to convert the raw data for each channel to the
        quantity specified by the corresponding (003A,0210) *Channel
        Sensitivity* unit.

    Yields
    ------
    np.ndarray
        The waveform data for a multiplex group as an :class:`~numpy.ndarray`
        with shape (samples, channels).
    """
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if transfer_syntax not in SUPPORTED_TRANSFER_SYNTAXES:
        raise NotImplementedError(
            "Unable to convert the waveform data as the transfer syntax "
            "is not supported by the waveform data handler"
        )

    if 'WaveformSequence' not in ds:
        raise AttributeError(
            "No (5400,0100) Waveform Sequence element found in the dataset"
        )

    for ii, item in enumerate(ds.WaveformSequence):
        required_elements = [
            'NumberOfWaveformChannels', 'NumberOfWaveformSamples',
            'WaveformBitsAllocated', 'WaveformSampleInterpretation',
            'WaveformData'
        ]
        missing = [elem for elem in required_elements if elem not in item]
        if missing:
            raise AttributeError(
                f"Unable to convert the waveform multiplex group with index "
                f"{ii} as the following required elements are missing from "
                f"the sequence item: {', '.join(missing)}"
            )

        # Determine the expected length of the data (without padding)
        bytes_per_sample = item.WaveformBitsAllocated // 8
        nr_samples = item.NumberOfWaveformSamples
        nr_channels = item.NumberOfWaveformChannels
        expected_len = nr_samples * nr_channels * bytes_per_sample

        # Waveform Data is ordered as (C = channel, S = sample):
        # C1S1, C2S1, ..., CnS1, C1S2, ..., CnS2, ..., C1Sm, ..., CnSm
        dtype = WAVEFORM_DTYPES[
            (item.WaveformBitsAllocated, item.WaveformSampleInterpretation)
        ]
        arr = np.frombuffer(item.WaveformData[:expected_len], dtype=dtype)
        # Reshape to (samples, channels) and make writeable
        arr = np.copy(arr.reshape(nr_samples, nr_channels))

        if not as_raw:
            # Apply correction factor (if possible)
            arr = arr.astype('float')
            for jj, ch in enumerate(item.ChannelDefinitionSequence):
                baseline = ch.get("ChannelBaseline", 0.0)
                sensitivity = ch.get("ChannelSensitivity", 1.0)
                correction = ch.get("ChannelSensitivityCorrectionFactor", 1.0)
                arr[..., jj] = (
                    (arr[..., jj] + baseline) * sensitivity * correction
                )

        yield arr


def multiplex_array(ds: "Dataset", index: int = 0, as_raw: bool = True) -> "np.ndarray":  # noqa
    """Return an :class:`~numpy.ndarray` for the multiplex group in the
    *Waveform Sequence* at `index`.

    .. versionadded:: 2.1

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The :class:`Dataset` containing a :dcm:`Waveform
        <part03/sect_C.10.9.html>` module and the *Waveform Sequence* to be
        converted.
    index : int, optional
        The index of the multiplex group to return, default ``0``.
    as_raw : bool, optional
        If ``True`` (default), then return the raw unitless waveform data. If
        ``False`` then attempt to convert the raw data for each channel to the
        quantity specified by the corresponding (003A,0210) *Channel
        Sensitivity* unit.

    Returns
    -------
    np.ndarray
        The waveform data for a multiplex group as an :class:`~numpy.ndarray`
        with shape (samples, channels).
    """
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if transfer_syntax not in SUPPORTED_TRANSFER_SYNTAXES:
        raise NotImplementedError(
            "Unable to convert the waveform data as the transfer syntax "
            "is not supported by the waveform data handler"
        )

    if 'WaveformSequence' not in ds:
        raise AttributeError(
            "No (5400,0100) Waveform Sequence element found in the dataset"
        )

    item = ds.WaveformSequence[index]
    required_elements = [
        'NumberOfWaveformChannels', 'NumberOfWaveformSamples',
        'WaveformBitsAllocated', 'WaveformSampleInterpretation',
        'WaveformData'
    ]
    missing = [elem for elem in required_elements if elem not in item]
    if missing:
        raise AttributeError(
            f"Unable to convert the waveform multiplex group with index "
            f"{index} as the following required elements are missing from "
            f"the sequence item: {', '.join(missing)}"
        )

    # Determine the expected length of the data (without padding)
    bytes_per_sample = item.WaveformBitsAllocated // 8
    nr_samples = item.NumberOfWaveformSamples
    nr_channels = item.NumberOfWaveformChannels
    expected_len = nr_samples * nr_channels * bytes_per_sample

    # Waveform Data is ordered as (C = channel, S = sample):
    # C1S1, C2S1, ..., CnS1, C1S2, ..., CnS2, ..., C1Sm, ..., CnSm
    dtype = WAVEFORM_DTYPES[
        (item.WaveformBitsAllocated, item.WaveformSampleInterpretation)
    ]
    arr = np.frombuffer(item.WaveformData[:expected_len], dtype=dtype)
    # Reshape to (samples, channels) and make writeable
    arr = np.copy(arr.reshape(nr_samples, nr_channels))

    if not as_raw:
        # Apply correction factor (if possible)
        arr = arr.astype('float')
        for jj, channel in enumerate(item.ChannelDefinitionSequence):
            baseline = channel.get("ChannelBaseline", 0.0)
            sensitivity = channel.get("ChannelSensitivity", 1.0)
            correction = channel.get("ChannelSensitivityCorrectionFactor", 1.0)
            arr[..., jj] = (
                (arr[..., jj] + baseline) * sensitivity * correction
            )

    return arr
