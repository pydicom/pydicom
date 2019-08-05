# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Module for Media Storage SOP classes"""
from pydicom.dataset import FileDataset
from pydicom.sr.value_types import ContentSequence, ContentItem


class MediaStorage(FileDataset):

    pass

class ImageStorage(MediaStorage):

    pass

class SRStorage(MediaStorage):

    pass

class WaveformStorage(MediaStorage):

    pass

