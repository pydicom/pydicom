# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for `pydicom show`"""

from pydicom import dcmread
from pydicom.data.data_manager import get_testdata_file
from pydicom.dataset import Dataset
import sys

from pydicom.cli.main import filespec_help, filespec_parser

def add_subparser(subparsers):
    subparser = subparsers.add_parser(
        "show", description="Display all or part of a DICOM file"
    )
    subparser.add_argument(
        "filespec", 
        help=filespec_help,
        type=filespec_parser
    )
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
    ds, element = args.filespec
    if not element:
        element = ds

    if args.exclude_private:
        ds.remove_private_tags()

    if args.quiet and isinstance(element, Dataset):
        show_quiet(element)
    elif args.top and isinstance(element, Dataset):
        print(element.top())
    else:
        print(str(element))


def SOPClassname(ds):
    class_uid = ds.get("SOPClassUID")
    if class_uid is None:
        return None
    return f"SOPClassUID: {class_uid.name}"


def quiet_rtplan(ds):
    if "BeamSequence" not in ds:
        return None

    plan_label = ds.get('RTPlanLabel')
    plan_name = ds.get('RTPlanName')
    line = f"Plan Label: {plan_label}  "
    if plan_name:
        line += f"Plan Name: {plan_name}"
    lines = [line]

    if 'FractionGroupSequence' in ds:  # it should be
        for fraction_group in ds.FractionGroupSequence:
            fraction_group_num = fraction_group.get('FractionGroupNumber', '')
            lines.append(f"Fraction Group {fraction_group_num}")
            for refd_beam in fraction_group.ReferencedBeamSequence:
                ref_num = refd_beam.get("ReferencedBeamNumber")
                dose = refd_beam.get("BeamDose")
                mu = refd_beam.get("BeamMeterset")
                line = f"   Beam {ref_num} "
                if dose or mu:
                    line += f"Dose {dose} Meterset {mu}"
                lines.append(line)
    
    for beam in ds.BeamSequence:
        beam_num = beam.get("BeamNumber")
        beam_name = beam.get("BeamName")
        beam_type = beam.get("BeamType")
        beam_delivery = beam.get("TreatmentDeliveryType")
        beam_radtype = beam.get("RadiationType")
        line = f"Beam {beam_num} '{beam_name}' {beam_delivery} {beam_type} {beam_radtype}"
              
        if beam_type == "STATIC":
            cp = beam.ControlPointSequence[0]
            if cp:
                energy = cp.get("NominalBeamEnergy")
                gantry = cp.get("GantryAngle")
                bld = cp.get("BeamLimitingDeviceAngle")
                couch = cp.get("PatientSupportAngle")
        
                line += f" energy {energy} gantry {gantry}, coll {bld}, couch {couch}"
        lines.append(line)
    return "\n".join(lines)


def quiet_image(ds):
    if "SOPClassUID" not in ds or "Image Storage" not in ds.SOPClassUID.name:
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
            print(f"{item}: {ds.get(item, 'N/A')}")
