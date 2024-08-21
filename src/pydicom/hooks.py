# Copyright 2008-2024 pydicom authors. See LICENSE file for details.

from typing import Any, TYPE_CHECKING, Protocol
from collections.abc import MutableSequence, Callable

from pydicom import config
from pydicom.datadict import dictionary_VR, private_dictionary_VR
from pydicom.errors import BytesLengthException
from pydicom.misc import warn_and_log
from pydicom.tag import BaseTag, _LUT_DESCRIPTOR_TAGS
from pydicom.valuerep import VR


if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset
    from pydicom.dataelem import RawDataElement

    class RawDataHook(Protocol):
        def __call__(
            self,
            raw: RawDataElement,
            data: dict[str, Any],
            *,
            encoding: str | MutableSequence[str] | None = ...,
            ds: Dataset | None = ...,
            **kwargs: Any,
        ) -> None: ...


class Hooks:
    """Management class for callback functions.

    .. versionadded:: 3.0

    .. warning::

        New instances of this class should not be created, instead use the instance
        imported with ``from pydicom.hooks import hooks``.

    **Available Hooks**

    For conversion of raw element data to :class:`~pydicom.dataelem.DataElement`
    using :func:`~pydicom.dataelem.convert_raw_data_element`:

    * ``"raw_element_vr"``: function to perform VR lookups for raw elements,
      default :func:`raw_element_vr`.
    * ``"raw_element_value"``: function to convert raw element values to types
      appropriate for the VR, default :func:`raw_element_value`.
    * ``"raw_element_kwargs"``: `kwargs` :class:`dict` passed to the callback
      functions.
    """

    def __init__(self) -> None:
        """Initialize a new ``Hooks`` instance."""
        self.raw_element_value: RawDataHook
        self.raw_element_vr: RawDataHook
        self.raw_element_kwargs: dict[str, Any] = {}

    def register_callback(self, hook: str, func: Callable) -> None:
        """Register the callback function `func` to a hook.

        Example
        -------

        .. code-block:: python

            from pydicom import dcmread
            from pydicom.hooks import hooks, raw_element_value_fix_separator

            hooks.register_callback(
                "raw_element_value", raw_element_value_fix_separator
            )
            kwargs = {"target_VRs": ("DS", "IS")}
            hooks.register_kwargs("raw_element_kwargs", kwargs)

            ds = dcmread("path/to/dataset.dcm")

        Parameters
        ----------
        hook : str
            The name of the hook to register the function to, allowed values
            ``"raw_element_vr"`` and ``"raw_element_value"``.
        func : Callable
            The callback function to use with the hook. Only one callback function can
            be used per hook. For details on the required function signatures please
            see the documentation for the corresponding calling function.
        """
        if not callable(func):
            raise TypeError("'func' must be a callable function")

        if hook == "raw_element_value":
            self.raw_element_value = func
        elif hook == "raw_element_vr":
            self.raw_element_vr = func
        else:
            raise ValueError(f"Unknown hook '{hook}'")

    def register_kwargs(self, hook: str, kwargs: dict[str, Any]) -> None:
        """Register a `kwargs` :class:`dict` to be passed to the corresponding
        callback function(s).

        Parameters
        ----------
        hook : str
            The name of the hook to register `kwargs` to, allowed value
            ``"raw_element_kwargs"``.
        kwargs : dict[str, Any]
            A :class:`dict` containing keyword arguments to be passed to the
            hook's corresponding callback function(s).
        """
        if not isinstance(kwargs, dict):
            raise TypeError(f"'kwargs' must be a dict, not '{type(kwargs).__name__}'")

        if hook == "raw_element_kwargs":
            self.raw_element_kwargs = kwargs
        else:
            raise ValueError(f"Unknown hook '{hook}'")


def _private_vr_for_tag(ds: "Dataset | None", tag: BaseTag) -> str:
    """Return the VR for a known private tag, otherwise "UN".

    Parameters
    ----------
    ds : Dataset, optional
        The dataset needed for the private creator lookup.
        If not given, "UN" is returned.
    tag : BaseTag
        The private tag to lookup. The caller has to ensure that the
        tag is private.

    Returns
    -------
    str
        "LO" if the tag is a private creator, the VR of the private tag if
        found in the private dictionary, or "UN".
    """
    if tag.is_private_creator:
        return VR.LO

    # invalid private tags are handled as UN
    if ds is not None and (tag.element & 0xFF00):
        private_creator_tag = tag.group << 16 | (tag.element >> 8)
        private_creator = ds.get(private_creator_tag, "")
        if private_creator:
            try:
                return private_dictionary_VR(tag, private_creator.value)
            except KeyError:
                pass

    return VR.UN


def raw_element_vr(
    raw: "RawDataElement",
    data: dict[str, Any],
    *,
    encoding: str | MutableSequence[str] | None = None,
    ds: "Dataset | None" = None,
    **kwargs: Any,
) -> None:
    """Determine the VR to use for `raw`.

    .. versionadded:: 3.0

    Default callback function for the ``"raw_element_vr"`` hook.

    Parameters
    ----------
    raw : RawDataElement
        The raw data element to determine the VR for.
    data : dict[str, Any]
        A dict to store the results of the VR lookup, which should be added
        as ``{"VR": str}``.
    ds : pydicom.dataset.Dataset | None
        The dataset the element belongs to.
    **kwargs: dict[str, Any]
        Additional keyword arguments.
    """
    vr = raw.VR
    if vr is None:  # Can be if was implicit VR
        try:
            vr = dictionary_VR(raw.tag)
        except KeyError:
            # just read the bytes, no way to know what they mean
            if raw.tag.is_private:
                # for VR for private tags see PS3.5, 6.2.2
                vr = _private_vr_for_tag(ds, raw.tag)

            # group length tag implied in versions < 3.0
            elif raw.tag.element == 0:
                vr = VR.UL
            else:
                msg = f"VR lookup failed for the raw element with tag {raw.tag}"
                if config.settings.reading_validation_mode == config.RAISE:
                    raise KeyError(msg)

                vr = VR.UN
                warn_and_log(f"{msg} - setting VR to 'UN'")
    elif vr == VR.UN and config.replace_un_with_known_vr:
        # handle rare case of incorrectly set 'UN' in explicit encoding
        # see also DataElement.__init__()
        if raw.tag.is_private:
            vr = _private_vr_for_tag(ds, raw.tag)
        elif raw.value is None or len(raw.value) < 0xFFFF:
            try:
                vr = dictionary_VR(raw.tag)
            except KeyError:
                pass

    data["VR"] = vr


def raw_element_value(
    raw: "RawDataElement",
    data: dict[str, Any],
    *,
    encoding: str | MutableSequence[str] | None = None,
    ds: "Dataset | None" = None,
    **kwargs: Any,
) -> None:
    """Convert the encoded value for `raw` to an appropriate type.

    .. versionadded:: 3.0

    Will set the VR to **UN** if unable to convert the value.

    Default callback function for the ``"raw_element_value"`` hook.

    Parameters
    ----------
    raw : RawDataElement
        The raw data element to determine the value for.
    data : dict[str, Any]
        A dict to store the results of the value conversion, which should be added
        as ``{"value": Any}``.
    encoding : str | MutableSequence[str] | None
        The character set encoding to use for text VRs.
    **kwargs: dict[str, Any]
        Additional keyword arguments.
    """
    from pydicom.values import convert_value

    vr = data["VR"]
    try:
        value = convert_value(vr, raw, encoding)
    except NotImplementedError as exc:
        raise NotImplementedError(f"{exc} in tag {raw.tag}")
    except BytesLengthException as exc:
        # Failed conversion, either raise or convert to a UN VR
        msg = (
            f"{exc} This occurred while trying to parse {raw.tag} according "
            f"to VR '{raw.VR}'."
        )
        if not config.convert_wrong_length_to_UN:
            raise BytesLengthException(
                f"{msg} To replace this error with a warning set "
                "pydicom.config.convert_wrong_length_to_UN = True."
            )

        warn_and_log(f"{msg} Setting VR to 'UN'.")
        data["VR"] = VR.UN
        value = raw.value

    if raw.tag in _LUT_DESCRIPTOR_TAGS:
        # We only fix the first value as the third value is 8 or 16
        if value and isinstance(value, list):
            try:
                if value[0] < 0:
                    value[0] += 65536
            except Exception:
                pass

    data["value"] = value


def raw_element_value_fix_separator(
    raw: "RawDataElement",
    data: dict[str, Any],
    *,
    encoding: str | MutableSequence[str] | None = None,
    ds: "Dataset | None",
    separator: str | bytes = b",",
    target_VRs: tuple[str, ...] | None = None,
    **kwargs: Any,
) -> None:
    """Convenience function to fix values with an invalid multivalue separator.

    .. versionadded:: 3.0

    Alternative callback function for the ``"raw_element_value"`` hook.

    Example
    -------

    Fix **DS** and **IS** elements that use an invalid ":" character as the
    multivalue separator::

        from pydicom import dcmread
        from pydicom.hooks import hooks, raw_element_value_fix_separator

        hooks.register_callback(
            "raw_element_value",
            raw_element_value_fix_separator,
        )
        hooks.register_kwargs(
            "raw_element",
            {"target_VRs": ("DS", "IS"), "separator": b":"},
        )

        ds = dcmread("path/to/dataset.dcm")


    Parameters
    ----------
    raw : RawDataElement
        The raw data element to determine the value for.
    data : dict[str, Any]
        A dict to store the results of the value conversion, which should be added
        as ``{"value": Any}``.
    encoding : str | MutableSequence[str] | None
        The character set encoding to use for text VRs.
    separator : str | bytes, optional
        The invalid separator character to be replaced by an ASCII backslash (0x5C).
    target_VRs : tuple[str, ...], optional
        The VRs the fix should apply.
    **kwargs: dict[str, Any]
        Additional keyword arguments.
    """
    vr = data["VR"]
    if target_VRs and vr in target_VRs and isinstance(raw.value, bytes):
        if isinstance(separator, str):
            separator = separator.encode("ascii")

        raw = raw._replace(value=raw.value.replace(separator, b"\x5C"))

    raw_element_value(raw, data, encoding=encoding, ds=ds, **kwargs)


def raw_element_value_retry(
    raw: "RawDataElement",
    data: dict[str, Any],
    *,
    encoding: str | MutableSequence[str] | None = None,
    ds: "Dataset | None",
    target_VRs: dict[str, tuple[str, ...]] | None = None,
    **kwargs: Any,
) -> None:
    """Convenience function to retry value conversion using a different VR.

    .. versionadded:: 3.0

    Alternative callback function for the ``"raw_element_value"`` hook.

    Example
    -------

    Retry the value conversion for **DS** elements using **US** or **SS**::

        from pydicom import dcmread
        from pydicom.hooks import hooks, raw_element_value_retry

        hooks.register_callback(
            "raw_element_value",
            raw_element_value_retry,
        )
        hooks.register_kwargs(
            "raw_element",
            {"target_VRs": {"DS": ("US", "SS")}},
        )

        ds = dcmread("path/to/dataset.dcm")

    Parameters
    ----------
    raw : RawDataElement
        The raw data element to determine the value for.
    data : dict[str, Any]
        A dict to store the results of the value conversion, which should be added
        as ``{"value": Any}``.
    encoding : str | MutableSequence[str] | None
        The character set encoding to use for text VRs.
    target_VRs : dict[str, tuple[str, ...]], optional
        The ``{VRs the fix should apply: tuple of alternative VRs to try}``.
    **kwargs: dict[str, Any]
        Additional keyword arguments.
    """
    from pydicom.values import convert_value

    try:
        raw_element_value(raw, data, encoding=encoding, ds=ds, **kwargs)
    except Exception as exc:
        vr = data["VR"]
        if target_VRs and vr in target_VRs:
            for candidate in target_VRs[vr]:
                try:
                    data["value"] = convert_value(candidate, raw)
                    data["VR"] = candidate
                    return
                except Exception:
                    pass

        raise exc


hooks: Hooks = Hooks()
"""The global :class:`~pydicom.hooks.Hooks` singleton.

.. versionadded:: 3.0
"""
hooks.raw_element_value = raw_element_value
hooks.raw_element_vr = raw_element_vr
