"""Test suite for Tag.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.tag import BaseTag, Tag, TupleTag


class TestBaseTag(unittest.TestCase):
    """Test the BaseTag class."""
    def test_le_same_class(self):
        """Test __le__ of two classes with same type."""
        self.assertTrue(BaseTag(0x00000000) <= BaseTag(0x00000001))
        self.assertTrue(BaseTag(0x00000001) <= BaseTag(0x00000001))
        self.assertFalse(BaseTag(0x00000001) <= BaseTag(0x00000000))

    def test_le_diff_class(self):
        """Test __le__ of two classes with different type."""
        self.assertTrue(BaseTag(0x00000000) <= 1)
        self.assertTrue(BaseTag(0x00000001) <= 1)
        self.assertFalse(BaseTag(0x00000001) <= 0)

    def test_le_subclass(self):
        """Test __le__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertTrue(BaseTagPlus(0x00000000) <= BaseTag(0x00000001))
        self.assertTrue(BaseTagPlus(0x00000001) <= BaseTag(0x00000001))
        self.assertFalse(BaseTagPlus(0x00000001) <= BaseTag(0x00000000))

    def test_le_tuple(self):
        """Test __le__ of tuple with BaseTag."""
        self.assertTrue(BaseTag(0x00010001) <= (0x0001, 0x0002))
        self.assertTrue(BaseTag(0x00010002) <= (0x0001, 0x0002))
        self.assertFalse(BaseTag(0x00010002) <= (0x0001, 0x0001))

    def test_le_raises(self):
        """Test __le__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) <= 'Something'
        self.assertRaises(TypeError, test_raise)

    def test_lt_same_class(self):
        """Test __lt__ of two classes with same type."""
        self.assertTrue(BaseTag(0x00000000) < BaseTag(0x00000001))
        self.assertFalse(BaseTag(0x00000001) < BaseTag(0x00000001))
        self.assertFalse(BaseTag(0x00000001) < BaseTag(0x00000000))

    def test_lt_diff_class(self):
        """Test __lt__ of two classes with different type."""
        self.assertTrue(BaseTag(0x00000000) < 1)
        self.assertFalse(BaseTag(0x00000001) < 1)
        self.assertFalse(BaseTag(0x00000001) < 0)

    def test_lt_subclass(self):
        """Test __lt__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertTrue(BaseTagPlus(0x00000000) < BaseTag(0x00000001))
        self.assertFalse(BaseTagPlus(0x00000001) < BaseTag(0x00000001))
        self.assertFalse(BaseTagPlus(0x00000001) < BaseTag(0x00000000))

    def test_lt_tuple(self):
        """Test __lt__ of tuple with BaseTag."""
        self.assertTrue(BaseTag(0x00010001) < (0x0001, 0x0002))
        self.assertFalse(BaseTag(0x00010002) < (0x0001, 0x0002))
        self.assertFalse(BaseTag(0x00010002) < (0x0001, 0x0001))

    def test_lt_raises(self):
        """Test __lt__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) < 'Somethin'
        self.assertRaises(TypeError, test_raise)

    def test_ge_same_class(self):
        """Test __ge__ of two classes with same type."""
        self.assertFalse(BaseTag(0x00000000) >= BaseTag(0x00000001))
        self.assertTrue(BaseTag(0x00000001) >= BaseTag(0x00000001))
        self.assertTrue(BaseTag(0x00000001) >= BaseTag(0x00000000))

    def test_ge_diff_class(self):
        """Test __ge__ of two classes with different type."""
        self.assertFalse(BaseTag(0x00000000) >= 1)
        self.assertTrue(BaseTag(0x00000001) >= 1)
        self.assertTrue(BaseTag(0x00000001) >= 0)

    def test_ge_subclass(self):
        """Test __ge__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertFalse(BaseTagPlus(0x00000000) >= BaseTag(0x00000001))
        self.assertTrue(BaseTagPlus(0x00000001) >= BaseTag(0x00000001))
        self.assertTrue(BaseTagPlus(0x00000001) >= BaseTag(0x00000000))

    def test_ge_tuple(self):
        """Test __ge__ of tuple with BaseTag."""
        self.assertFalse(BaseTag(0x00010001) >= (0x0001, 0x0002))
        self.assertTrue(BaseTag(0x00010002) >= (0x0001, 0x0002))
        self.assertTrue(BaseTag(0x00010002) >= (0x0001, 0x0001))

    def test_ge_raises(self):
        """Test __ge__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) >= 'AGHIJJJJ'
        self.assertRaises(TypeError, test_raise)

    def test_gt_same_class(self):
        """Test __gt__ of two classes with same type."""
        self.assertFalse(BaseTag(0x00000000) > BaseTag(0x00000001))
        self.assertFalse(BaseTag(0x00000001) > BaseTag(0x00000001))
        self.assertTrue(BaseTag(0x00000001) > BaseTag(0x00000000))

    def test_gt_diff_class(self):
        """Test __gt__ of two classes with different type."""
        self.assertFalse(BaseTag(0x00000000) > 1)
        self.assertFalse(BaseTag(0x00000001) > 1)
        self.assertTrue(BaseTag(0x00000001) > 0)

    def test_gt_subclass(self):
        """Test __gt__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertFalse(BaseTagPlus(0x00000000) > BaseTag(0x00000001))
        self.assertFalse(BaseTagPlus(0x00000001) > BaseTag(0x00000001))
        self.assertTrue(BaseTagPlus(0x00000001) > BaseTag(0x00000000))

    def test_gt_tuple(self):
        """Test __gt__ of tuple with BaseTag."""
        self.assertFalse(BaseTag(0x00010001) > (0x0001, 0x0002))
        self.assertFalse(BaseTag(0x00010002) > (0x0001, 0x0002))
        self.assertTrue(BaseTag(0x00010002) > (0x0001, 0x0001))

    def test_gt_raises(self):
        """Test __gt__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) > 'BLUH'
        self.assertRaises(TypeError, test_raise)

    def test_eq_same_class(self):
        """Test __eq__ of two classes with same type."""
        self.assertTrue(BaseTag(0x00000000) == BaseTag(0x00000000))
        self.assertFalse(BaseTag(0x00000001) == BaseTag(0x00000000))

    def test_eq_diff_class(self):
        """Test __eq__ of two classes with different type."""
        self.assertTrue(BaseTag(0x00000000) == 0)
        self.assertFalse(BaseTag(0x00000001) == 0)

    def test_eq_subclass(self):
        """Test __eq__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertTrue(BaseTagPlus(0x00000000) == BaseTag(0x00000000))
        self.assertFalse(BaseTagPlus(0x00000001) == BaseTag(0x00000000))

    def test_eq_tuple(self):
        """Test __eq__ of tuple with BaseTag."""
        self.assertTrue(BaseTag(0x00010002) == (0x0001, 0x0002))
        self.assertFalse(BaseTag(0x00010001) == (0x0001, 0x0002))

    def test_eq_raises(self):
        """Test __eq__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) == 'eraa'
        self.assertRaises(TypeError, test_raise)

    def test_ne_same_class(self):
        """Test __ne__ of two classes with same type."""
        self.assertFalse(BaseTag(0x00000000) != BaseTag(0x00000000))
        self.assertTrue(BaseTag(0x00000001) != BaseTag(0x00000000))

    def test_ne_diff_class(self):
        """Test __ne__ of two classes with different type."""
        self.assertFalse(BaseTag(0x00000000) != 0)
        self.assertTrue(BaseTag(0x00000001) != 0)

    def test_ne_subclass(self):
        """Test __ne__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag): pass
        self.assertFalse(BaseTagPlus(0x00000000) != BaseTag(0x00000000))
        self.assertTrue(BaseTagPlus(0x00000001) != BaseTag(0x00000000))

    def test_ne_tuple(self):
        """Test __ne__ of tuple with BaseTag."""
        self.assertFalse(BaseTag(0x00010002) != (0x0001, 0x0002))
        self.assertTrue(BaseTag(0x00010001) != (0x0001, 0x0002))

    def test_ne_raises(self):
        """Test __ne__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) != 'aaag'
        self.assertRaises(TypeError, test_raise)

    def test_hash(self):
        """Test hash of BaseTag class."""
        self.assertEqual(hash(BaseTag(0x00010001)), hash(BaseTag(0x00010001)))
        self.assertNotEqual(hash(BaseTag(0x00010001)), hash(BaseTag(0x00010002)))
        self.assertNotEqual(hash(BaseTag(0x00020001)), hash(BaseTag(0x00010002)))

    def test_str(self):
        """Test str(BaseTag) produces correct value."""
        self.assertEqual(str(BaseTag(0x00000000)), '(0000, 0000)')
        self.assertEqual(str(BaseTag(0x00010002)), '(0001, 0002)')
        self.assertEqual(str(BaseTag(0x10002000)), '(1000, 2000)')
        self.assertEqual(str(BaseTag(0xFFFFFFFE)), '(ffff, fffe)')

    def test_group(self):
        """Test BaseTag.group returns correct values."""
        self.assertEqual(BaseTag(0x00000001).group, 0x0000)
        self.assertEqual(BaseTag(0x00020001).group, 0x0002)
        self.assertEqual(BaseTag(0xFFFF0001).group, 0xFFFF)

    def test_element(self):
        """Test BaseTag.element returns correct values."""
        self.assertEqual(BaseTag(0x00010000).element, 0x0000)
        self.assertEqual(BaseTag(0x00010002).element, 0x0002)
        self.assertEqual(BaseTag(0x0001FFFF).element, 0xFFFF)

    def test_private(self):
        """Test BaseTag.is_private returns correct values."""
        self.assertTrue(BaseTag(0x00010001).is_private) # Odd groups private
        self.assertFalse(BaseTag(0x00020001).is_private) # Even groups not private
        self.assertFalse(BaseTag(0x00000001).is_private) # Group 0 not private


class TestTag(unittest.TestCase):
    """Test the Tag method."""
    def test_tag_single_int(self):
        """Test creating a Tag from a single int."""
        self.assertEqual(Tag(0x0000), BaseTag(0x00000000))
        self.assertEqual(Tag(10), BaseTag(0x0000000A))
        self.assertEqual(Tag(0xFFFF), BaseTag(0x0000FFFF))
        self.assertEqual(Tag(0x00010002), BaseTag(0x00010002))

        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, 0xFFFFFFFF1)
        # Must be positive
        self.assertRaises(ValueError, Tag, -1)

    def test_tag_single_tuple(self):
        """Test creating a Tag from a single tuple."""
        self.assertEqual(Tag((0x0000, 0x0000)), BaseTag(0x00000000))
        self.assertEqual(Tag((0x22, 0xFF)), BaseTag(0x002200FF))
        self.assertEqual(Tag((14, 0xF)), BaseTag(0x000E000F))
        self.assertEqual(Tag((0x1000, 0x2000)), BaseTag(0x10002000))
        self.assertEqual(Tag(('0x01', '0x02')), BaseTag(0x00010002))

        # Must be 2 tuple
        self.assertRaises(ValueError, Tag, (0x1000, 0x2000, 0x0030))
        self.assertRaises(ValueError, Tag, ('0x10', '0x20', '0x03'))
        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, (0xFFFF, 0xFFFF1))
        self.assertRaises(OverflowError, Tag, ('0xFFFF', '0xFFFF1'))
        # Must be positive
        self.assertRaises(ValueError, Tag, (-1, 0))
        self.assertRaises(ValueError, Tag, (0, -1))
        self.assertRaises(ValueError, Tag, ('0x0', '-0x1'))
        self.assertRaises(ValueError, Tag, ('-0x1', '0x0'))
        # Can't have second parameter
        self.assertRaises(ValueError, Tag, (0x01, 0x02), 0x01)
        self.assertRaises(ValueError, Tag, (0x01, 0x02), '0x01')
        self.assertRaises(ValueError, Tag, ('0x01', '0x02'), '0x01')
        self.assertRaises(ValueError, Tag, ('0x01', '0x02'), 0x01)

    def test_tag_single_list(self):
        """Test creating a Tag from a single list."""
        self.assertEqual(Tag([0x0000, 0x0000]), BaseTag(0x00000000))
        self.assertEqual(Tag([0x99, 0xFE]), BaseTag(0x009900FE))
        self.assertEqual(Tag([15, 0xE]), BaseTag(0x000F000E))
        self.assertEqual(Tag([0x1000, 0x2000]), BaseTag(0x10002000))
        self.assertEqual(Tag(['0x01', '0x02']), BaseTag(0x00010002))

        # Must be 2 list
        self.assertRaises(ValueError, Tag, [0x1000, 0x2000, 0x0030])
        self.assertRaises(ValueError, Tag, ['0x10', '0x20', '0x03'])
        self.assertRaises(ValueError, Tag, [0x1000])
        self.assertRaises(ValueError, Tag, ['0x10'])
        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, [65536, 0])
        self.assertRaises(OverflowError, Tag, [0, 65536])
        self.assertRaises(OverflowError, Tag, ('0xFFFF', '0xFFFF1'))
        # Must be positive
        self.assertRaises(ValueError, Tag, [-1, 0])
        self.assertRaises(ValueError, Tag, [0, -1])
        self.assertRaises(ValueError, Tag, ('0x0', '-0x1'))
        self.assertRaises(ValueError, Tag, ('-0x1', '0x0'))
        # Can't have second parameter
        self.assertRaises(ValueError, Tag, [0x01, 0x02], 0x01)
        self.assertRaises(ValueError, Tag, [0x01, 0x02], '0x01')
        self.assertRaises(ValueError, Tag, ['0x01', '0x02'], '0x01')
        self.assertRaises(ValueError, Tag, ['0x01', '0x02'], 0x01)

    def test_tag_single_str(self):
        """Test creating a Tag from a single str raises."""
        self.assertEqual(Tag('0x10002000'), BaseTag(0x10002000))
        self.assertEqual(Tag('0x2000'), BaseTag(0x00002000))
        self.assertEqual(Tag('15'), BaseTag(0x00000015))
        self.assertEqual(Tag('0xF'), BaseTag(0x0000000F))

        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, '0xFFFFFFFF1')
        # Must be positive
        self.assertRaises(ValueError, Tag, '-0x01')
        # Must be numeric str
        self.assertRaises(ValueError, Tag, 'hello')

    def test_tag_double_str(self):
        """Test creating a Tag from two str."""
        self.assertEqual(Tag('0x1000', '0x2000'), BaseTag(0x10002000))
        self.assertEqual(Tag('0x10', '0x20'), BaseTag(0x00100020))
        self.assertEqual(Tag('15', '0'), BaseTag(0x00150000))
        self.assertEqual(Tag('0xF', '0'), BaseTag(0x000F0000))

        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, '0xFFFF1', '0')
        self.assertRaises(OverflowError, Tag, '0', '0xFFFF1')
        # Must be positive
        self.assertRaises(ValueError, Tag, '-0x01', '0')
        self.assertRaises(ValueError, Tag, '0', '-0x01')
        self.assertRaises(ValueError, Tag, '-1', '-0x01')
        # Must both be str
        self.assertRaises(ValueError, Tag, '0x01', 0)
        self.assertRaises(ValueError, Tag, 0, '0x01')

    def test_tag_double_int(self):
        """Test creating a Tag from a two ints."""
        self.assertEqual(Tag(0x0000, 0x0000), BaseTag(0x00000000))
        self.assertEqual(Tag(2, 0), BaseTag(0x00020000)) # Issue #47
        self.assertTrue(Tag(2, 0).elem == 0x0000)
        self.assertEqual(Tag(0x99, 0xFE), BaseTag(0x009900FE))
        self.assertEqual(Tag(15, 14), BaseTag(0x000F000E))
        self.assertEqual(Tag(0x1000, 0x2000), BaseTag(0x10002000))

        # Must be 32-bit
        self.assertRaises(OverflowError, Tag, 65536, 0)
        self.assertRaises(OverflowError, Tag, 0, 65536)
        # Must be positive
        self.assertRaises(ValueError, Tag, -1, 0)
        self.assertRaises(ValueError, Tag, 0, -1)
        self.assertRaises(ValueError, Tag, -65535, -1)


class TestTupleTag(unittest.TestCase):
    """Test the TupleTag method."""
    def test_tuple_tag(self):
        """Test quick tag construction with TupleTag."""
        self.assertTrue(TupleTag((0xFFFF, 0xFFee)), BaseTag(0xFFFFFFEE))


if __name__ == "__main__":
    unittest.main()
