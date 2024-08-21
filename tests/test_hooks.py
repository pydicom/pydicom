"""Tests for the hooks module."""

import pytest

from pydicom.hooks import hooks, raw_element_vr, raw_element_value


@pytest.fixture
def reset_hooks():
    original = (
        hooks.raw_element_vr,
        hooks.raw_element_value,
        hooks.raw_element_kwargs,
    )
    yield
    (
        hooks.raw_element_vr,
        hooks.raw_element_value,
        hooks.raw_element_kwargs,
    ) = original


class TestHooks:
    """Tests for Hooks"""

    def test_unknown_hook_raises(self):
        """Test invalid hook name or function object raises an exception."""
        msg = "'func' must be a callable function"
        with pytest.raises(TypeError, match=msg):
            hooks.register_callback("foo", None)

        def foo():
            pass

        msg = "Unknown hook 'foo'"
        with pytest.raises(ValueError, match=msg):
            hooks.register_callback("foo", foo)

    def test_unknown_hook_kwargs_raises(self):
        """Test invalid hook name or kwargs object raises an exception."""
        msg = "'kwargs' must be a dict, not 'NoneType'"
        with pytest.raises(TypeError, match=msg):
            hooks.register_kwargs("foo", None)

        msg = "Unknown hook 'foo'"
        with pytest.raises(ValueError, match=msg):
            hooks.register_kwargs("foo", {})

    def test_register_callback(self, reset_hooks):
        """Test setting the functions for a hook."""
        assert hooks.raw_element_vr == raw_element_vr
        assert hooks.raw_element_value == raw_element_value

        def foo():
            pass

        def bar():
            pass

        hooks.register_callback("raw_element_vr", foo)
        hooks.register_callback("raw_element_value", bar)

        assert hooks.raw_element_vr == foo
        assert hooks.raw_element_value == bar

    def test_register_kwargs(self, reset_hooks):
        """Test setting the kwargs for a hook function"""
        d = {"a": 1, 2: "foo"}
        assert hooks.raw_element_kwargs == {}
        hooks.register_kwargs("raw_element_kwargs", d)
        assert hooks.raw_element_kwargs == d
