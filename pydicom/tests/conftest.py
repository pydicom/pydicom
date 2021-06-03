# -*- coding: utf-8 -*-
# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Fixtures used in different tests."""

import pytest

from pydicom import config


@pytest.fixture
def enforce_valid_values():
    value = config.enforce_valid_values
    config.enforce_valid_values = True
    yield
    config.enforce_valid_values = value


@pytest.fixture
def allow_invalid_values():
    value = config.enforce_valid_values
    config.enforce_valid_values = False
    yield
    config.enforce_valid_values = value


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
