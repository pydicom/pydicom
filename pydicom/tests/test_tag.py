# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test suite for tag.py"""

import unittest

import pytest

from pydicom.compat import in_py2
from pydicom.tag import BaseTag, Tag, TupleTag, tag_in_exception


class TestBaseTag(object):
    """Test the BaseTag class."""
    def test_le_same_class(self):
        """Test __le__ of two classes with same type."""
        assert BaseTag(0x00000000) <= BaseTag(0x00000001)
        assert BaseTag(0x00000001) <= BaseTag(0x00000001)
        assert not BaseTag(0x00000001) <= BaseTag(0x00000000)

    def test_le_diff_class(self):
        """Test __le__ of two classes with different type."""
        assert BaseTag(0x00000000) <= 1
        assert BaseTag(0x00000001) <= 1
        assert not BaseTag(0x00000001) <= 0

    def test_le_subclass(self):
        """Test __le__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert BaseTagPlus(0x00000000) <= BaseTag(0x00000001)
        assert BaseTagPlus(0x00000001) <= BaseTag(0x00000001)
        assert not BaseTagPlus(0x00000001) <= BaseTag(0x00000000)

    def test_le_tuple(self):
        """Test __le__ of tuple with BaseTag."""
        assert BaseTag(0x00010001) <= (0x0001, 0x0002)
        assert BaseTag(0x00010002) <= (0x0001, 0x0002)
        assert not BaseTag(0x00010002) <= (0x0001, 0x0001)

    def test_le_raises(self):
        """Test __le__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) <= 'Somethin'
        pytest.raises(TypeError, test_raise)

    def test_lt_same_class(self):
        """Test __lt__ of two classes with same type."""
        assert BaseTag(0x00000000) < BaseTag(0x00000001)
        assert not BaseTag(0x00000001) < BaseTag(0x00000001)
        assert not BaseTag(0x00000001) < BaseTag(0x00000000)

    def test_lt_diff_class(self):
        """Test __lt__ of two classes with different type."""
        assert BaseTag(0x00000000) < 1
        assert not BaseTag(0x00000001) < 1
        assert not BaseTag(0x00000001) < 0

    def test_lt_subclass(self):
        """Test __lt__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert BaseTagPlus(0x00000000) < BaseTag(0x00000001)
        assert not BaseTagPlus(0x00000001) < BaseTag(0x00000001)
        assert not BaseTagPlus(0x00000001) < BaseTag(0x00000000)

    def test_lt_tuple(self):
        """Test __lt__ of tuple with BaseTag."""
        assert BaseTag(0x00010001) < (0x0001, 0x0002)
        assert not BaseTag(0x00010002) < (0x0001, 0x0002)
        assert not BaseTag(0x00010002) < (0x0001, 0x0001)

    def test_lt_raises(self):
        """Test __lt__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) < 'Somethin'
        pytest.raises(TypeError, test_raise)

    def test_ge_same_class(self):
        """Test __ge__ of two classes with same type."""
        assert not BaseTag(0x00000000) >= BaseTag(0x00000001)
        assert BaseTag(0x00000001) >= BaseTag(0x00000001)
        assert BaseTag(0x00000001) >= BaseTag(0x00000000)

    def test_ge_diff_class(self):
        """Test __ge__ of two classes with different type."""
        assert not BaseTag(0x00000000) >= 1
        assert BaseTag(0x00000001) >= 1
        assert BaseTag(0x00000001) >= 0

    def test_ge_subclass(self):
        """Test __ge__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert not BaseTagPlus(0x00000000) >= BaseTag(0x00000001)
        assert BaseTagPlus(0x00000001) >= BaseTag(0x00000001)
        assert BaseTagPlus(0x00000001) >= BaseTag(0x00000000)

    def test_ge_tuple(self):
        """Test __ge__ of tuple with BaseTag."""
        assert not BaseTag(0x00010001) >= (0x0001, 0x0002)
        assert BaseTag(0x00010002) >= (0x0001, 0x0002)
        assert BaseTag(0x00010002) >= (0x0001, 0x0001)

    def test_ge_raises(self):
        """Test __ge__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) >= 'AGHIJJJJ'
        pytest.raises(TypeError, test_raise)

    def test_gt_same_class(self):
        """Test __gt__ of two classes with same type."""
        assert not BaseTag(0x00000000) > BaseTag(0x00000001)
        assert not BaseTag(0x00000001) > BaseTag(0x00000001)
        assert BaseTag(0x00000001) > BaseTag(0x00000000)

    def test_gt_diff_class(self):
        """Test __gt__ of two classes with different type."""
        assert not BaseTag(0x00000000) > 1
        assert not BaseTag(0x00000001) > 1
        assert BaseTag(0x00000001) > 0

    def test_gt_subclass(self):
        """Test __gt__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert not BaseTagPlus(0x00000000) > BaseTag(0x00000001)
        assert not BaseTagPlus(0x00000001) > BaseTag(0x00000001)
        assert BaseTagPlus(0x00000001) > BaseTag(0x00000000)

    def test_gt_tuple(self):
        """Test __gt__ of tuple with BaseTag."""
        assert not BaseTag(0x00010001) > (0x0001, 0x0002)
        assert not BaseTag(0x00010002) > (0x0001, 0x0002)
        assert BaseTag(0x00010002) > (0x0001, 0x0001)

    def test_gt_raises(self):
        """Test __gt__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) > 'BLUH'
        pytest.raises(TypeError, test_raise)

    def test_eq_same_class(self):
        """Test __eq__ of two classes with same type."""
        assert BaseTag(0x00000000) == BaseTag(0x00000000)
        assert not BaseTag(0x00000001) == BaseTag(0x00000000)

    def test_eq_diff_class(self):
        """Test __eq__ of two classes with different type."""
        assert BaseTag(0x00000000) == 0
        assert not BaseTag(0x00000001) == 0

    def test_eq_subclass(self):
        """Test __eq__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert BaseTagPlus(0x00000000) == BaseTag(0x00000000)
        assert not BaseTagPlus(0x00000001) == BaseTag(0x00000000)

    def test_eq_tuple(self):
        """Test __eq__ of tuple with BaseTag."""
        assert BaseTag(0x00010002) == (0x0001, 0x0002)
        assert not BaseTag(0x00010001) == (0x0001, 0x0002)

    def test_eq_raises(self):
        """Test __eq__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) == 'eraa'
        pytest.raises(TypeError, test_raise)

    def test_ne_same_class(self):
        """Test __ne__ of two classes with same type."""
        assert not BaseTag(0x00000000) != BaseTag(0x00000000)
        assert BaseTag(0x00000001) != BaseTag(0x00000000)

    def test_ne_diff_class(self):
        """Test __ne__ of two classes with different type."""
        assert not BaseTag(0x00000000) != 0
        assert BaseTag(0x00000001) != 0

    def test_ne_subclass(self):
        """Test __ne__ of two classes with one as a subclass."""
        class BaseTagPlus(BaseTag):
            pass
        assert not BaseTagPlus(0x00000000) != BaseTag(0x00000000)
        assert BaseTagPlus(0x00000001) != BaseTag(0x00000000)

    def test_ne_tuple(self):
        """Test __ne__ of tuple with BaseTag."""
        assert not BaseTag(0x00010002) != (0x0001, 0x0002)
        assert BaseTag(0x00010001) != (0x0001, 0x0002)

    def test_ne_raises(self):
        """Test __ne__ raises TypeError when comparing to non numeric."""
        def test_raise():
            BaseTag(0x00010002) != 'aaag'
        pytest.raises(TypeError, test_raise)

    def test_hash(self):
        """Test hash of BaseTag class."""
        assert hash(BaseTag(0x00010001)) == hash(BaseTag(0x00010001))
        assert hash(BaseTag(0x00010001)) != hash(BaseTag(0x00010002))
        assert hash(BaseTag(0x00020001)) != hash(BaseTag(0x00010002))

    def test_str(self):
        """Test str(BaseTag) produces correct value."""
        assert str(BaseTag(0x00000000)) == '(0000, 0000)'
        assert str(BaseTag(0x00010002)) == '(0001, 0002)'
        assert str(BaseTag(0x10002000)) == '(1000, 2000)'
        assert str(BaseTag(0xFFFFFFFE)) == '(ffff, fffe)'

    def test_group(self):
        """Test BaseTag.group returns correct values."""
        assert BaseTag(0x00000001).group == 0x0000
        assert BaseTag(0x00020001).group == 0x0002
        assert BaseTag(0xFFFF0001).group == 0xFFFF

    def test_element(self):
        """Test BaseTag.element returns correct values."""
        assert BaseTag(0x00010000).element == 0x0000
        assert BaseTag(0x00010002).element == 0x0002
        assert BaseTag(0x0001FFFF).element == 0xFFFF

    def test_private(self):
        """Test BaseTag.is_private returns correct values."""
        # Odd groups private
        assert BaseTag(0x00010001).is_private
        # Even groups not private
        assert not BaseTag(0x00020001).is_private
        # Group 0 not private
        assert not BaseTag(0x00000001).is_private

    def test_private_creator(self):
        """Test BaseTag.is_private_creator returns correct values."""
        # Non-private tag
        assert not BaseTag(0x00080010).is_private_creator
        # private creator have element 0x0010 - 0x00FF
        assert not BaseTag(0x0009000F).is_private_creator
        assert BaseTag(0x00090010).is_private_creator
        assert BaseTag(0x000900FF).is_private_creator
        assert not BaseTag(0x00090100).is_private_creator

    def test_base_class(self):
        """Test the class BaseTag inherits from."""
        if in_py2:
            # Test for overflow of int
            tag = Tag(0xFFFFFFFF)
            assert isinstance(tag, long)
        else:
            tag = Tag(0xFFFFFFFF)
            assert isinstance(tag, int)


class TestTag(object):
    """Test the Tag method."""
    def test_tag_single_int(self):
        """Test creating a Tag from a single int."""
        assert Tag(0x0000) == BaseTag(0x00000000)
        assert Tag(10) == BaseTag(0x0000000A)
        assert Tag(0xFFFF) == BaseTag(0x0000FFFF)
        assert Tag(0x00010002) == BaseTag(0x00010002)

        # Must be 32-bit
        pytest.raises(OverflowError, Tag, 0xFFFFFFFF1)
        # Must be positive
        pytest.raises(ValueError, Tag, -1)

    def test_tag_single_tuple(self):
        """Test creating a Tag from a single tuple."""
        assert Tag((0x0000, 0x0000)) == BaseTag(0x00000000)
        assert Tag((0x22, 0xFF)) == BaseTag(0x002200FF)
        assert Tag((14, 0xF)) == BaseTag(0x000E000F)
        assert Tag((0x1000, 0x2000)) == BaseTag(0x10002000)
        assert Tag(('0x01', '0x02')) == BaseTag(0x00010002)

        # Must be 2 tuple
        pytest.raises(ValueError, Tag, (0x1000, 0x2000, 0x0030))
        pytest.raises(ValueError, Tag, ('0x10', '0x20', '0x03'))
        # Must be 32-bit
        pytest.raises(OverflowError, Tag, (0xFFFF, 0xFFFF1))
        pytest.raises(OverflowError, Tag, ('0xFFFF', '0xFFFF1'))
        # Must be positive
        pytest.raises(ValueError, Tag, (-1, 0))
        pytest.raises(ValueError, Tag, (0, -1))
        pytest.raises(ValueError, Tag, ('0x0', '-0x1'))
        pytest.raises(ValueError, Tag, ('-0x1', '0x0'))
        # Can't have second parameter
        pytest.raises(ValueError, Tag, (0x01, 0x02), 0x01)
        pytest.raises(ValueError, Tag, (0x01, 0x02), '0x01')
        pytest.raises(ValueError, Tag, ('0x01', '0x02'), '0x01')
        pytest.raises(ValueError, Tag, ('0x01', '0x02'), 0x01)

    def test_tag_single_list(self):
        """Test creating a Tag from a single list."""
        assert Tag([0x0000, 0x0000]) == BaseTag(0x00000000)
        assert Tag([0x99, 0xFE]) == BaseTag(0x009900FE)
        assert Tag([15, 0xE]) == BaseTag(0x000F000E)
        assert Tag([0x1000, 0x2000]) == BaseTag(0x10002000)
        assert Tag(['0x01', '0x02']) == BaseTag(0x00010002)

        # Must be 2 list
        pytest.raises(ValueError, Tag, [0x1000, 0x2000, 0x0030])
        pytest.raises(ValueError, Tag, ['0x10', '0x20', '0x03'])
        pytest.raises(ValueError, Tag, [0x1000])
        pytest.raises(ValueError, Tag, ['0x10'])

        # Must be int or string
        pytest.raises(ValueError, Tag, [1., 2.])

        # Must be 32-bit
        pytest.raises(OverflowError, Tag, [65536, 0])
        pytest.raises(OverflowError, Tag, [0, 65536])
        pytest.raises(OverflowError, Tag, ('0xFFFF', '0xFFFF1'))
        # Must be positive
        pytest.raises(ValueError, Tag, [-1, 0])
        pytest.raises(ValueError, Tag, [0, -1])
        pytest.raises(ValueError, Tag, ('0x0', '-0x1'))
        pytest.raises(ValueError, Tag, ('-0x1', '0x0'))
        # Can't have second parameter
        pytest.raises(ValueError, Tag, [0x01, 0x02], 0x01)
        pytest.raises(ValueError, Tag, [0x01, 0x02], '0x01')
        pytest.raises(ValueError, Tag, ['0x01', '0x02'], '0x01')
        pytest.raises(ValueError, Tag, ['0x01', '0x02'], 0x01)

    @unittest.skipIf(not in_py2, 'Long type only exists in Python 2')
    def test_mixed_long_int(self):
        assert Tag([0x1000, long(0x2000)]) == BaseTag(0x10002000)
        assert Tag([long(0x1000), 0x2000]) == BaseTag(0x10002000)
        assert Tag([long(0x1000), long(0x2000)]) == BaseTag(0x10002000)

    def test_tag_single_str(self):
        """Test creating a Tag from a single str."""
        assert Tag('0x10002000') == BaseTag(0x10002000)
        assert Tag('0x2000') == BaseTag(0x00002000)
        assert Tag('15') == BaseTag(0x00000015)
        assert Tag('0xF') == BaseTag(0x0000000F)

        # Must be 32-bit
        pytest.raises(OverflowError, Tag, '0xFFFFFFFF1')
        # Must be positive
        pytest.raises(ValueError, Tag, '-0x01')
        # Must be numeric str
        pytest.raises(ValueError, Tag, 'hello')

    def test_tag_double_str(self):
        """Test creating a Tag from two str."""
        assert Tag('0x1000', '0x2000') == BaseTag(0x10002000)
        assert Tag('0x10', '0x20') == BaseTag(0x00100020)
        assert Tag('15', '0') == BaseTag(0x00150000)
        assert Tag('0xF', '0') == BaseTag(0x000F0000)

        # Must be 32-bit
        pytest.raises(OverflowError, Tag, '0xFFFF1', '0')
        pytest.raises(OverflowError, Tag, '0', '0xFFFF1')
        # Must be positive
        pytest.raises(ValueError, Tag, '-0x01', '0')
        pytest.raises(ValueError, Tag, '0', '-0x01')
        pytest.raises(ValueError, Tag, '-1', '-0x01')
        # Must both be str
        pytest.raises(ValueError, Tag, '0x01', 0)
        pytest.raises(ValueError, Tag, 0, '0x01')

    def test_tag_double_int(self):
        """Test creating a Tag from a two ints."""
        assert Tag(0x0000, 0x0000) == BaseTag(0x00000000)
        assert Tag(2, 0) == BaseTag(0x00020000)
        assert Tag(2, 0).elem == 0x0000
        assert Tag(0x99, 0xFE) == BaseTag(0x009900FE)
        assert Tag(15, 14) == BaseTag(0x000F000E)
        assert Tag(0x1000, 0x2000) == BaseTag(0x10002000)

        # Must be 32-bit
        pytest.raises(OverflowError, Tag, 65536, 0)
        pytest.raises(OverflowError, Tag, 0, 65536)
        # Must be positive
        pytest.raises(ValueError, Tag, -1, 0)
        pytest.raises(ValueError, Tag, 0, -1)
        pytest.raises(ValueError, Tag, -65535, -1)


class TestTupleTag(object):
    """Test the TupleTag method."""
    def test_tuple_tag(self):
        """Test quick tag construction with TupleTag."""
        assert TupleTag((0xFFFF, 0xFFee)) == BaseTag(0xFFFFFFEE)


class TestTagInException(object):
    """Test the tag_in_exception method."""
    def test_raise_exception(self):
        """"""
        def test():
            tag = Tag(0x00100010)
            with tag_in_exception(tag) as tag:
                raise ValueError('Test message.')
        pytest.raises(ValueError, test)


if __name__ == "__main__":
    unittest.main()
