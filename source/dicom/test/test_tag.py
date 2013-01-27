"""Test suite for Tag.py"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import unittest
from dicom.tag import Tag, TupleTag


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


class Comparisons(unittest.TestCase):
    def setUp(self):
        self.int1 = 0x300a00b0
        self.tup1 = (0x300a, 0xb0)
        self.tup3 = (0xFFFE, 0xFFFC)
        self.t1 = Tag(self.int1)
        self.t2 = Tag(self.tup1)
        self.t3 = Tag(self.tup3)

    def testCmpEq(self):
        """Tags compare correctly (==)..............................."""
        self.assertTrue(self.t1 == self.int1, "tag t1 was not equal to int1")
        self.assertTrue(self.t1 == self.t2, "tag t1 did not equal other tag")
        self.assertTrue(self.t1 == self.tup1, "tag t1 did not equal its tuple")

    def testCmpNotEq(self):
        self.assertTrue(self.t1 != self.t3, "Not equal comparison failed")

    def testCmpLT(self):
        """Tags compare correctly (<, >)............................."""
        self.assertTrue(self.t1 < self.int1 + 1, "tag < failed")
        self.assertTrue(self.int1 + 1 > self.t1, "int > tag failed")
        self.assertTrue(self.t3 > self.t1, "'negative' int tag > other tag failed")

    def testHash(self):
        """Tags hash the same as an int.............................."""
        self.assertTrue(hash(self.t1) == hash(self.int1))
        self.assertTrue(hash(self.t2) == hash(self.int1))


if __name__ == "__main__":
    unittest.main()
