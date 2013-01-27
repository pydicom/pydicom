# raw_convert_test.py
"""Try reading a large RTSTRUCT file, profiling how much time it takes"""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# EDIT THIS SECTION --------------------------
#    to point to local temp directory

tempfile = "/tmp/pydicom_stats"
read_filename = r"/Users/darcy/hg/pydicom/source/dicom/testfiles/RStest.dcm"
write_filename = "/tmp/write_test.dcm"

import dicom
import cProfile
import pstats


def test_full_read(filename):
    dataset = dicom.read_file(filename)
    return dataset


def walkval(dataset, dataelem):
    dataelem.value


def test_convert_from_raw(dataset):
    # s = str(dataset)
    dataset.walk(walkval)


def test_write_file(dataset, write_filename):
    dataset.save_as(write_filename)


if __name__ == "__main__":
    runs = ['ds=test_full_read(read_filename)',
            'test_convert_from_raw(ds)',
            'test_write_file(ds, write_filename)',
            ]
    for testrun in runs:
        cProfile.run(testrun, tempfile)
        p = pstats.Stats(tempfile)
        print("---------------")
        print(testrun)
        print("---------------")
        p.strip_dirs().sort_stats('time').print_stats(12)

    # Clear disk cache for next run?
#    import sys
#    if not on_windows:
#        prompt= "Run purge command (linux/Mac OS X) to clear disk cache?(N):"
#        answer = raw_input(prompt)
#        if answer.lower() == "y":
#            print "Running 'purge'. Please wait..."
#            os.system("purge")
