# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Test suite for uid.py"""

import pytest

from pydicom.uid import UID, generate_uid, PYDICOM_ROOT_UID


class TestGenerateUID(object):
    def test_generate_uid(self):
        """Test UID generator"""
        # Test standard UID generation with pydicom prefix
        uid = generate_uid()
        assert uid[:26] == PYDICOM_ROOT_UID
        assert len(uid) <= 64

        # Test standard UID generation with no prefix
        uid = generate_uid(None)
        assert uid[:5] == '2.25.'
        assert len(uid) <= 64

        # Test invalid UID prefixes
        for invalid_prefix in (('1' * 63) + '.',
                               '',
                               '.',
                               '1',
                               '1.2',
                               '1.2..3.',
                               '1.a.2.',
                               '1.01.1.'):
            with pytest.raises(ValueError):
                generate_uid(prefix=invalid_prefix)

        # Test some valid prefixes and make sure they survive
        for valid_prefix in ('0.',
                             '1.',
                             '1.23.',
                             '1.0.23.',
                             ('1' * 62) + '.',
                             '1.2.3.444444.'):
            uid = generate_uid(prefix=valid_prefix)

            assert uid[:len(valid_prefix)] == valid_prefix
            assert len(uid) <= 64


class TestUID(object):
    """Test DICOM UIDs"""
    @classmethod
    def setup_class(self):
        """Set default UID"""
        self.uid = UID('1.2.840.10008.1.2')

    def test_equality(self):
        """Test that UID.__eq__ works."""
        assert self.uid == UID('1.2.840.10008.1.2')
        assert self.uid == '1.2.840.10008.1.2'
        assert self.uid == 'Implicit VR Little Endian'
        assert not self.uid == UID('1.2.840.10008.1.2.1')
        assert not self.uid == '1.2.840.10008.1.2.1'
        assert not self.uid == 'Explicit VR Little Endian'
        # Issue 96
        assert not self.uid == 3
        assert not self.uid is None

    def test_inequality(self):
        """Test that UID.__ne__ works."""
        assert not self.uid != UID('1.2.840.10008.1.2')
        assert not self.uid != '1.2.840.10008.1.2'
        assert not self.uid != 'Implicit VR Little Endian'
        assert self.uid != UID('1.2.840.10008.1.2.1')
        assert self.uid != '1.2.840.10008.1.2.1'
        assert self.uid != 'Explicit VR Little Endian'
        # Issue 96
        assert self.uid != 3
        assert self.uid is not None

    def test_hash(self):
        """Test that UID.__hash_- works."""
        assert hash(self.uid) == hash(self.uid)

    def test_str(self):
        """Test that UID.__str__ works."""
        assert self.uid.__str__() == 'Implicit VR Little Endian'

    def test_is_implicit_vr(self):
        """Test that UID.is_implicit_VR works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert UID('1.2.840.10008.1.2').is_implicit_VR
        assert not UID('1.2.840.10008.1.2.1').is_implicit_VR
        assert not UID('1.2.840.10008.1.2.1.99').is_implicit_VR
        assert not UID('1.2.840.10008.1.2.2').is_implicit_VR
        assert not UID('1.2.840.10008.1.2.4.50').is_implicit_VR

        with pytest.raises(ValueError):
            UID('1.2.840.10008.5.1.4.1.1.2').is_implicit_VR

    def test_is_little_endian(self):
        """Test that UID.is_little_endian works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert UID('1.2.840.10008.1.2').is_little_endian
        assert UID('1.2.840.10008.1.2.1').is_little_endian
        assert UID('1.2.840.10008.1.2.1.99').is_little_endian
        assert not UID('1.2.840.10008.1.2.2').is_little_endian
        assert UID('1.2.840.10008.1.2.4.50').is_little_endian

        with pytest.raises(ValueError):
            UID('1.2.840.10008.5.1.4.1.1.2').is_little_endian

    def test_is_deflated(self):
        """Test that UID.is_deflated works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert not UID('1.2.840.10008.1.2').is_deflated
        assert not UID('1.2.840.10008.1.2.1').is_deflated
        assert UID('1.2.840.10008.1.2.1.99').is_deflated
        assert not UID('1.2.840.10008.1.2.2').is_deflated
        assert not UID('1.2.840.10008.1.2.4.50').is_deflated

        with pytest.raises(ValueError):
            UID('1.2.840.10008.5.1.4.1.1.2').is_deflated

    def test_is_transfer_syntax(self):
        """Test that UID.is_transfer_syntax works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert UID('1.2.840.10008.1.2').is_transfer_syntax
        assert UID('1.2.840.10008.1.2.1').is_transfer_syntax
        assert UID('1.2.840.10008.1.2.1.99').is_transfer_syntax
        assert UID('1.2.840.10008.1.2.2').is_transfer_syntax
        assert UID('1.2.840.10008.1.2.4.50').is_transfer_syntax

        assert not UID('1.2.840.10008.5.1.4.1.1.2').is_transfer_syntax

    def test_is_compressed(self):
        """Test that UID.is_compressed works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert not UID('1.2.840.10008.1.2').is_compressed
        assert not UID('1.2.840.10008.1.2.1').is_compressed
        assert not UID('1.2.840.10008.1.2.1.99').is_compressed
        assert not UID('1.2.840.10008.1.2.2').is_compressed
        assert UID('1.2.840.10008.1.2.4.50').is_compressed

        with pytest.raises(ValueError):
            UID('1.2.840.10008.5.1.4.1.1.2').is_compressed

    def test_is_encapsulated(self):
        """Test that UID.is_encapsulated works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        assert not UID('1.2.840.10008.1.2').is_encapsulated
        assert not UID('1.2.840.10008.1.2.1').is_encapsulated
        assert not UID('1.2.840.10008.1.2.1.99').is_encapsulated
        assert not UID('1.2.840.10008.1.2.2').is_encapsulated
        assert UID('1.2.840.10008.1.2.4.50').is_encapsulated

        with pytest.raises(ValueError):
            UID('1.2.840.10008.5.1.4.1.1.2').is_encapsulated

    def test_name(self):
        """Test that UID.name works."""
        assert self.uid.name == 'Implicit VR Little Endian'
        assert UID('1.2.840.10008.5.1.4.1.1.2').name == 'CT Image Storage'

    def test_type(self):
        """Test that UID.type works."""
        assert self.uid.type == 'Transfer Syntax'
        assert UID('1.2.840.10008.5.1.4.1.1.2').type == 'SOP Class'

    def test_info(self):
        """Test that UID.info works."""
        assert self.uid.info == 'Default Transfer Syntax for DICOM'
        assert UID('1.2.840.10008.5.1.4.1.1.2').info == ''

    def test_is_retired(self):
        """Test that UID.is_retired works."""
        assert not self.uid.is_retired
        assert UID('1.2.840.10008.1.2.2').is_retired

    def test_is_valid(self):
        """Test that UID.is_valid works."""
        for invalid_uid in ('1' * 65,
                            '1.' + ('2' * 63),
                            '',
                            '.',
                            '1.',
                            '1.01',
                            '1.a.2'):
            assert not UID(invalid_uid).is_valid

        for valid_uid in ('0',
                          '1',
                          '0.1',
                          '1' * 64,
                          '1.' + ('2' * 62),
                          '1.0.23'):
            assert UID(valid_uid).is_valid

    def test_is_private(self):
        """Test the is_private property"""
        private_uid = UID('1.2.840.10009.1.2')
        assert private_uid.is_private
        assert not self.uid.is_private


class TestUIDPrivate(object):
    """Test private UIDs"""
    @classmethod
    def setup_class(self):
        """Set default UID"""
        self.uid = UID('9.9.999.90009.1.2')

    def test_equality(self):
        """Test that UID.__eq__ works with private UIDs."""
        assert self.uid == UID('9.9.999.90009.1.2')
        assert self.uid == '9.9.999.90009.1.2'
        assert not self.uid == UID('9.9.999.90009.1.3')
        assert not self.uid == '9.9.999.90009.1.3'

    def test_inequality(self):
        """Test that UID.__ne__ works with private UIDs."""
        assert not self.uid != UID('9.9.999.90009.1.2')
        assert not self.uid != '9.9.999.90009.1.2'
        assert self.uid != UID('9.9.999.90009.1.3')
        assert self.uid != '9.9.999.90009.1.3'

    def test_hash(self):
        """Test that UID.__hash_- works with private UIDs."""
        assert hash(self.uid) == hash(self.uid)

    def test_str(self):
        """Test that UID.__str__ works with private UIDs."""
        assert self.uid.__str__() == '9.9.999.90009.1.2'

    def test_is_implicit_vr(self):
        """Test that UID.is_implicit_VR works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_implicit_VR

    def test_is_little_endian(self):
        """Test that UID.is_little_endian works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_little_endian

    def test_is_deflated(self):
        """Test that UID.is_deflated works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_deflated

    def test_is_transfer_syntax(self):
        """Test that UID.is_transfer_syntax works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_transfer_syntax

    def test_is_compressed(self):
        """Test that UID.is_compressed works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_compressed

    def test_is_encapsulated(self):
        """Test that UID.is_encapsulated works with private UIDs."""
        with pytest.raises(ValueError):
            self.uid.is_encapsulated

    def test_name(self):
        """Test that UID.name works with private UIDs."""
        assert self.uid.name == '9.9.999.90009.1.2'

    def test_type(self):
        """Test that UID.type works with private UIDs."""
        assert self.uid.type == ''

    def test_info(self):
        """Test that UID.info works with private UIDs."""
        assert self.uid.info == ''

    def test_is_retired(self):
        """Test that UID.is_retired works with private UIDs."""
        assert not self.uid.is_retired

    def test_is_valid(self):
        """Test that UID.is_valid works with private UIDs."""
        assert self.uid.is_valid

    def test_is_private(self):
        """Test that UID.is_private works with private UIDs."""
        assert self.uid.is_private
