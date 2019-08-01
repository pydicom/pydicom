# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Benchmarks for the encaps module."""

from pydicom.tag import Tag


class TimeTag(object):
    """Time tests for tag.Tag."""
    def setup(self):
        """Setup the test"""
        self.no_runs = 100000

        self.int = 0x00100010
        self.str = '0x00100010'
        self.keyword = 'PatientName'
        self.list_int = [0x0010, 0x0010]
        self.list_str = ['0x0010', '0x0010']
        self.tuple_int = (0x0010, 0x0010)
        self.tuple_str = ('0x0010', '0x0010')
        self.tag = Tag(0x00100010)

    def time_single_tag(self):
        """Time creation of Tag from a Tag."""
        for ii in range(self.no_runs):
            Tag(self.tag)

    def time_single_int(self):
        """Time creation of Tag from an int."""
        for ii in range(self.no_runs):
            Tag(self.int)

    def time_single_str(self):
        """Time creation of Tag from a str."""
        for ii in range(self.no_runs):
            Tag(self.str)

    def time_keyword(self):
        """Time creation of Tag from a keyword."""
        for ii in range(self.no_runs):
            Tag(self.keyword)

    def time_list_int(self):
        """Time creation of Tag from a list of int."""
        for ii in range(self.no_runs):
            Tag(self.list_int)

    def time_list_str(self):
        """Time creation of Tag from a list of strt."""
        for ii in range(self.no_runs):
            Tag(self.list_str)

    def time_tuple_int(self):
        """Time creation of Tag from a tuple of int."""
        for ii in range(self.no_runs):
            Tag(self.tuple_int)

    def time_tuple_str(self):
        """Time creation of Tag from a tuple of str."""
        for ii in range(self.no_runs):
            Tag(self.tuple_str)
