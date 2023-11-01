"""
Demonstrates writing a video file to a DICOM dataset in an uncompressed format
while keeping the data out of memory.
"""
import os
import cv2
from tempfile import TemporaryFile
from pydicom import Dataset
from pydicom.uid import UltrasoundMultiFrameImageStorage, generate_uid

cine = cv2.VideoCapture("cine.mp4")
mp4_file_size = os.stat("cine.mp4").st_size

if not cine.isOpened():
    raise RuntimeError("Could not open cine")

file_meta = Dataset()
file_meta.MediaStorageSOPClassUID = UltrasoundMultiFrameImageStorage
file_meta.MediaStorageSOPInstanceUID = generate_uid()

dataset = Dataset()
dataset.file_meta = file_meta
dataset.is_little_endian = True
dataset.is_implicit_VR = True

# Image metadata - this makes assumptions based on the known attributes of the test file
# these attributes can be dynamically generated through inspecting the frames in the
# video
dataset.SamplesPerPixel = 3
dataset.BitsAllocated = 8
dataset.BitsStored = 8
dataset.HighBit = 7
dataset.PixelRepresentation = 0
dataset.PlanarConfiguration = 0
dataset.PhotometricInterpretation = "RGB"
dataset.Rows = int(cine.get(cv2.CAP_PROP_FRAME_HEIGHT))
dataset.Columns = int(cine.get(cv2.CAP_PROP_FRAME_WIDTH))
dataset.FrameTime = f"{1000 / int(cine.get(cv2.CAP_PROP_FPS)):.2f}"
dataset.FrameIncrementPointer = dataset.FrameTime

with TemporaryFile("+wb") as cine_pixeldata:
    frame_count = 0
    while True:
        more, frame = cine.read()

        if not more:
            break

        # change the frame from BGR to RGB and write to the file
        cine_pixeldata.write(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes())
        frame_count += 1

    cine_pixeldata.seek(0)

    # to demonstrate how much space uncompressed video data takes up
    print(
        f"expanded mp4 with {frame_count} frames from {mp4_file_size / 1000:.2f}KB to {cine_pixeldata.tell() / 1000:.2f}KB"
    )

    dataset.NumberOfFrames = frame_count
    # set PixelData to the buffer - writing the file will copy the pixeldata from the file to the dicom file
    # without reading the pixeldata into memory
    dataset.PixelData = cine_pixeldata
    dataset.save_as("ds.dcm", write_like_original=False)

cine.release()
