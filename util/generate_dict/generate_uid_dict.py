#!/usr/bin/env python

"""
Reformat the UID list (tables A-1 and A-2) from the PS3.6 docbook file to
Python syntax.

Write the dict element as:
    UID: (name, type, info, is_retired, keyword)

    * info is extra information extracted from very long names, e.g.
        which bit size a particular transfer syntax is default for
    * is_retired is 'Retired' if true, else ''

Based on Rickard Holmberg's docbook_to_uiddict2013.py.
"""

import argparse
import os
from pathlib import Path
from urllib import request
import xml.etree.ElementTree as ET

from pydicom import _version


_PKG_DIRECTORY = Path(__file__).parent.parent.parent / "src" / "pydicom"
PYDICOM_DICT_FILENAME = _PKG_DIRECTORY / "_uid_dict.py"
DICT_NAME = "UID_dictionary"
BR = "{http://docbook.org/ns/docbook}"


def write_dict(fp, dict_name, attributes):
    """Write the `dict_name` dict to file `fp`.

    Parameters
    ----------
    fp : file
        The file to write the dict to.
    dict_name : str
        The name of the dict variable.
    attributes : list of str
        List of attributes of the dict entries.
    """
    uid_entry = (
        "('{UID Name}', '{UID Type}', '{UID Info}', '{Retired}', " "'{UID Keyword}')"
    )
    entry_format = "'{UID Value}': %s" % (uid_entry)

    fp.write(f"\n{dict_name} = {{\n    ")
    fp.write(",  # noqa\n    ".join(entry_format.format(**attr) for attr in attributes))
    fp.write("  # noqa\n}\n")


def parse_row(column_names, row):
    """Parses `row` for the DICOM Element data.

    The row should be <tbody><tr>...</tr></tbody>
    Which leaves the following:
        <td><para>Value 1</para></td>
        <td><para>Value 2</para></td>
        etc...
    Some rows have
        <td><para><emphasis>Value 1</emphasis></para></td>
        <td><para><emphasis>Value 2</emphasis></para></td>
        etc...
    There are also some without text values
        <td><para/></td>
        <td><para><emphasis/></para></td>

    Parameters
    ----------
    column_names : list of str
        The column header names
    row
        The XML for the header row of the table

    Returns
    -------
    dict
        {header1 : val1, header2 : val2, ...} representing the
        information for the row.
    """
    # Value, name, keyword, type | info, retired
    cell_values = [] * len(column_names)
    for cell in row.iter(f"{BR}para"):
        # If we have an emphasis tag under the para tag
        emph_value = cell.find(f"{BR}emphasis")
        if emph_value is not None:
            # If there is a text value add it, otherwise add ""
            if emph_value.text is not None:
                # 200b is a zero width space
                cell_values.append(emph_value.text.strip().replace("\u200b", ""))
            else:
                cell_values.append("")

        # Otherwise just grab the para tag text
        else:
            if cell.text is not None:
                cell_values.append(cell.text.strip().replace("\u200b", ""))
            else:
                cell_values.append("")

    cell_values.append("")

    return {k: v for k, v in zip(column_names, cell_values)}


def parse_docbook_table(root, labels, caption):
    """Return the parsed XML data for a table.

    Parameters
    ----------
    root
        The XML book root
    labels : List[str]
        The table column labels.
    caption : str
        The caption of the table to be parsed.

    Returns
    -------
    List[Dict[str, str]]
        The list of dicts generated by parsing the table.
    """
    # Find the table in book_root with caption
    for table in root.iter(f"{BR}table"):
        if table.find(f"{BR}caption").text == caption:
            # Get all the Element data from the table
            return [
                parse_row(labels, row)
                for row in table.find(f"{BR}tbody").iter(f"{BR}tr")
            ]

    raise ValueError(f"No tables found with the caption {caption}")


def parse_a1(root):
    """Return the parsed XML data for Table  A-1.

    Parameters
    ----------
    root
        The XML book root

    Returns
    -------
    List[Dict[str, str]]
        The list of dicts generated by parsing the table.
    """
    labels = [
        "UID Value",
        "UID Name",
        "UID Keyword",
        "UID Type",
        "UID Info",
        "Retired",
    ]
    attrs = parse_docbook_table(root, labels, "UID Values")

    # Customisations for Table A-1
    for attr in attrs:
        name = attr["UID Name"]
        if "(Retired)" in name:
            attr["Retired"] = "Retired"
            attr["UID Name"] = attr["UID Name"].replace("(Retired)", "").strip()

        if ":" in name:
            name = name.split(":")
            attr["UID Name"] = name[0].strip()
            attr["UID Info"] = name[-1].strip()

    return attrs


def parse_a2(root):
    """Return the parsed XML data for Table  A-2.

    Parameters
    ----------
    root
        The XML book root

    Returns
    -------
    List[Dict[str, str]]
        The list of dicts generated by parsing the table.
    """
    labels = ["UID Value", "UID Name", "UID Keyword", "Normative Reference"]
    attrs = parse_docbook_table(root, labels, "Well-known Frames of Reference")

    # Customisations for Table A-2
    for v in attrs:
        v["UID Type"] = "Well-known frame of reference"
        v["UID Info"] = ""
        v["Retired"] = ""
        del v["Normative Reference"]

    return attrs


def setup_argparse():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a new _uid_dict.py file from Part 6 of the " "DICOM Standard"
        ),
        usage="generate_uid_dict.py [options]",
    )

    opts = parser.add_argument_group("Options")
    opts.add_argument(
        "--local",
        help=(
            "The path to the directory containing the XML files (used instead "
            "of downloading them)"
        ),
        type=str,
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = setup_argparse()
    USE_DOWNLOAD = True
    if args.local:
        USE_DOWNLOAD = False

    attrs = []

    if not USE_DOWNLOAD:
        local_dir = Path(args.local)
        part_06 = (local_dir / "part06.xml").resolve(strict=True)
    else:
        url = "https://medical.nema.org/medical/dicom/current/source/docbook"
        url_06 = f"{url}/part06/part06.xml"
        print(f"Downloading '{url_06}'")
        part_06 = request.urlopen(url_06)
        print("Download complete, processing...")

    tree = ET.parse(part_06)
    root = tree.getroot()

    # Check the version is up to date
    dcm_version = root.find(f"{BR}subtitle")
    dcm_version = dcm_version.text.split()[2]
    lib_version = getattr(_version, "__dicom_version__", None)
    if lib_version != dcm_version:
        print(
            "Warning: 'pydicom._version.__dicom_version__' needs to be "
            f"updated to '{dcm_version}'"
        )

    attrs += parse_a1(root)
    attrs += parse_a2(root)

    for attr in attrs:
        attr["UID Name"] = attr["UID Name"].replace("&", "and")
        attr["UID Value"] = attr["UID Value"].replace("\u00ad", "")

    with open(PYDICOM_DICT_FILENAME, "w") as f:
        f.write(
            '"""DICOM UID dictionary auto-generated by '
            f'{os.path.basename(__file__)}"""\n'
        )
        f.write("# Each dict entry is UID: (Name, Type, Info, Retired, Keyword)")
        write_dict(f, DICT_NAME, attrs)

    print(f"Finished, wrote {len(attrs)} UIDs")
