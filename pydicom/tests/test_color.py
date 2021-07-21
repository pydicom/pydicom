import numpy as np
import pytest
from PIL.ImageCms import ImageCmsProfile, createProfile

from pydicom.color import ColorManager


class TestColorManager:

    def setup(self):
        self._icc_profile = ImageCmsProfile(createProfile('sRGB')).tobytes()

    def test_construction(self):
        ColorManager(self._icc_profile)

    def test_construction_without_profile(self):
        with pytest.raises(TypeError):
            ColorManager()  # type: ignore

    def test_transform_frame(self):
        manager = ColorManager(self._icc_profile)
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 255
        output = manager.transform_frame(frame)
        assert output.shape == frame.shape
        assert output.dtype == frame.dtype

    def test_transform_frame_wrong_shape(self):
        manager = ColorManager(self._icc_profile)
        frame = np.ones((10, 10), dtype=np.uint8) * 255
        with pytest.raises(ValueError):
            manager.transform_frame(frame)
