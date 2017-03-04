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
            BaseTag(0x00010002) <= '0x00010002'
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
            BaseTag(0x00010002) < '0x00010002'
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
            BaseTag(0x00010002) >= '0x00010002'
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
            BaseTag(0x00010002) > '0x00010002'
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
            BaseTag(0x00010002) == '0x00010002'
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
            BaseTag(0x00010002) != '0x00010002'
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


class Values(unittest.TestCase):
    def testGoodInts(self):
        """Tags can be constructed with 4-byte integers.............."""
        Tag(0x300a00b0)
        Tag(0xFFFFFFEE)

    def testGoodTuple(self):
        """Tags can be constructed with two-tuple of 2-byte integers."""
        TupleTag((0xFFFF, 0xFFee))
        tag = TupleTag((0x300a, 0x00b0))
        self.assertEqual(tag.group, 0x300a, "Expected tag.group 0x300a, got %r" % tag.group)

    def testAnyUnpack(self):
        """Tags can be constructed from list........................."""
        Tag([2, 0])

    def testBadTuple(self):
        """Tags: if a tuple, must be a 2-tuple......................."""
        self.assertRaises(ValueError, Tag, (1, 2, 3, 4))

    def testNonNumber(self):
        """Tags cannot be instantiated from a non-hex string........."""
        self.assertRaises(ValueError, Tag, "hello")

    def testHexString(self):
        """Tags can be instantiated from hex strings................."""
        tag = Tag('0010', '0002')
        self.assertEqual(tag.group, 16)
        self.assertEqual(tag.elem, 2)

    def testStr(self):
        """Tags have (gggg, eeee) string rep........................."""
        self.assertTrue(str(Tag(0x300a00b0)) == "(300a, 00b0)")

    def testGroup(self):
        """Tags' group and elem portions extracted properly.........."""
        tag = Tag(0x300a00b0)
        self.assertTrue(tag.group == 0x300a)
        self.assertTrue(tag.elem == 0xb0)
        self.assertTrue(tag.element == 0xb0)

    def testZeroElem(self):
        """Tags with arg2=0 ok (was issue 47)........................"""
        tag = Tag(2, 0)
        self.assertTrue(tag.group == 2 and tag.elem == 0)

    def testBadInts(self):
        """Tags constructed with > 8 bytes gives OverflowError......."""
        self.assertRaises(OverflowError, Tag, 0x123456789)


if __name__ == "__main__":
    unittest.main()
