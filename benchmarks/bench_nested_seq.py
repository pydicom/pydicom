from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag


def create_nested_test_seq(num_items: int = 6280) -> Dataset:
    """Create a simplified version of sequence from issue #1728"""
    # original had 6280 items, but that is probably larger than needed
    from copy import deepcopy
    ds = Dataset()

    # Per-frame Functional Groups Sequence
    func_gps_seq = Sequence()
    ds.PerFrameFunctionalGroupsSequence = func_gps_seq

    # Per-frame Functional Groups Sequence: Per-frame Functional Groups 1
    func_gps1 = Dataset()

    # Plane Position Sequence
    plane_pos_seq = Sequence()
    func_gps1.PlanePositionSequence = plane_pos_seq
    func_gps_seq.append(func_gps1)

    # Plane Position Sequence: Plane Position 1
    plane_pos1 = Dataset()
    plane_pos1.XOffsetInSlideCoordinateSystem = '0.0'
    plane_pos1.YOffsetInSlideCoordinateSystem = '0.0'
    plane_pos1.ZOffsetInSlideCoordinateSystem = '0.0'
    plane_pos1.ColumnPositionInTotalImagePixelMatrix = 1
    plane_pos1.RowPositionInTotalImagePixelMatrix = 1
    plane_pos_seq.append(plane_pos1)

    for i in range(num_items - 1):
        func_gp = Dataset()
        plane_pos = deepcopy(plane_pos1)
        # Ensure different numbers to avoid memory caching of some kind
        plane_pos.ColumnPositionInTotalImagePixelMatrix = i
        plane_pos.RowPositionInTotalImagePixelMatrix = i
        func_gp.PlanePositionSequence = Sequence([plane_pos])
        func_gps_seq.append(func_gp)

    return ds


class TimeNestedSeqAccess:
    """Time tests for large nested sequences."""
    len_top_sequence = 2000
    dataset = create_nested_test_seq(len_top_sequence)

    def setup(self):
        pass

    def time_iterate_nested_elems(self):
        for func_gp in self.dataset.PerFrameFunctionalGroupsSequence:
            pps_item = func_gp.PlanePositionSequence[0]
            (
                pps_item.RowPositionInTotalImagePixelMatrix,
                pps_item.ColumnPositionInTotalImagePixelMatrix,
            )

    def time_index_to_nested_items(self):
        for i in range(len(self.dataset.PerFrameFunctionalGroupsSequence)):
            func_gp = self.dataset.PerFrameFunctionalGroupsSequence[i]
            pps_item = func_gp.PlanePositionSequence[0]
            (
                pps_item.RowPositionInTotalImagePixelMatrix,
                pps_item.ColumnPositionInTotalImagePixelMatrix,
            )

    def time_iterate_preload_tags(self):
        row_pos_tag = Tag("RowPositionInTotalImagePixelMatrix")
        col_pos_tag = Tag("ColumnPositionInTotalImagePixelMatrix")
        plane_pos_seq_tag = Tag("PlanePositionSequence")
        for func_gp in self.dataset.PerFrameFunctionalGroupsSequence:
            pps_item = func_gp[plane_pos_seq_tag][0]
            (
                pps_item[row_pos_tag].value,
                pps_item[col_pos_tag].value,
            )

    def track_len_top_sequence(self):
        return self.len_top_sequence
