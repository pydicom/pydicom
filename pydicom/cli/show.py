# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for `pydicom show`"""

from pydicom import dcmread
from pydicom.compat import int_type

default_exclude_size = 100


def SOPClassname(ds):
    class_uid = ds.get("SOPClassUID")
    if class_uid is None:
        return None
    return "SOPClassUID: {}".format(class_uid.name)

def num_beams(ds):
    if 'BeamSequence' not in ds:
        return None
    return "Number of beams: {}".format(len(ds.BeamSequence))

# Items to show for different verbosity levels
# Item can be a callable or a DICOM keyword
verbosity_items = {
    0: [SOPClassname, "Modality", "PatientName", "PatientID"],
    1: [
        # Images
        "StudyID",
        "StudyDate",
        "StudyTime",
        "StudyDescription",
        "SliceThickness",
        "SliceLocation",
        "Rows",
        "Columns",
        "BitsStored",
        # Radiotherapy
        "RTPlanName",
        "RTPlanLabel",
        num_beams,
    ],
}


def add_subparser(subparsers):
    subparser = subparsers.add_parser(
        "show",
        description="Display all or part of a DICOM file's data elements",
    )
    subparser.add_argument("filename", help="DICOM file to show")
    subparser.add_argument(
        "-v", "--verbosity", nargs="?", type=int_type, default=1,
        choices=[0, 1],
    )
    subparser.set_defaults(func=show)


def show(args):
    try:
        ds = dcmread(args.filename, force=True)
    except:
        print("Unable to read file {}".format(args.filename))
        return

    i = 0
    while i <= args.verbosity:
        for item in verbosity_items[i]:
            if callable(item):
                result = item(ds)
                if result:
                    print(result)
            else:
                print("{}: {}".format(item, ds.get(item, "N/A")))
        i += 1