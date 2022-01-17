# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""Debugging functions to help with troubleshooting."""

from typing import cast

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import generate_pixel_data_frame
from pydicom.jpeg.jpeg10918 import debug_jpeg
from pydicom.jpeg.jpeg15444 import debug_jpeg2k
from pydicom.uid import JPEGTransferSyntaxes, JPEG2000TransferSyntaxes


def debug_pixel_data(ds: Dataset, idx: int = 0) -> None:
    """Print debugging information to help with pixel data troubleshooting.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to troubleshoot.
    idx : int, optional
        For multi-framed pixel data, this is the frame index to troubleshoot.
    """
    ds_class = ds.__class__.__name__
    if not isinstance(ds, Dataset):
        raise TypeError(
            f"'ds' should be pydicom.dataset.Dataset, not '{ds_class}'"
        )

    s = []

    # Check File Meta Information
    meta = getattr(ds, "file_meta", None)
    if meta is not None:
        s.append("File Meta Information: present")
    else:
        s.append("File Meta Information: absent")

    # Check transfer syntax
    tsyntax = None
    if meta:
        tsyntax = meta.get("TransferSyntaxUID")
        if tsyntax.is_private:
            s.append(f"  Transfer Syntax UID: {tsyntax}")
        else:
            s.append(f"  Transfer Syntax UID: {tsyntax} ({tsyntax.name})")
    else:
        s.append("  Transfer Syntax UID: (none available)")

    s.append("")
    s.append("Dataset")

    # Check Image Pixel module
    for elem in ds.group_dataset(0x0028):
        s.append(f"  {str(elem)}")

    # Check pixel data
    px_keyword = ["PixelData", "FloatPixelData", "DoubleFloatPixelData"]
    px_keyword = [kw for kw in px_keyword if kw in ds]
    if not px_keyword:
        s.append("  No pixel data elements found")
    elif len(px_keyword) > 1:
        s.append(
            f"  Multiple pixel data elements found: {', '.join(px_keyword)}"
        )
    elif len(px_keyword) == 1:
        s.append(f"  {str(ds[px_keyword[0]])}")
        s.append("")

        # Try and parse the JPEG info
        if tsyntax in JPEGTransferSyntaxes:
            s.append(f"JPEG codestream info for frame {idx}")
            info = debug_jpeg(_get_frame_data(ds, idx))
            s.extend([f"  {s}" for s in info])

        if tsyntax in JPEG2000TransferSyntaxes:
            s.append(f"JPEG 2000 codestream info for frame {idx}")
            info = debug_jpeg2k(_get_frame_data(ds, idx))
            s.extend([f"  {s}" for s in info])

    for line in s:
        print(line)

def _get_frame_data(ds: Dataset, idx: int) -> bytes:
    """Return the encapsulated frame data at index `idx`"""
    # May be absent, None, 0 or positive int
    nr_frames = int(ds.get("NumberOfFrames", 1) or 1)

    frame_nr = 0
    gen = generate_pixel_data_frame(ds.PixelData, nr_frames)
    while frame_nr != idx:
        next(gen)
        frame_nr += 1

    return next(gen)
