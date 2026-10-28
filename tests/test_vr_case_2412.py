"""Regression tests for https://github.com/pydicom/pydicom/issues/2412

A VR written in lower or mixed case used to be mistaken for an implicit-VR switch: its two
bytes failed the ``ENCODED_VR`` membership test and also fell outside the
``b"AA" <= vr <= b"ZZ"`` range (lowercase ASCII sorts after uppercase), so they were read as
part of a 4-byte length. Every following element was then lost, silently.

These tests pin the tolerant behaviour requested in the issue: a VR that is two letters is
normalised to uppercase, so the element after it survives.

``read_dataset`` is used rather than ``dcmread`` because the bytes here carry no file meta, and
without meta pydicom assumes implicit VR - which would parse these explicit-VR bytes as garbage.
"""

import io

import pytest

from pydicom import config
from pydicom.filereader import read_dataset

# (0010,0010) PN, then the element under test, then two more so a misalignment is visible
LEAD = b"\x10\x00\x10\x00PN\x08\x00DOE^JOHN"


def _tail(vr: bytes) -> bytes:
    return (
        b"\x08\x00\x60\x00" + vr + b"\x02\x00MR"
        b"\x10\x00\x20\x00LO\x06\x00ID1234"
        b"\x08\x00\x30\x10LO\x0c\x00DESCRIPTION "
    )


def _parse(vr: bytes):
    fp = io.BytesIO(LEAD + _tail(vr))
    return read_dataset(fp, is_implicit_VR=False, is_little_endian=True)


def _tags(ds) -> set:
    return {"%04X%04X" % (el.tag.group, el.tag.element) for el in ds.iterall()}


@pytest.mark.parametrize("vr", [b"cs", b"Cs", b"cS", b"CS"])
def test_lowercase_vr_does_not_lose_following_elements(vr):
    """A letter VR in the wrong case must not misalign the rest of the data set."""
    with config.disable_value_validation():
        ds = _parse(vr)

    assert {"00100010", "00080060", "00100020", "00081030"} <= _tags(ds)


def test_lowercase_vr_value_is_preserved():
    """The element itself must still carry its value after normalisation."""
    with config.disable_value_validation():
        ds = _parse(b"cs")

    assert ds[0x00080060].value == "MR"


def test_non_letter_vr_still_uses_the_implicit_fallback():
    """A VR that is not two letters is not a valid VR, so the pre-existing
    implicit-VR fallback still applies - this pins that it was not changed."""
    with config.disable_value_validation():
        ds = _parse(b"1S")

    assert "00100010" in _tags(ds)
