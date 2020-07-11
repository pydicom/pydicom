import pytest

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.waveform_data_handlers import numpy_handler


def test_simple():
    ds = dcmread(get_testdata_file('anonymous_ecg.dcm'))
    generator = ds.waveform_generator
    arr = next(generator)
    import matplotlib.pyplot as plt
    fix, (ax1, ax2, ax3) = plt.subplots(3, 1)
    ax1.plot(arr[:, 0])
    ax2.plot(arr[:, 1])
    ax3.plot(arr[:, 2])
    plt.show()
