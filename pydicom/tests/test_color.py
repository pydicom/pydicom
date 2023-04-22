import pytest

from pydicom.color import ColorManager
from pydicom.config import have_numpy

if have_numpy:
    import numpy as np

try:
    from PIL.ImageCms import ImageCmsProfile, createProfile
    have_pillow = True
except ImportError:
    have_pillow = False


class TestColorManager:

    @pytest.mark.skipif(
        not(have_numpy and have_pillow),
        reason="numpy and pillow are not installed"
    )
    def test_construction(self):
        icc_profile = ImageCmsProfile(createProfile('sRGB')).tobytes()
        ColorManager(icc_profile)

    @pytest.mark.skipif(
        have_numpy and have_pillow,
        reason="numpy and pillow are installed"
    )
    def test_construction_missing_dependencies(self):
        with pytest.raises(RuntimeError):
            ColorManager(b'')

    @pytest.mark.skipif(
        not(have_numpy and have_pillow),
        reason="numpy and pillow are not installed"
    )
    def test_construction_without_profile(self):
        with pytest.raises(TypeError):
            ColorManager()  # type: ignore

    @pytest.mark.skipif(
        not(have_numpy and have_pillow),
        reason="numpy and pillow are not installed"
    )
    def test_transform_frame(self):
        icc_profile = ImageCmsProfile(createProfile('sRGB')).tobytes()
        manager = ColorManager(icc_profile)
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 255
        output = manager.transform_frame(frame)
        assert output.shape == frame.shape
        assert output.dtype == frame.dtype

    @pytest.mark.skipif(
        not(have_numpy and have_pillow),
        reason="numpy and pillow are not installed"
    )
    def test_transform_frame_wrong_shape(self):
        icc_profile = ImageCmsProfile(createProfile('sRGB')).tobytes()
        manager = ColorManager(icc_profile)
        frame = np.ones((10, 10), dtype=np.uint8) * 255
        with pytest.raises(ValueError):
            manager.transform_frame(frame)
