# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
# -*- coding: utf-8 -*-
"""Unit tests for the pydicom.framereader module."""
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest

from pydicom import config
from pydicom.data import get_testdata_files, get_testdata_file
from pydicom import framereader, dcmread
from pydicom.encaps import generate_pixel_data_frame
from pydicom.filereader import data_element_offset_to_value
from pydicom.pixel_data_handlers import gdcm_handler
from pydicom.tag import ItemDelimiterTag

have_numpy = config.have_numpy
if have_numpy:
    import numpy  # NOQA

have_gdcm_handler = gdcm_handler.is_available()
try:
    from PIL import Image as PILImg
except ImportError:
    # If that failed, try the alternate import syntax for PIL.
    try:
        import Image as PILImg
    except ImportError:
        # Neither worked, so it's likely not installed.
        PILImg = None
have_pillow = PILImg is not None

can_decode = all([have_gdcm_handler, have_pillow, have_numpy])

encaps_paths = [
    get_testdata_file(name)
    for name in [
        "SC_rgb_jpeg.dcm",
        "SC_rgb_dcmtk_+eb+cy+s2.dcm",
        "JPGExtended.dcm",
        "SC_rgb_dcmtk_+eb+cr.dcm",
        "MR_small_RLE.dcm",
        "rtdose_rle_1frame.dcm",
        "SC_rgb_dcmtk_+eb+cy+s4.dcm",
        "SC_rgb_rle.dcm",
        "MR_small_jp2klossless.dcm",
        "693_J2KI.dcm",
        "SC_rgb_jpeg_app14_dcmd.dcm",
        "SC_rgb_rle_2frame.dcm",
        "SC_rgb_dcmtk_+eb+cy+n1.dcm",
        "SC_rgb_dcmtk_+eb+cy+np.dcm",
        "SC_jpeg_no_color_transform_2.dcm",
        "SC_rgb_rle_16bit_2frame.dcm",
        "SC_rgb_dcmtk_+eb+cy+n2.dcm",
        "SC_rgb_jpeg_dcmtk.dcm",
        "SC_rgb_jpeg_lossy_gdcm.dcm",
        "SC_jpeg_no_color_transform.dcm",
        "SC_rgb_small_odd_jpeg.dcm",
        "GDCMJ2K_TextGBR.dcm",
        "SC_rgb_gdcm_KY.dcm",
        "JPEG2000-embedded-sequence-delimiter.dcm",
        "SC_rgb_rle_32bit_2frame.dcm",
        "SC_rgb_jpeg_gdcm.dcm",
        "JPEG-lossy.dcm",
        "JPEG2000.dcm",
        "MR_small_jpeg_ls_lossless.dcm",
        "SC_rgb_rle_32bit.dcm",
        "J2K_pixelrep_mismatch.dcm",
        "rtdose_rle.dcm",
        "SC_rgb_rle_16bit.dcm",
    ]
]

cannot_read_names = {
    "rtplan_truncated.dcm",  # missing PixelData
    "no_meta_group_length.dcm",  # missing PixelData
    "rtstruct.dcm",  # missing PixelData
    "reportsi_with_empty_number_tags.dcm",  # missing PixelData
    "meta_missing_tsyntax.dcm",  # Missing BitsAllocated and other attr
    "waveform_ecg.dcm",  # missing PixelData
    "nested_priv_SQ.dcm",  # Missing BitsAllocated and other attr
    "no_meta.dcm",  # missing PixelData
    "empty_charset_LEI.dcm",  # missing PixelData
    "rtplan.dcm",  # missing PixelData
    "ExplVR_LitEndNoMeta.dcm",  # missing PixelData
    "UN_sequence.dcm",  # missing PixelData
    "reportsi.dcm",  # missing PixelData
    "priv_SQ.dcm",  # missing PixelData
    "test-SR.dcm",  # missing PixelData
    "image_dfl.dcm",  # missing PixelData
    "ExplVR_BigEndNoMeta.dcm",  # missing PixelData
    "emri_small_jpeg_2k_lossless_too_short.dcm",  # truncated
}
all_paths = (Path(f) for f in get_testdata_files("*.dcm"))
can_read_paths = [p for p in all_paths if p.name not in cannot_read_names]


class TestFrameReader:
    def setup(self):
        self.bot_list = [0, 32768, 65536]
        self.pixel_data_location = 4314
        self.first_frame_location = 4326
        self.liver_path = get_testdata_file("liver.dcm")
        self.rle_path = get_testdata_file("SC_rgb_rle_2frame.dcm")
        self.rle_basic_offset_table = [0, 672]
        self.rle_pixel_data_location = 1316
        self.rle_first_frame_location = 1344

    def test_read_encapsulated_basic_offset_table(self):
        with open(self.rle_path, "rb") as fp:
            file_like = framereader.DicomFileLike(fp)
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            result = framereader.read_encapsulated_basic_offset_table(
                file_like, self.rle_pixel_data_location
            )
            assert result == (
                self.rle_first_frame_location,
                self.rle_basic_offset_table,
            )

    def test_build_encapsulated_basic_offset_table(self):
        with open(self.rle_path, "rb") as fp:
            file_like = framereader.DicomFileLike(fp)
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            result = framereader.build_encapsulated_basic_offset_table(
                file_like, self.rle_first_frame_location, 2
            )
            assert result == self.rle_basic_offset_table

    def test_build_encapsulated_bot_raises_for_non_item_tag(self):
        with pytest.raises(IOError):
            with open(self.rle_path, "rb") as fp:
                file_like = framereader.DicomFileLike(fp)
                file_like.is_implicit_VR = False
                file_like.is_little_endian = True
                assert framereader.build_encapsulated_basic_offset_table(
                    file_like, self.rle_pixel_data_location, 2
                )

    def test_build_encapsulated_bot_raises_if_bot_too_short(self):
        with pytest.raises(ValueError):
            with open(self.rle_path, "rb") as fp:
                file_like = framereader.DicomFileLike(fp)
                file_like.is_implicit_VR = False
                file_like.is_little_endian = True
                assert framereader.build_encapsulated_basic_offset_table(
                    file_like, self.rle_first_frame_location, 4
                )

    def test_build_encapsulated_bot_raises_if_odd_item_length(self):
        with pytest.raises(IOError):
            item_length_3 = b"\xfe\xff\x00\xe0\x03\x00\x00\x00"
            file_like = framereader.DicomFileLike(BytesIO(item_length_3))
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            assert framereader.build_encapsulated_basic_offset_table(
                file_like, 0, 2
            )

    def test_build_encapsulated_basic_offset_table_raises_frame_length_0(self):
        with pytest.raises(IOError):
            item_length_0 = b"\xfe\xff\x00\xe0\x00\x00\x00\x00"
            file_like = framereader.DicomFileLike(BytesIO(item_length_0))
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            assert framereader.build_encapsulated_basic_offset_table(
                file_like, 0, 2
            )

    def test_build_encapsulated_basic_offset_table_jpg(self):
        path = get_testdata_file("JPEG2000.dcm")
        with open(path, "rb") as fp:
            file_like = framereader.DicomFileLike(fp)
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            result = framereader.build_encapsulated_basic_offset_table(
                file_like, 3042, 1
            )
            assert result == [0]

    def test_get_encapsulated_basic_offset_table_raises_for_non_item(self):
        with open(self.rle_path, "rb") as filereader:
            file_like = framereader.DicomFileLike(filereader)
            file_like.is_implicit_VR = False
            file_like.is_little_endian = True
            with mock.patch("pydicom.framereader.TupleTag") as mock_tuple_tag:
                mock_tuple_tag.side_effect = [
                    0x7FE00010,
                    ItemDelimiterTag
                ]
                with pytest.raises(ValueError):
                    assert framereader.get_encapsulated_basic_offset_table(
                        file_like, self.rle_pixel_data_location, 1
                    )

    @pytest.mark.parametrize("attr", framereader._REQUIRED_DATASET_ATTRIBUTES)
    def test_get_dataset_copy_with_frame_attrs_raises_if_missing_required_attr(
            self, attr
    ):
        dataset = dcmread(self.liver_path)
        delattr(dataset, attr)
        with pytest.raises(ValueError):
            assert framereader.get_dataset_copy_with_frame_attrs(dataset)

    def test_get_dataset_copy_with_frame_attrs_raises_if_missing_tsyntax(self):
        dataset = dcmread(self.liver_path)
        delattr(dataset.file_meta, "TransferSyntaxUID")
        with pytest.raises(ValueError):
            assert framereader.get_dataset_copy_with_frame_attrs(dataset)
        delattr(dataset, "file_meta")
        with pytest.raises(ValueError):
            assert framereader.get_dataset_copy_with_frame_attrs(dataset)

    def test_basic_offset_table_raises_without_kwargs(self):
        with pytest.raises(KeyError):
            assert framereader.BasicOffsetTable(self.bot_list)

    def test_basic_offset_table_with_kwargs(self):
        test_bot = framereader.BasicOffsetTable(
            self.bot_list,
            pixel_data_location=self.pixel_data_location,
            first_frame_location=self.first_frame_location,
        )
        assert test_bot.pixel_data_location == self.pixel_data_location
        assert test_bot.first_frame_location == self.first_frame_location

    def test_frame_dataset_liver(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            # test attributes are set
            assert test_frame_dataset.file_meta
            assert test_frame_dataset.is_little_endian
            assert not test_frame_dataset.is_implicit_VR
            assert test_frame_dataset.pixels_per_frame == 262144
            assert test_frame_dataset.bytes_per_frame == 32768
            assert test_frame_dataset.bytes_per_frame == 32768
            # test validate
            assert test_frame_dataset.validate_frame_dataset() is None

            # test get bot
            dcm_file_like = framereader.DicomFileLike(filereader)
            dcm_file_like.is_implicit_VR = test_frame_dataset.is_implicit_VR
            dcm_file_like.is_little_endian = \
                test_frame_dataset.is_little_endian
            bot = test_frame_dataset.get_basic_offset_table(
                dcm_file_like, self.pixel_data_location
            )
            assert bot == self.bot_list
            assert bot.pixel_data_location == self.pixel_data_location
            assert bot.first_frame_location == self.first_frame_location

    @pytest.mark.parametrize(
        "exc", [framereader.InvalidDicomError(), Exception()]
    )
    def test_frame_dataset_read_dataset_raises_ioerror(self, exc):
        with mock.patch(
                "pydicom.framereader.read_partial"
        ) as mock_read_partial:
            mock_read_partial.side_effect = exc
            with pytest.raises(IOError):
                with open(self.liver_path, "rb") as fp:
                    assert framereader.FrameDataset.read_dataset(fp)

    def test_frame_dataset_read_dataset__get_encapsulated_bot_raises_on_exc(
            self,
    ):
        with pytest.raises(IOError):
            with open(self.liver_path, "rb") as filereader:
                test_frame_dataset = framereader.FrameDataset.from_file(
                    filereader
                )
                dcm_file_like = framereader.DicomFileLike(filereader)
                dcm_file_like.is_implicit_VR = \
                    test_frame_dataset.is_implicit_VR
                dcm_file_like.is_little_endian = \
                    test_frame_dataset.is_little_endian
                # should except with pixeldata location of 0
                assert test_frame_dataset._get_encapsulated_basic_offset_table(
                    dcm_file_like, 0
                )

    def test_frame_dataset_infer_transfer_syntax(self):
        # implicit vr, little endian
        path = get_testdata_file("MR_small_implicit.dcm")
        with open(path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            delattr(test_frame_dataset.file_meta, "TransferSyntaxUID")
            test_frame_dataset.validate_frame_dataset()
            assert \
                test_frame_dataset.file_meta.TransferSyntaxUID.is_little_endian
            assert \
                test_frame_dataset.file_meta.TransferSyntaxUID.is_implicit_VR

    def test_frame_dataset_validate_raises_if_cannot_infer_tsyntax(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            delattr(test_frame_dataset.file_meta, "TransferSyntaxUID")
            with pytest.raises(IOError):
                assert test_frame_dataset.validate_frame_dataset()

    def test_frame_dataset_validate_raises_if_missing_required_attr(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            delattr(test_frame_dataset, "BitsAllocated")
            assert "BitsAllocated" in framereader._REQUIRED_DATASET_ATTRIBUTES
            with pytest.raises(IOError):
                assert test_frame_dataset.validate_frame_dataset()

    def test_frame_info_validate_pixel_data_raises_on_eof(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            dcm_file_like = framereader.DicomFileLike(filereader)
            dcm_file_like.is_implicit_VR = test_frame_dataset.is_implicit_VR
            dcm_file_like.is_little_endian = \
                test_frame_dataset.is_little_endian
            dcm_file_like.seek(0, 2)
            end_file = dcm_file_like.tell()
            with pytest.raises(IOError):
                assert framereader.FrameInfo.validate_pixel_data(
                    dcm_file_like, end_file
                )

    def test_frame_info_validate_pixel_data_raises_if_not_pixel_tags(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_dataset = framereader.FrameDataset.from_file(filereader)
            dcm_file_like = framereader.DicomFileLike(filereader)
            dcm_file_like.is_implicit_VR = test_frame_dataset.is_implicit_VR
            dcm_file_like.is_little_endian = \
                test_frame_dataset.is_little_endian
            with pytest.raises(ValueError):
                assert framereader.FrameInfo.validate_pixel_data(
                    dcm_file_like, 0
                )

    def test_frame_reader_open_raises_on_exc(self):
        with mock.patch("pydicom.framereader.open") as mock_open:
            mock_open.side_effect = IOError()
            with pytest.raises(OSError):
                with framereader.FrameReader(self.liver_path) as frame_reader:
                    assert frame_reader.open()

    @pytest.mark.parametrize("path", encaps_paths)
    def test_frame_info_to_from_dict(self, path):
        with open(path, "rb") as fp:
            frame_info = framereader.FrameInfo.from_file(fp)
            frame_info_dict = frame_info.to_dict()
            result = framereader.FrameInfo.from_dict(frame_info_dict)
            assert result.basic_offset_table == frame_info.basic_offset_table
            assert result.transfer_syntax_uid == frame_info.transfer_syntax_uid
            for attr in framereader._REQUIRED_DATASET_ATTRIBUTES:
                assert result.dataset.get(attr) == frame_info.dataset.get(attr)

    def test_frame_info_from_file(self):
        with open(self.liver_path, "rb") as filereader:
            test_frame_info = framereader.FrameInfo.from_file(filereader)
            assert test_frame_info.basic_offset_table == self.bot_list

    def test_frame_reader_liver(self):
        if can_decode:
            with framereader.FrameReader(self.liver_path) as frame_reader:
                assert frame_reader.basic_offset_table == self.bot_list
                for i in range(frame_reader.dataset.NumberOfFrames):
                    expected_shape = (
                        frame_reader.dataset.Rows,
                        frame_reader.dataset.Columns,
                    )
                    assert frame_reader.read_frame(i).shape == expected_shape

    def test_frame_reader_from_buffered_reader(self):
        with open(self.liver_path, "rb") as filereader:
            with framereader.FrameReader(filereader) as frame_reader:
                assert frame_reader.basic_offset_table == self.bot_list

    def test_frame_reader_open_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            frame_reader = framereader.FrameReader("does_not_exist.dcm")
            assert frame_reader.open()

    def test_frame_reader_decode_non_encapsulated(self):
        if can_decode:
            path = get_testdata_file("MR_small.dcm")
            dcm = dcmread(path)
            with framereader.FrameReader(path) as frame_reader:
                result = frame_reader.read_frame(0)
                assert numpy.array_equal(result, dcm.pixel_array)

    def test_frame_reader_decode_encapsulated(self):
        if can_decode:
            path = get_testdata_file("JPEG2000.dcm")
            dcm = dcmread(path)
            with framereader.FrameReader(path) as frame_reader:
                result = frame_reader.read_frame(0)
                assert numpy.array_equal(result, dcm.pixel_array)

    @pytest.mark.parametrize("path", encaps_paths)
    def test_frame_reader_encaps_parity(self, path):
        with framereader.FrameReader(path, force=True) as frame_reader:
            read_frames = [
                frame_reader.read_frame_raw(frame_index)
                for frame_index in range(frame_reader.number_of_frames)
            ]
            # seek to bot
            ob_offset = data_element_offset_to_value(
                frame_reader.dataset.is_implicit_VR, "OB"
            )
            frame_reader._fp.seek(frame_reader.pixel_data_location + ob_offset)
            pixel_bytes = frame_reader._fp.read()
            encaps_frames = [
                *generate_pixel_data_frame(pixel_bytes, len(read_frames))
            ]
            assert encaps_frames == read_frames

    @pytest.mark.parametrize("path", can_read_paths)
    def test_frame_reader_can_read(self, path):
        with framereader.FrameReader(path, force=True) as frame_reader:
            for frame_index in range(frame_reader.number_of_frames):
                assert frame_reader.read_frame_raw(frame_index)

    def test_frame_reader_closes_file_obj_on_except(self):
        # No pixel data
        path = get_testdata_file("priv_SQ.dcm")
        with pytest.raises(IOError):
            with open(path, "rb") as filereader:
                with framereader.FrameReader(path) as frame_reader:
                    assert frame_reader.read_frame_raw(0)
                assert filereader.closed

    def test_frame_reader_raises_if_non_item_tag_found(self):
        with pytest.raises(ValueError):
            with open(self.rle_path, "rb") as filereader:
                with framereader.FrameReader(filereader) as frame_reader:
                    frame_reader.basic_offset_table.append(674)
                    setattr(frame_reader, "_number_of_frames", 3)
                    assert frame_reader.read_frame_raw(2)

    def test_frame_reader_raises_if_index_greater_than_bot_length(self):
        with open(self.rle_path, "rb") as filereader:
            with framereader.FrameReader(filereader) as frame_reader:
                with pytest.raises(ValueError):
                    assert frame_reader.read_frame_raw(2)

    def test_frame_reader_initialize_with_frame_info(self):
        with BytesIO() as file_obj:
            with framereader.FrameReader(self.liver_path) as frame_reader:
                frame_reader.fp.seek(frame_reader.pixel_data_location)
                file_obj.write(frame_reader.fp.read())
                new_ff = frame_reader.first_frame_location - \
                    frame_reader.pixel_data_location
                new_bot = framereader.BasicOffsetTable(
                    frame_reader.basic_offset_table,
                    pixel_data_location=0,
                    first_frame_location=new_ff
                )

                frame_info_dict = frame_reader.frame_info.to_dict()
                frame_info_dict["basic_offset_table"] = new_bot.to_dict()
                new_frame_info = framereader.FrameInfo.from_dict(
                    frame_info_dict
                )
            with framereader.FrameReader(
                    file_obj, frame_info=new_frame_info
            ) as frame_reader:
                for frame_i in range(frame_reader.number_of_frames):
                    assert frame_reader.read_frame_raw(frame_i)
