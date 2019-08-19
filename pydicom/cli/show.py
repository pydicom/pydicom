# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for `pydicom show`"""

from pydicom import dcmread


def add_subparser(subparsers):
    subparser = subparsers.add_parser(
        "show", description="Display all or part of a DICOM file"
    )
    subparser.add_argument("filename", help="DICOM file to show")
    subparser.add_argument(
        "-x",
        "--exclude-private",
        help="Don't show private data elements",
        action="store_true",
    )
    subparser.add_argument(
        "-t", "--top", help="Only show top level", action="store_true"
    )
    subparser.add_argument(
        "-q",
        "--quiet",
        help="Only show basic information",
        action="store_true",
    )

    subparser.set_defaults(func=do_command)


def do_command(args):
    try:
        ds = dcmread(args.filename, force=True)
    except Exception:
        print("Unable to read file {}".format(args.filename))
        return

    if args.exclude_private:
        ds.remove_private_tags()

    if args.quiet:
        show_quiet(ds)
    elif args.top:
        print(ds.top())
    else:
        print(repr(ds))


def SOPClassname(ds):
    class_uid = ds.get("SOPClassUID")
    if class_uid is None:
        return None
    return "SOPClassUID: {}".format(class_uid.name)


def quiet_rtplan(ds):
    if "BeamSequence" not in ds:
        return None

    lines = []
    lines.append("Plan name: {}".format(ds.get("RTPlanName", "N/A")))

    for beam in ds.BeamSequence:
        s = "Beam {} '{}' {}"
        results = [
            beam.get(kywd) for kywd in ["BeamNumber", "BeamName", "BeamType"]
        ]
        beam_type = beam.get("BeamType")
        if beam_type == "STATIC":
            cp = beam.ControlPointSequence[0]
            if cp:
                more_results = [
                    cp.get(kywd)
                    for kywd in [
                        "GantryAngle",
                        "BeamLimitingDeviceAngle",
                        "PatientSupportAngle",
                    ]
                ]
                s += " gantry {}, coll {}, couch {}"
                results.extend(more_results)
        lines.append(s.format(*results))
    return "\n".join(lines)


def quiet_image(ds):
    if "Image Storage" not in ds.SOPClassUID.name:
        return None
    s = "Image: {}-bit {} {}x{} pixels Slice location: {}"
    results = [
        ds.get(name, "N/A")
        for name in [
            "BitsStored",
            "Modality",
            "Rows",
            "Columns",
            "SliceLocation",
        ]
    ]
    return s.format(*results)


# Items to show in quiet mode
# Item can be a callable or a DICOM keyword
quiet_items = [
    SOPClassname,
    "PatientName",
    "PatientID",
    # Images
    "StudyID",
    "StudyDate",
    "StudyTime",
    "StudyDescription",
    quiet_image,
    quiet_rtplan,
]


def show_quiet(ds):
    for item in quiet_items:
        if callable(item):
            result = item(ds)
            if result:
                print(result)
        else:
            print("{}: {}".format(item, ds.get(item, "N/A")))
