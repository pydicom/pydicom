"""Tests for the hooks module."""

import pytest

from pydicom.hooks import hooks


class TestHooks:
    """Tests for Hooks"""

    def test_unknown_hook_raises(self):
        """Test invalid hook name or function object raises an exception."""
        msg = "'func' must be a callable function"
        with pytest.raises(TypeError, match=msg):
            hooks.register_hook("foo", None)

        def foo():
            pass

        msg = "Unknown hook 'foo'"
        with pytest.raises(ValueError, match=msg):
            hooks.register_hook("foo", foo)

    def test_unknown_hook_kwargs_raises(self):
        """Test invalid hook name or kwargs object raises an exception."""
        msg = "'kwargs' must be a dict, not 'NoneType'"
        with pytest.raises(TypeError, match=msg):
            hooks.register_kwargs("foo", None)

        msg = "Unknown hook 'foo'"
        with pytest.raises(ValueError, match=msg):
            hooks.register_kwargs("foo", {})

    def test_register_hook(self):
        pass

    def test_register_kwargs(self):
        pass
