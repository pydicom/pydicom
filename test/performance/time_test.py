# time_test.py
"""Try reading large sets of files, profiling how much time it takes"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import os.path
import os
import sys
on_windows = sys.platform.startswith("win")

# EDIT THIS SECTION --------------------------
#    to point to local temp directory, and to a set of >400 DICOM files of same size to work on
# I used images freely available from http://pcir.org
if on_windows:
    tempfile = "c:/temp/pydicom_stats"
    location_base = r"z:/testdicom/"
else:
    tempfile = "/tmp/pydicom_stats"
    location_base = r"/Users/darcy/testdicom/"
    # location_base = r"/Volumes/Disk 1/testdicom/"  # Network disk location
locations = [
    "77654033_19950903/77654033/19950903/CT2/",
    "98890234_20010101/98890234/20010101/CT5/",
    "98890234_20010101/98890234/20010101/CT6/",
    "98890234_20010101/98890234/20010101/CT7/",
]
locations = [os.path.join(location_base, location) for location in locations]
# -------------------------------------------------------
import glob
import dicom
from dicom.filereader import read_partial, _at_pixel_data
from io import BytesIO

import cProfile
import pstats
import sys
import random

rp = read_partial
filenames = []
for location in locations:
    loc_list = glob.glob(os.path.join(location, "*"))
    filenames.extend((x for x in loc_list if not x.startswith(".")))

assert len(filenames) >= 400, "Need at least 400 files"  # unless change slices below


print()
random.shuffle(filenames)  # to make sure no bias for any particular file


print("Sampling from %d files. Each test gets 100 distinct files" % len(filenames))
print("Test order is randomized too...")

# Give each test it's own set of files, to avoid reading something in cache from previous test
filenames1 = filenames[:100]  # keep the time to a reasonable amount (~2-25 sec)
filenames2 = filenames[100:200]
filenames3 = filenames[200:300]
filenames4 = filenames[300:400]


def test_full_read():
    rf = dicom.read_file
    datasets = [rf(fn) for fn in filenames1]
    return datasets


def test_partial():
    rp = read_partial
    [rp(open(fn, 'rb'), stop_when=_at_pixel_data) for fn in filenames2]


def test_mem_read_full():
    rf = dicom.read_file
    str_io = BytesIO
    memory_files = (str_io(open(fn, 'rb').read()) for fn in filenames3)
    [rf(memory_file) for memory_file in memory_files]


def test_mem_read_small():
    rf = dicom.read_file
    str_io = BytesIO  # avoid global lookup, make local instead
    memory_files = (str_io(open(fn, 'rb').read(4000)) for fn in filenames4)
    [rf(memory_file) for memory_file in memory_files]


def test_python_read_files():
    [open(fn, 'rb').read() for fn in filenames4]


if __name__ == "__main__":
    runs = ['datasets=test_full_read()',
            # 'test_partial()',
            # 'test_mem_read_full()',
            # 'test_mem_read_small()',
            'test_python_read_files()',
            ]
    random.shuffle(runs)
    for testrun in runs:
        cProfile.run(testrun, tempfile)
        p = pstats.Stats(tempfile)
        print("---------------")
        print(testrun)
        print("---------------")
        p.strip_dirs().sort_stats('time').print_stats(5)
    print("Confirming file read worked -- check for data elements near end")
    try:
        image_sizes = [len(ds.PixelData) for ds in datasets]  # NOQA
    except Exception as e:
        print("Failed to access dataset data for all files\nError:" + str(e))
    else:
        print("Reads checked ok.")

    # Clear disk cache for next run?
    if not on_windows:
        prompt = "Run purge command (linux/Mac OS X) to clear disk cache?...(N):"
        if sys.version_info[0] > 2:
            answer = input(prompt)
        else:
            answer = raw_input(prompt)
        if answer.lower() == "y":
            print("Running 'purge'. Please wait...")
            os.system("purge")
