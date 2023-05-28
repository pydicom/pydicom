# -*- coding: utf-8 -*-
# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Fixtures used in different tests."""

import pytest
from pydicom import config
from pydicom.data import get_testdata_file


@pytest.fixture
def enforce_valid_values():
    value = config.settings.reading_validation_mode
    config.settings.reading_validation_mode = config.RAISE
    yield
    config.settings.reading_validation_mode = value


@pytest.fixture
def allow_reading_invalid_values():
    value = config.settings.reading_validation_mode
    config.settings.reading_validation_mode = config.WARN
    yield
    config.settings.reading_validation_mode = value


@pytest.fixture
def enforce_writing_invalid_values():
    value = config.settings.writing_validation_mode
    config.settings.writing_validation_mode = config.RAISE
    yield
    config.settings.writing_validation_mode = value


@pytest.fixture
def allow_writing_invalid_values():
    value = config.settings.writing_validation_mode
    config.settings.writing_validation_mode = config.WARN
    yield
    config.settings.writing_validation_mode = value


@pytest.fixture
def no_numpy_use():
    use_ds_numpy = config.use_DS_numpy
    use_is_numpy = config.use_IS_numpy
    config.use_DS_numpy = False
    config.use_IS_numpy = False
    yield
    config.use_DS_numpy = use_ds_numpy
    config.use_IS_numpy = use_is_numpy


@pytest.fixture
def no_datetime_conversion():
    datetime_conversion = config.datetime_conversion
    config.datetime_conversion = False
    yield
    config.datetime_conversion = datetime_conversion


@pytest.fixture
def dont_replace_un_with_known_vr():
    old_value = config.replace_un_with_known_vr
    config.replace_un_with_known_vr = False
    yield
    config.replace_un_with_known_vr = old_value


@pytest.fixture
def dont_replace_un_with_sq_vr():
    old_value = config.settings.infer_sq_for_un_vr
    config.settings.infer_sq_for_un_vr = False
    yield
    config.settings.infer_sq_for_un_vr = old_value


@pytest.fixture
def dont_raise_on_writing_invalid_value():
    old_value = config.settings.writing_validation_mode
    config.settings.writing_validation_mode = config.WARN
    yield
    config.settings.writing_validation_mode = old_value


@pytest.fixture
def raise_on_writing_invalid_value():
    old_value = config.settings.writing_validation_mode
    config.settings.writing_validation_mode = config.RAISE
    yield
    config.settings.writing_validation_mode = old_value


@pytest.fixture
def disable_value_validation():
    with config.disable_value_validation():
        yield


# fixtures for often used testdata file names

@pytest.fixture(scope="session")
def ct_name():
    yield get_testdata_file("CT_small.dcm")


@pytest.fixture(scope="session")
def mr_name():
    yield get_testdata_file("MR_small.dcm")


@pytest.fixture(scope="module")
def mr_implicit_name():
    yield get_testdata_file("MR_small_implicit.dcm")


@pytest.fixture(scope="session")
def rle_mr_name():
    yield get_testdata_file("MR_small_RLE.dcm")


@pytest.fixture(scope="session")
def rtplan_name():
    yield get_testdata_file("rtplan.dcm")


@pytest.fixture(scope="session")
def rtdose_name():
    yield get_testdata_file("rtdose.dcm")


@pytest.fixture(scope="session")
def rtstruct_name():
    yield get_testdata_file("rtstruct.dcm")


@pytest.fixture(scope="session")
def truncated_mr_name():
    yield get_testdata_file("MR_truncated.dcm")


@pytest.fixture(scope="session")
def jpeg2000_name():
    yield get_testdata_file("JPEG2000.dcm")


@pytest.fixture(scope="session")
def jpeg2000_lossless_name():
    yield get_testdata_file("MR_small_jp2klossless.dcm")


@pytest.fixture(scope="session")
def jpeg_ls_lossless_name():
    yield get_testdata_file("MR_small_jpeg_ls_lossless.dcm")


@pytest.fixture(scope="session")
def jpeg_lossy_name():
    yield get_testdata_file("JPEG-lossy.dcm")


@pytest.fixture(scope="session")
def jpeg_lossless_name():
    yield get_testdata_file("JPEG-LL.dcm")


@pytest.fixture(scope="session")
def emri_jpeg_ls_lossless_name():
    yield get_testdata_file("emri_small_jpeg_ls_lossless.dcm")


@pytest.fixture(scope="session")
def emri_jpeg_2k_lossless_name():
    yield get_testdata_file("emri_small_jpeg_2k_lossless.dcm")


@pytest.fixture(scope="session")
def color_3d_jpeg_baseline_name():
    yield get_testdata_file("color3d_jpeg_baseline.dcm")


@pytest.fixture(scope="session")
def deflate_name():
    yield get_testdata_file("image_dfl.dcm")


@pytest.fixture(scope="session")
def color_pl_name():
    yield get_testdata_file("color-pl.dcm")


@pytest.fixture(scope="session")
def emri_name():
    yield get_testdata_file("emri_small.dcm")


@pytest.fixture(scope="session")
def sc_rgb_name():
    yield get_testdata_file("SC_rgb.dcm")


@pytest.fixture(scope="session")
def mono_8bit_1frame_name():
    yield get_testdata_file("OBXXXX1A.dcm")


@pytest.fixture(scope="session")
def rgb_32bit_expl_name():
    yield get_testdata_file("SC_rgb_32bit.dcm")


@pytest.fixture(scope="session")
def rgb_8bit_2frames_name():
    yield get_testdata_file("SC_rgb_2frame.dcm")
