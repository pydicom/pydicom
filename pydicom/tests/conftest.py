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
