"""Test suite for uid.py"""

import unittest

from pydicom.uid import UID, generate_uid, PYDICOM_ROOT_UID


class TestGenerateUID(unittest.TestCase):
    def testGenerateUID(self):
        """Test UID generator"""
        # Test standard UID generation with pydicom prefix
        uid = generate_uid()
        self.assertEqual(uid[:26], PYDICOM_ROOT_UID)
        self.assertTrue(len(uid) <= 64)

        # Test standard UID generation with no prefix
        uid = generate_uid(None)
        self.assertEqual(uid[:5], '2.25.')
        self.assertTrue(len(uid) <= 64)

        # Test invalid UID prefixes
        for invalid_prefix in (('1' * 63) + '.',
                               '',
                               '.',
                               '1',
                               '1.2',
                               '1.2..3.',
                               '1.a.2.',
                               '1.01.1.'):
            self.assertRaises(ValueError, generate_uid, invalid_prefix)

        # Test some valid prefixes and make sure they survive
        for valid_prefix in ('0.',
                             '1.',
                             '1.23.',
                             '1.0.23.',
                             ('1' * 62) + '.',
                             '1.2.3.444444.'):
            uid = generate_uid(prefix=valid_prefix)
            self.assertEqual(uid[:len(valid_prefix)], valid_prefix)
            self.assertTrue(len(uid) <= 64)


class TestUID(unittest.TestCase):
    """Test DICOM UIDs"""
    def setUp(self):
        """Set default UID"""
        self.uid = UID('1.2.840.10008.1.2')

    def test_equality(self):
        """Test that UID.__eq__ works with private UIDs."""
        self.assertTrue(self.uid == UID('1.2.840.10008.1.2'))
        self.assertTrue(self.uid == '1.2.840.10008.1.2')
        self.assertTrue(self.uid == 'Implicit VR Little Endian')
        self.assertFalse(self.uid == UID('1.2.840.10008.1.2.1'))
        self.assertFalse(self.uid == '1.2.840.10008.1.2.1')
        self.assertFalse(self.uid == 'Explicit VR Little Endian')
        # Issue 96
        self.assertFalse(self.uid == 3)
        self.assertFalse(self.uid is None)

    def test_inequality(self):
        """Test that UID.__ne__ works with private UIDs."""
        self.assertFalse(self.uid != UID('1.2.840.10008.1.2'))
        self.assertFalse(self.uid != '1.2.840.10008.1.2')
        self.assertFalse(self.uid != 'Implicit VR Little Endian')
        self.assertTrue(self.uid != UID('1.2.840.10008.1.2.1'))
        self.assertTrue(self.uid != '1.2.840.10008.1.2.1')
        self.assertTrue(self.uid != 'Explicit VR Little Endian')
        # Issue 96
        self.assertTrue(self.uid != 3)
        self.assertTrue(self.uid is not None)

    def test_hash(self):
        """Test that UID.__hash_- works."""
        self.assertEqual(hash(self.uid), 3026120838586540702)
        self.assertEqual(hash(self.uid), 3026120838586540702)

    def test_str(self):
        """Test that UID.__str__ works."""
        self.assertEqual(self.uid.__str__(), 'Implicit VR Little Endian')

    def test_is_implicit_vr(self):
        """Test that UID.is_implicit_VR works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertTrue(UID('1.2.840.10008.1.2').is_implicit_VR)
        self.assertFalse(UID('1.2.840.10008.1.2.1').is_implicit_VR)
        self.assertFalse(UID('1.2.840.10008.1.2.1.99').is_implicit_VR)
        self.assertFalse(UID('1.2.840.10008.1.2.2').is_implicit_VR)
        self.assertFalse(UID('1.2.840.10008.1.2.4.50').is_implicit_VR)

        def test(): UID('1.2.840.10008.5.1.4.1.1.2').is_implicit_VR
        self.assertRaises(ValueError, test)

    def test_is_little_endian(self):
        """Test that UID.is_little_endian works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertTrue(UID('1.2.840.10008.1.2').is_little_endian)
        self.assertTrue(UID('1.2.840.10008.1.2.1').is_little_endian)
        self.assertTrue(UID('1.2.840.10008.1.2.1.99').is_little_endian)
        self.assertFalse(UID('1.2.840.10008.1.2.2').is_little_endian)
        self.assertTrue(UID('1.2.840.10008.1.2.4.50').is_little_endian)

        def test(): UID('1.2.840.10008.5.1.4.1.1.2').is_little_endian
        self.assertRaises(ValueError, test)

    def test_is_deflated(self):
        """Test that UID.is_deflated works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertFalse(UID('1.2.840.10008.1.2').is_deflated)
        self.assertFalse(UID('1.2.840.10008.1.2.1').is_deflated)
        self.assertTrue(UID('1.2.840.10008.1.2.1.99').is_deflated)
        self.assertFalse(UID('1.2.840.10008.1.2.2').is_deflated)
        self.assertFalse(UID('1.2.840.10008.1.2.4.50').is_deflated)

        def test(): UID('1.2.840.10008.5.1.4.1.1.2').is_deflated
        self.assertRaises(ValueError, test)

    def test_is_transfer_syntax(self):
        """Test that UID.is_transfer_syntax works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertTrue(UID('1.2.840.10008.1.2').is_transfer_syntax)
        self.assertTrue(UID('1.2.840.10008.1.2.1').is_transfer_syntax)
        self.assertTrue(UID('1.2.840.10008.1.2.1.99').is_transfer_syntax)
        self.assertTrue(UID('1.2.840.10008.1.2.2').is_transfer_syntax)
        self.assertTrue(UID('1.2.840.10008.1.2.4.50').is_transfer_syntax)

        self.assertFalse(UID('1.2.840.10008.5.1.4.1.1.2').is_transfer_syntax)

    def test_is_compressed(self):
        """Test that UID.is_compressed works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertFalse(UID('1.2.840.10008.1.2').is_compressed)
        self.assertFalse(UID('1.2.840.10008.1.2.1').is_compressed)
        self.assertFalse(UID('1.2.840.10008.1.2.1.99').is_compressed)
        self.assertFalse(UID('1.2.840.10008.1.2.2').is_compressed)
        self.assertTrue(UID('1.2.840.10008.1.2.4.50').is_compressed)

        def test(): UID('1.2.840.10008.5.1.4.1.1.2').is_compressed
        self.assertRaises(ValueError, test)

    def test_is_encapsulated(self):
        """Test that UID.is_encapsulated works."""
        # '1.2.840.10008.1.2' Implicit VR Little Endian
        # '1.2.840.10008.1.2.1' Explicit VR Little Endian
        # '1.2.840.10008.1.2.1.99' Deflated Explicit VR Little Endian
        # '1.2.840.10008.1.2.2' Explicit VR Big Endian
        # '1.2.840.10008.1.2.4.50'JPEG Baseline (Process 1)
        self.assertFalse(UID('1.2.840.10008.1.2').is_encapsulated)
        self.assertFalse(UID('1.2.840.10008.1.2.1').is_encapsulated)
        self.assertFalse(UID('1.2.840.10008.1.2.1.99').is_encapsulated)
        self.assertFalse(UID('1.2.840.10008.1.2.2').is_encapsulated)
        self.assertTrue(UID('1.2.840.10008.1.2.4.50').is_encapsulated)

        def test(): UID('1.2.840.10008.5.1.4.1.1.2').is_encapsulated
        self.assertRaises(ValueError, test)

    def test_name(self):
        """Test that UID.name works."""
        self.assertEqual(self.uid.name, 'Implicit VR Little Endian')
        self.assertEqual(UID('1.2.840.10008.5.1.4.1.1.2').name,
                         'CT Image Storage')

    def test_type(self):
        """Test that UID.type works."""
        self.assertEqual(self.uid.type, 'Transfer Syntax')
        self.assertEqual(UID('1.2.840.10008.5.1.4.1.1.2').type, 'SOP Class')

    def test_info(self):
        """Test that UID.info works."""
        self.assertEqual(self.uid.info, 'Default Transfer Syntax for DICOM')
        self.assertEqual(UID('1.2.840.10008.5.1.4.1.1.2').info, '')

    def test_is_retired(self):
        """Test that UID.is_retired works."""
        self.assertFalse(self.uid.is_retired)
        self.assertTrue(UID('1.2.840.10008.1.2.2').is_retired)

    def test_is_valid(self):
        """Test that UID.is_valid works."""
        for invalid_uid in ('1' * 65,
                            '1.' + ('2' * 63),
                            '',
                            '.',
                            '1.',
                            '1.01',
                            '1.a.2'):
            self.assertFalse(UID(invalid_uid).is_valid)

        for valid_uid in ('0',
                          '1',
                          '0.1',
                          '1' * 64,
                          '1.' + ('2' * 62),
                          '1.0.23'):
            self.assertTrue(UID(valid_uid).is_valid)

    def test_is_private(self):
        """Test the is_private property"""
        uid = UID('1.2.840.10008.1.2')
        private_uid = UID('1.2.840.10009.1.2')
        self.assertTrue(private_uid.is_private)
        self.assertFalse(uid.is_private)


class TestUIDPrivate(unittest.TestCase):
    """Test private UIDs"""
    def setUp(self):
        """Set default UID"""
        self.uid = UID('9.9.999.90009.1.2')

    def test_equality(self):
        """Test that UID.__eq__ works with private UIDs."""
        self.assertTrue(self.uid == UID('9.9.999.90009.1.2'))
        self.assertTrue(self.uid == '9.9.999.90009.1.2')
        self.assertFalse(self.uid == UID('9.9.999.90009.1.3'))
        self.assertFalse(self.uid == '9.9.999.90009.1.3')

    def test_inequality(self):
        """Test that UID.__ne__ works with private UIDs."""
        self.assertFalse(self.uid != UID('9.9.999.90009.1.2'))
        self.assertFalse(self.uid != '9.9.999.90009.1.2')
        self.assertTrue(self.uid != UID('9.9.999.90009.1.3'))
        self.assertTrue(self.uid != '9.9.999.90009.1.3')

    def test_hash(self):
        """Test that UID.__hash_- works with private UIDs."""
        self.assertEqual(hash(self.uid), 6878411962048153691)
        self.assertEqual(hash(self.uid), 6878411962048153691)

    def test_str(self):
        """Test that UID.__str__ works with private UIDs."""
        self.assertEqual(self.uid.__str__(), '9.9.999.90009.1.2')

    def test_is_implicit_vr(self):
        """Test that UID.is_implicit_VR works with private UIDs."""
        def test(): self.uid.is_implicit_VR
        self.assertRaises(ValueError, test)

    def test_is_little_endian(self):
        """Test that UID.is_little_endian works with private UIDs."""
        def test(): self.uid.is_little_endian
        self.assertRaises(ValueError, test)

    def test_is_deflated(self):
        """Test that UID.is_deflated works with private UIDs."""
        def test(): self.uid.is_deflated
        self.assertRaises(ValueError, test)

    def test_is_transfer_syntax(self):
        """Test that UID.is_transfer_syntax works with private UIDs."""
        def test(): self.uid.is_transfer_syntax
        self.assertRaises(ValueError, test)

    def test_is_compressed(self):
        """Test that UID.is_compressed works with private UIDs."""
        def test(): self.uid.is_compressed
        self.assertRaises(ValueError, test)

    def test_is_encapsulated(self):
        """Test that UID.is_encapsulated works with private UIDs."""
        def test(): self.uid.is_encapsulated
        self.assertRaises(ValueError, test)

    def test_name(self):
        """Test that UID.name works with private UIDs."""
        self.assertEqual(self.uid.name, '9.9.999.90009.1.2')

    def test_type(self):
        """Test that UID.type works with private UIDs."""
        self.assertEqual(self.uid.type, '')

    def test_info(self):
        """Test that UID.info works with private UIDs."""
        self.assertEqual(self.uid.info, '')

    def test_is_retired(self):
        """Test that UID.is_retired works with private UIDs."""
        self.assertFalse(self.uid.is_retired)

    def test_is_valid(self):
        """Test that UID.is_valid works with private UIDs."""
        self.assertTrue(self.uid.is_valid)

    def test_is_private(self):
        """Test that UID.is_private works with private UIDs."""
        self.assertTrue(self.uid.is_private)


if __name__ == "__main__":
    unittest.main()
