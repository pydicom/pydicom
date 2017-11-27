# time_test.py
"""Try reading large sets of files, profiling how much time it takes"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom

import cProfile
from io import BytesIO
import glob
import os
import os.path
import pydicom

from pydicom.filereader import (
    read_partial,
    _at_pixel_data
)

import pstats
import pytest
import random
import sys
on_windows = sys.platform.startswith("win")


# EDIT THIS SECTION --------------------------
#    to point to local temp directory, and to a set of
#    >400 DICOM files of same size to work on
#    I used images freely available from http://pcir.org
if on_windows:
    tempfile = "c:/temp/pydicom_stats"
    tempwrite = "c:/temp/tempwrite"
    location_base = r"c:/temp/testdicom/"
else:
    tempfile = "/tmp/pydicom_stats"
    location_base = r"/Users/darcy/testdicom/"
    # location_base = r"/Volumes/Disk 1/testdicom/"  # Network disk location
locations = [
    "77654033_19950903/77654033/19950903/CT2/",
    # "98890234_20010101/98890234/20010101/CT5/",
    # "98890234_20010101/98890234/20010101/CT6/",
    # "98890234_20010101/98890234/20010101/CT7/",
]
locations = [os.path.join(location_base, location) for location in locations]
datasets = []
# -------------------------------------------------------

rp = read_partial
filenames = []
for location in locations:
    loc_list = glob.glob(os.path.join(location, "*"))
    filenames.extend((x for x in loc_list if not x.startswith(".")))

# assert len(filenames) >= 400
# "Need at least 400 files"
# unless change slices below

print()


# Give each test it's own set of files, to avoid
# reading something in cache from previous test
# keep the time to a reasonable amount (~2-25 sec)
filenames1 = filenames[:50]
# filenames2 = filenames[100:200]
# filenames3 = filenames[200:300]
# filenames4 = filenames[300:400]

reason = "Not doing time tests."
reason = "%s Need at least 400 files in %s" % (reason, str(locations))


def test_write():
    for ds in datasets:
        ds.save_as(ds.new_filename)

@pytest.mark.skipif(len(filenames) < 400,
                    reason=reason)
def test_python_write_files():
    [open(fn, 'rb').read() for fn in filenames4]
    

if __name__ == "__main__":
    print("Reading files from", location_base)
    
    write_filenames = filenames1[:50]
    # print("Filenames:", write_filenames)
    datasets = [pydicom.dcmread(fn) for fn in write_filenames]
    for ds in datasets:
        ds.new_filename = os.path.join(tempwrite, os.path.basename(ds.filename))
    
    num_tags = sum([len(x.keys()) for x in datasets])
    print("Total number of tags: %d in %d files" % (num_tags, len(datasets)))
      
    runs = ['test_write()',
            # 'test_python_write_files()',
            ]



    do_trace = False   
    if do_trace:       
        import trace

        # create a Trace object, telling it what to ignore, and whether to
        # do tracing or line-counting or both.
        tracer = trace.Trace(
            ignoredirs=[sys.prefix, sys.exec_prefix],
            trace=0,
            count=1)

        # run the new command using the given tracer
        tracer.run('test_write()')

        # make a report, placing output in the current directory
        r = tracer.results()
        r.write_results(show_missing=True, coverdir=".")            

        sys.exit()
    
    for testrun in runs:
        cProfile.run(testrun, tempfile)
        p = pstats.Stats(tempfile)
        print("---------------")
        print(testrun)
        print("---------------")
        p.strip_dirs().sort_stats('time').print_stats(8)


    # Clear disk cache for next run?
    if not on_windows:
        prompt = "Run purge command (linux/Mac OS X)"
        prompt = "%s to clear disk cache?...(N):" % (prompt)
        if sys.version_info[0] > 2:
            answer = input(prompt)
        else:
            answer = raw_input(prompt)
        if answer.lower() == "y":
            print("Running 'purge'. Please wait...")
            os.system("purge")
