# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Try reading a large RTSTRUCT file, profiling how much time it takes"""

# EDIT THIS SECTION --------------------------
#    to point to local temp directory

import pydicom
import cProfile
import pstats
import pytest

tempfile = "/tmp/pydicom_stats"
read_filename = r"/Users/darcy/hg/pydicom/source/dicom/testfiles/RStest.dcm"
write_filename = "/tmp/write_test.dcm"


@pytest.mark.skip(reason="This is not an actual pytest test")
def test_full_read(filename):
    dataset = pydicom.dcmread(filename)
    return dataset


def walkval(dataset, dataelem):
    dataelem.value


@pytest.mark.skip(reason="This is not an actual pytest test")
def test_convert_from_raw(dataset):
    # s = str(dataset)
    dataset.walk(walkval)


@pytest.mark.skip(reason="This is not an actual pytest test")
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
