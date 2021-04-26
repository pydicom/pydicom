

from pydicom.encaps import encapsulate, encapsulate_extended
from pydicom.encoders import Encoder
from pydicom.uid import RLELossless



class PyLibJPEGEncoder(Encoder):
    def __init__(self, ds, uid):
        self.arr = arr
        self.ds = ds
        self.uid = uid

    @classmethod
    def is_encodeable(cls, ds, uid, data_type):
        if data_type != 'PixelData':
            return False

        if uid not in cls.uids:
            return False

        if uid == RLELossless:
            if ds.Rows > 2**16 - 1 or ds.Columns > 2**16 - 1:
                return False

            if ds.SamplesPerPixel not in (1, 3):
                return False

            if ds.BitsAllocated not in (8, 16, 32, 64):
                return False

            if ds.SamplesPerPixel * ds.BitsAllocated > 15:
                return False
        else:
            return False

        return True

    def encode(self, arr, uid, **kwargs):
        pass
