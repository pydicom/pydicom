# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test for tests/testing.py"""
from warnings import warn

import pytest

from .testing import assert_raises_regex, assert_warns_regex


class TestAssertRaisesRegex(object):
    """Test tests/testing.assert_raises_regex"""
    def test_good_raise_good_match(self):
        """Test regex match with good raised exception"""
        def raise_ex():
            raise ValueError("Something happened 123")

        assert_raises_regex(ValueError, "Something happened", raise_ex)
        assert_raises_regex(ValueError, "Something", raise_ex)
        assert_raises_regex(ValueError, ".", raise_ex)
        assert_raises_regex(ValueError, "[0-9]{3}", raise_ex)

    def test_good_raise_no_match(self):
        """Test no regex match with good raised exception"""
        def raise_ex():
            raise ValueError("Something happened")

        with pytest.raises(AssertionError):
            assert_raises_regex(ValueError,
                                "Something didn't happen",
                                raise_ex)
        with pytest.raises(AssertionError):
            assert_raises_regex(ValueError, "[0-9]", raise_ex)

    def test_bad_raise_good_match(self):
        """Test regex match with bad raised exception"""
        def raise_ex():
            raise NotImplementedError("Something happened 123")

        with pytest.raises(NotImplementedError):
            assert_raises_regex(ValueError, "Something happened", raise_ex)

    def test_bad_raise_bad_match(self):
        """Test no regex match with bad raised exception"""
        def raise_ex():
            raise NotImplementedError("Something happened")

        with pytest.raises(NotImplementedError):
            assert_raises_regex(ValueError,
                                "Something didn't happen",
                                raise_ex)


class TestAssertWarnsRegex(object):
    """Test tests/testing.assert_warns_regex"""
    def test_good_raise_good_match(self):
        """Test regex match with good fired warning"""
        def fire_warn():
            warn("Something happened 123", DeprecationWarning)

        assert_warns_regex(DeprecationWarning, "Something happened", fire_warn)
        assert_warns_regex(DeprecationWarning, "Something", fire_warn)
        assert_warns_regex(DeprecationWarning, ".", fire_warn)
        assert_warns_regex(DeprecationWarning, "[0-9]{3}", fire_warn)

    def test_good_raise_no_match(self):
        """Test no regex match with good fired warningn"""
        def fire_warn():
            warn("Something didn't happen", DeprecationWarning)

        with pytest.raises(AssertionError):
            assert_warns_regex(DeprecationWarning,
                               "Something happened",
                               fire_warn)

    def test_bad_raise_good_match(self):
        """Test regex match with no fired warning"""
        def fire_warn():
            warn("Something happened 123", UserWarning)

        with pytest.raises(AssertionError):
            assert_warns_regex(DeprecationWarning,
                               "Something happen",
                               fire_warn)

    def test_bad_raise_bad_match(self):
        """Test no regex match with no fired warning"""
        def fire_warn():
            warn("Something happened 123", UserWarning)

        with pytest.raises(AssertionError):
            assert_warns_regex(DeprecationWarning,
                               "Something didn't happen",
                               fire_warn)
