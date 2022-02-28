#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Encoding required to deal with 'micro' character

"""
Create the _dicom_dict.py DICOM dictionary file from the Standard.

Reformat The DICOM dictionary PS3.6 and PS3.7 docbook xml files (from e.g.
standard docs) to Python syntax.

DicomDictionary
---------------
Write the main DICOM dictionary elements as a python dict called
`main_attributes` with format:
    Tag: ('VR', 'VM', "Name", 'is_retired', 'Keyword')

Where:
    * Tag is a 32-bit representation of the group, element as 0xggggeeee
        (e.g. 0x00181600)
    * VR is the Value Representation (e.g. 'OB' or 'OB or UI' or 'NONE')
    * VM is the Value Multiplicity (e.g. '1' or '2-2n' or '3-n' or '1-32')
    * Name is the DICOM Element Name (or Message Field for Command Elements)
        (e.g. 'Tomo Time' or 'Retired-blank' or 'Time Source')
    * is_retired is '' if not retired, 'Retired' otherwise (e.g. '' or
        'Retired')
    * Keyword is the DICOM Keyword (e.g. 'TomoTime' or 'TimeSource')

The results are sorted in ascending order of the Tag.

RepeatersDictionary
-------------------
Also write the repeating groups or elements (e.g. group "50xx") as a python
dict called `mask_attributes` as masks that can be tested later for tag lookups
that didn't work using format:
    'Tag': ('VR', 'VM', "Name", 'is_retired', 'Keyword')

Where:
    * Tag is a string representation of the element (e.g. '002031xx' or
    '50xx0022')

The results are sorted in ascending order of the Tag.


Based on Rickard Holmberg's docbook_to_dict2013.py.
"""

import argparse
import itertools
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import urllib.request as urllib2

from pydicom import _version
from pydicom.values import converters


_PKG_DIRECTORY = Path(__file__).parent.parent.parent / "pydicom"
PYDICOM_DICT_FILENAME = _PKG_DIRECTORY / "_dicom_dict.py"
MAIN_DICT_NAME = 'DicomDictionary: Dict[int, Tuple[str, str, str, str, str]]'
MASK_DICT_NAME = (
    'RepeatersDictionary: Dict[str, Tuple[str, str, str, str, str]]'
)
BR = "{http://docbook.org/ns/docbook}"


def write_dict(fp, dict_name, attributes, tag_is_string):
    """Write the `dict_name` dict to file `fp`.

    Parameters
    ----------
    fp : file
        The file to write the dict to.
    dict_name : str
        The name of the dict variable.
    attributes : list of str
        List of attributes of the dict entries.
    tag_is_string : bool
        If the tag is a string (as it is for the RepeatersDictionary)
    """
    tag_content = """('{VR}', '{VM}', "{Name}", '{Retired}', '{Keyword}')"""
    if tag_is_string:
        entry_format = f"'{{Tag}}': {tag_content}"
    else:
        entry_format = f"{{Tag}}: {tag_content}"

    fp.write(f"\n{dict_name} = {{\n    ")
    fp.write(
        ",  # noqa\n    ".join(
            entry_format.format(**attr) for attr in attributes
        )
    )
    fp.write("  # noqa\n}\n")


def parse_header(header_row):
    """Parses the table's thead/tr row, header_row, for the column
    headers

    The header_row should be <thead><tr>...</tr></thead>
    Which leaves the following:
        <th><para><emphasis>Header 1</emphasis></para></th>
        <th><para><emphasis>Header 2</emphasis></para></th>
        etc...
    Note that for the part06 tables the last col header
    (Retired) is:
        <th><para/></th>

    Parameters
    ----------
    header_row
        The XML for the header row of the table

    Returns
    -------
    field_names : list of str
        A list of the field header names used in the table
    """
    field_names = []
    for x in header_row.iter(f"{BR}th"):
        # If there is an emphasis tag under the para tag then its
        #   text is the column header
        if x.find(f"{BR}para").find(f"{BR}emphasis") is not None:  # noqa
            col_label = x.find(f"{BR}para").find(f"{BR}emphasis").text  # noqa
            field_names.append(col_label)

        # If there isn't an emphasis tag under the para tag then it
        #   must be the Retired header
        else:
            field_names.append("Retired")

    return field_names


def parse_row(field_names, row):
    """Parses the table's tbody tr row, row, for the Element data.

    The row should be <tbody><tr>...</tr></tbody>
    Which leaves the following:
        <td><para>Value 1</para></td>
        <td><para>Value 2</para></td>
        etc...
    Some rows are
        <td><para><emphasis>Value 1</emphasis></para></td>
        <td><para><emphasis>Value 2</emphasis></para></td>
        etc...
    There are also some without text values
        <td><para/></td>
        <td><para><emphasis/></para></td>

    Parameters
    ----------
    field_names : list of str
        The field header names
    row
        The XML for the row to parse

    Returns
    -------
    dict
        {header1 : val1, header2 : val2, ...} representing the
        information for the row.
    """
    cell_values = []
    for cell in row.iter(f"{BR}para"):
        # If we have an emphasis tag under the para tag
        value = cell.find(f"{BR}emphasis")
        if value is not None:
            # If there is a text value add it, otherwise add ""
            if value.text is not None:
                # 200b is a zero width space
                cell_values.append(value.text.strip().replace("\u200b", ""))
            else:
                cell_values.append("")

        # Otherwise just grab the para tag text
        else:
            if cell.text is not None:
                cell_values.append(cell.text.strip().replace("\u200b", ""))
            else:
                cell_values.append("")

    return {k: v for k, v in zip(field_names, cell_values)}


def parse_docbook_table(book_root, caption):
    """Parses the XML `book_root` for the table with `caption`.

    Parameters
    ----------
    book_root
        The XML book root
    caption : str
        The caption of the table to parse

    Returns
    -------
    row_attrs : list of dict
        A list of the Element dicts generated by parsing the table.
    """
    for table in book_root.iter(f"{BR}table"):
        # Find the table in book_root with caption
        if table.find(f"{BR}caption").text == caption:
            # Get the column headers
            element = table.find(f"{BR}thead").find(f"{BR}tr")
            field_names = parse_header(element)

            # Get all the Element data from the table
            return [
                parse_row(field_names, row)
                for row in table.find(f"{BR}tbody").iter(f"{BR}tr")
            ]


def setup_argparse():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a new _dicom_dict.py file from Parts 6 and 7 of the "
            "DICOM Standard"
        ),
        usage="generate_dicom_dict.py [options]"
    )

    opts = parser.add_argument_group('Options')
    opts.add_argument(
        "--local",
        help=(
            "The path to the directory containing the XML files (used instead "
            "of downloading them)"
        ),
        type=str
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
        part_06 = (local_dir / 'part06.xml').resolve(strict=True)
        part_07 = (local_dir / 'part07.xml').resolve(strict=True)
    else:
        url = "http://medical.nema.org/medical/dicom/current/source/docbook"
        url_06 = f'{url}/part06/part06.xml'
        url_07 = f'{url}/part07/part07.xml'
        print(f"Downloading '{url_06}'")
        part_06 = urllib2.urlopen(url_06)
        print(f"Downloading '{url_07}'")
        part_07 = urllib2.urlopen(url_07)
        print("Downloads complete, processing...")

    # The public and repeating group elements - Part 6
    tree = ET.parse(part_06)
    root = tree.getroot()

    # Check the version is up to date
    dcm_version = root.find('{http://docbook.org/ns/docbook}subtitle')
    dcm_version = dcm_version.text.split()[2]
    lib_version = getattr(_version, '__dicom_version__', None)
    if lib_version != dcm_version:
        print(
            "Warning: 'pydicom._version.__dicom_version__' needs to be "
            f"updated to '{dcm_version}'"
        )

    title = "Registry of DICOM"
    attrs += parse_docbook_table(root, f"{title} Data Elements")
    attrs += parse_docbook_table(root, f"{title} File Meta Elements")
    attrs += parse_docbook_table(
        root, f"{title} Directory Structuring Elements"
    )

    # Get the Command Group elements (0000,eeee) - Part 7
    tree = ET.parse(part_07)
    root = tree.getroot()
    command_attrs = parse_docbook_table(root, "Command Fields")
    for attr in command_attrs:
        attr["Name"] = attr["Message Field"]
        attr["Retired"] = ""

    retired_command_attrs = parse_docbook_table(root, "Retired Command Fields")
    for attr in retired_command_attrs:
        attr["Name"] = attr["Message Field"]
        attr["Retired"] = "Retired"

    attrs += command_attrs
    attrs += retired_command_attrs

    # Create the dictionary
    attrs = sorted(attrs, key=lambda x: x["Tag"])

    main_attributes = []
    mask_attributes = []

    for attr in attrs:
        group, elem = attr['Tag'][1:-1].split(",")

        # e.g. (FFFE,E000)
        if attr['VR'] == 'See Note':
            attr['VR'] = 'NONE'

        # e.g. (0018,1153), (0018,8150) and (0018,8151)
        # SyntaxError without encoding statement
        # replace micro symbol
        attr["Name"] = attr["Name"].replace("µ", "u")

        # some new tags don't have the retired entry (2019)
        if 'Retired' not in attr:
            attr['Retired'] = ''
        # e.g. (0014,0023) and (0018,9445)
        elif attr['Retired'] in ['RET', 'RET - See Note']:
            attr['Retired'] = 'Retired'
        # since 2019 the year is added, e.g. RET(2007)
        elif attr['Retired'].startswith('RET ('):
            attr['Retired'] = 'Retired'
        # e.g. (0008,0102), (0014,0025), (0040, A170)
        elif attr['Retired'] in ['DICOS', 'DICONDE', 'See Note']:
            attr['Retired'] = ''

        # e.g. (0028,1200)
        attr['VM'] = attr['VM'].split(' or ')[0]

        # If blank then add dummy vals
        # e.g. (0018,9445) and (0028,0020)
        if attr['VR'] == '' and attr['VM'] == '':
            attr['VR'] = 'OB'
            attr['VM'] = '1'
            attr['Name'] = 'Retired-blank'

        # handle retired 'repeating group' tags
        # e.g. (50xx,eeee) or (gggg,31xx)
        if 'x' in group or 'x' in elem:
            attr["Tag"] = group + elem
            mask_attributes.append(attr)
        else:
            attr["Tag"] = f'0x{group}{elem}'
            main_attributes.append(attr)

    with open(PYDICOM_DICT_FILENAME, "w") as f:
        f.write(
            '"""DICOM data dictionary auto-generated by '
            f'{os.path.basename(__file__)}"""\n'
        )
        f.write("from typing import Dict, Tuple\n\n")
        f.write('# Each dict entry is Tag: (VR, VM, Name, Retired, Keyword)')
        write_dict(f, MAIN_DICT_NAME, main_attributes, tag_is_string=False)
        write_dict(f, MASK_DICT_NAME, mask_attributes, tag_is_string=True)

    nr_tags = len(main_attributes) + len(mask_attributes)
    print(f"Processing completed, wrote {nr_tags} tags")

    print("Checking that all VRs are supported...")
    for attr in itertools.chain(main_attributes, mask_attributes):
        vr = attr['VR']
        tag = attr['Tag']
        try:
            # (fffe,e000), (fffe,e00d) and (fffe,e0dd) have no VR
            assert vr in converters or vr == 'NONE'
        except AssertionError:
            print(f"Warning: the VR '{vr}' for tag {tag} is not implemented")

    print("VR checks complete")
