# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for `pydicom show`"""

import argparse
from glob import glob
from collections.abc import Callable

from pydicom.dataset import Dataset
from pydicom.cli.main import filespec_parser, filespec_parts

filespec_glob_help = (
    "File specification, in format [pydicom::]filename_glob[::element]. "
    "If `pydicom::` prefix is present, then use the pydicom "
    "test file with that name. If `element` is given, "
    "use only that data element within the file. "
    "The filename_glob can contain python glob patterns to match multiple files."
    "The globs should be protected from shell interpolation"
    "to ensure processing by showglob."
    "Showglob only accepts one glob pattern and applies the same"
    "prefix and element to the result file list."
    "Examples: "
    "*.dcm,"
    "*.dcm::Stuydate"
    "path/to/your_file.dcm, "
    "your_file.dcm::StudyDate, "
    "your_file.dcm::(0001,0001), "
    "pydicom::rtplan.dcm::BeamSequence[0], "
    "yourplan.dcm::BeamSequence[0].BeamNumber, "
    "pydicom::rtplan.dcm::(300A,00B0)[0].(300A,00B6)"
)


def filespec_glob_parser(filespec_glob: str) -> list[str]:
    """Utility to return a list of filespecs that match a file glob pattern.

    Note: this is used as an argparse 'type' for adding parsing arguments.

    Parameters
    ----------
    filespec_glob: str
        A filename with optional `pydicom::` prefix and optional data element,
        in format:
            [pydicom::]<filename_glob>[::<element>]
        If an element is specified, it must be a path to a data element,
        sequence item (dataset), or a sequence, specified with
        DICOM keywords, or DICOM tags in the format (gggg,eeee).
        Works just like "show" except it can match multiple files through
        a single glob pattern in filename_glob.


        Examples:
            your_file.dcm
            your_file.dcm::StudyDate
            *.dcm
            *.dcm::StudyDate
            pydicom::ct_small.dcm::(0019,0010)
            pydicom::rtplan.dcm::BeamSequence[0]
            pydicom::rtplan.dcm::BeamSequence[0].BeamLimitingDeviceSequence
            pydicom::rtplan.dcm::(300A,00B0)[0]
            pydicom::rtplan.dcm::(300A,00B0)[0].BeamLimitingDeviceSequence
            pydicom::rtplan.dcm::(300A,00B0)[0].(300A,00B6)

    Returns
    -------
    List[list of filespecs]
        This usually is a list of filespec files
        to work across multiple files.

    Note
    ----
        This function is meant to be used in a call to an `argparse` library's
        `add_argument` call for subparsers, with name="filespec_glob" and
        `type=filespec_glob_parser`. The resulting args.filespec_glob
        will contain the return values of this function
        (e.g. use `ds, element_val = filespec_parser(filespec)` after parsing arguments)
        See the `pydicom.cli.show` module for an example.

    Raises
    ------
    argparse.ArgumentTypeError
        If the filename glob pattern does not match existing files.
    """
    prefix, filename, element = filespec_parts(filespec_glob)

    # generate list of files if filename is a glob
    special_chars = ["*", "?", "[", "]"]
    if any(char in filename for char in special_chars):
        file_names = glob(filename)
    else:
        file_names = [filename]

    return ["::".join([prefix, filename, element]) for filename in file_names]


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    subparser = subparsers.add_parser(
        "showglob",
        description="Display all or part of a set of DICOM files matching glob pattern",
    )
    subparser.add_argument(
        "filespec_glob", help=filespec_glob_help, type=filespec_glob_parser
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


def do_command(args: argparse.Namespace) -> None:

    for filespec in args.filespec_glob:
        ds, element_val = filespec_parser(filespec)[0]

        if not element_val:
            element_val = ds

        if args.exclude_private:
            ds.remove_private_tags()

        if args.quiet and isinstance(element_val, Dataset):
            show_quiet(element_val)
        elif args.top and isinstance(element_val, Dataset):
            print(element_val.top())
        else:
            print(str(element_val))


def SOPClassname(ds: Dataset) -> str | None:
    class_uid = ds.get("SOPClassUID")
    if class_uid is None:
        return None
    return f"SOPClassUID: {class_uid.name}"


def quiet_rtplan(ds: Dataset) -> str | None:
    if "BeamSequence" not in ds:
        return None

    plan_label = ds.get("RTPlanLabel")
    plan_name = ds.get("RTPlanName")
    line = f"Plan Label: {plan_label}  "
    if plan_name:
        line += f"Plan Name: {plan_name}"
    lines = [line]

    if "FractionGroupSequence" in ds:  # it should be, is mandatory
        for fraction_group in ds.FractionGroupSequence:
            fraction_group_num = fraction_group.get("FractionGroupNumber", "")
            descr = fraction_group.get("FractionGroupDescription", "")
            fractions = fraction_group.get("NumberOfFractionsPlanned")
            fxn_info = f"{fractions} fraction(s) planned" if fractions else ""
            lines.append(f"Fraction Group {fraction_group_num} {descr} {fxn_info}")
            num_brachy = fraction_group.get("NumberOfBrachyApplicationSetups")
            lines.append(f"   Brachy Application Setups: {num_brachy}")
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
        line = (
            f"Beam {beam_num} '{beam_name}' {beam_delivery} {beam_type} {beam_radtype}"
        )

        if beam_type == "STATIC":
            cp = beam.ControlPointSequence[0]
            if cp:
                energy = cp.get("NominalBeamEnergy")
                gantry = cp.get("GantryAngle")
                bld = cp.get("BeamLimitingDeviceAngle")
                couch = cp.get("PatientSupportAngle")
                line += f" energy {energy} gantry {gantry}, coll {bld}, couch {couch}"

        wedges = beam.get("NumberOfWedges")
        comps = beam.get("NumberOfCompensators")
        boli = beam.get("NumberOfBoli")
        blocks = beam.get("NumberOfBlocks")

        line += f" ({wedges} wedges, {comps} comps, {boli} boli, {blocks} blocks)"

        lines.append(line)

    return "\n".join(lines)


def quiet_image(ds: Dataset) -> str | None:
    if "SOPClassUID" not in ds or "Image Storage" not in ds.SOPClassUID.name:
        return None

    results = [
        f"{name}: {ds.get(name, 'N/A')}"
        for name in [
            "BitsStored",
            "Modality",
            "Rows",
            "Columns",
            "SliceLocation",
        ]
    ]
    return "\n".join(results)


# Items to show in quiet mode
# Item can be a callable or a DICOM keyword
quiet_items: list[Callable[[Dataset], str | None] | str] = [
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


def show_quiet(ds: Dataset) -> None:
    for item in quiet_items:
        if callable(item):
            result = item(ds)
            if result:
                print(result)
        else:
            print(f"{item}: {ds.get(item, 'N/A')}")
