# -*- coding: utf-8 -*-
# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Fixtures used in different tests."""

import pytest
from pydicom import config
from pydicom.config import settings


@pytest.fixture
def enforce_valid_values():
    value = settings.reading_validation_mode
    settings.reading_validation_mode = config.RAISE
    yield
    settings.reading_validation_mode = value


@pytest.fixture
def allow_reading_invalid_values():
    value = settings.reading_validation_mode
    settings.reading_validation_mode = config.WARN
    yield
    settings.reading_validation_mode = value


@pytest.fixture
def allow_writing_invalid_values():
    value = settings.writing_validation_mode
    settings.writing_validation_mode = config.WARN
    yield
    settings.writing_validation_mode = value


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
def dont_raise_on_writing_invalid_value():
    old_value = settings.writing_validation_mode
    settings.writing_validation_mode = config.WARN
    yield
    settings.writing_validation_mode = old_value


@pytest.fixture
def raise_on_writing_invalid_value():
    old_value = settings.writing_validation_mode
    settings.writing_validation_mode = config.RAISE
    yield
    settings.writing_validation_mode = old_value


@pytest.fixture
def disable_value_validation():
    with config.disable_value_validation():
        yield
