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

import os
try:
    import urllib2 # python2
except ImportError:
    import urllib.request as urllib2 # python3
import xml.etree.ElementTree as ET

PYDICOM_DICT_FILENAME = '../../pydicom/_dicom_dict.py'
MAIN_DICT_NAME = 'DicomDictionary'
MASK_DICT_NAME = 'RepeatersDictionary'

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
    if tag_is_string:
        entry_format = """'{Tag}': ('{VR}', '{VM}', "{Name}", '{Retired}', '{Keyword}')"""
    else:
        entry_format = """{Tag}: ('{VR}', '{VM}', "{Name}", '{Retired}', '{Keyword}')"""

    fp.write("\n%s = {\n    " % dict_name)
    fp.write(",\n    ".join(entry_format.format(**attr) for attr in attributes))
    fp.write("\n}\n")

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
    br = '{http://docbook.org/ns/docbook}' # Shorthand variable

    # Find the table in book_root with caption
    for table in book_root.iter('%stable' %br):
        if table.find('%scaption' %br).text == caption:

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
                for x in header_row.iter('%sth' %br):
                    # If there is an emphasis tag under the para tag then its
                    #   text is the column header
                    if x.find('%spara' %br).find('%semphasis' %br) is not None:
                        col_label = x.find('%spara' %br).find('%semphasis' %br).text
                        field_names.append(col_label)

                    # If there isn't an emphasis tag under the para tag then it
                    #   must be the Retired header
                    else:
                        field_names.append("Retired")

                return field_names

            # Get the column headers
            field_names = parse_header(table.find('%sthead' %br).find('%str' %br))

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
                for cell in row.iter('%spara' %br):
                    # If we have an emphasis tag under the para tag
                    emph_value = cell.find('%semphasis' %br)
                    if emph_value is not None:
                        # If there is a text value add it, otherwise add ""
                        if emph_value.text is not None:
                            cell_values.append(emph_value.text.strip().replace(u"\u200b", "")) #200b is a zero width space
                        else:
                            cell_values.append("")
                    # Otherwise just grab the para tag text
                    else:
                        if cell.text is not None:
                            cell_values.append(cell.text.strip().replace(u"\u200b", ""))
                        else:
                            cell_values.append("")

                return {key : value for key, value in zip(field_names, cell_values)}

            # Get all the Element data from the table
            row_attrs = [parse_row(field_names, row) for row in \
                            table.find('%stbody' %br).iter('%str' %br)]
            return row_attrs

attrs = []

url = 'http://medical.nema.org/medical/dicom/current/source/docbook/part06/part06.xml'
response = urllib2.urlopen(url)
tree = ET.parse(response)
root = tree.getroot()

attrs += parse_docbook_table(root, "Registry of DICOM Data Elements")
attrs += parse_docbook_table(root, "Registry of DICOM File Meta Elements")
attrs += parse_docbook_table(root, "Registry of DICOM Directory Structuring Elements")

url = 'http://medical.nema.org/medical/dicom/current/source/docbook/part07/part07.xml'
response = urllib2.urlopen(url)
tree = ET.parse(response)
root = tree.getroot()

command_attrs = parse_docbook_table(root, "Command Fields") # Changed from 2013 standard
for attr in command_attrs:
    attr["Name"] = attr["Message Field"]
    attr["Retired"] = ""

retired_command_attrs = parse_docbook_table(root, "Retired Command Fields")
for attr in retired_command_attrs:
    attr["Name"] = attr["Message Field"]
    attr["Retired"] = "Retired"

attrs += command_attrs
attrs += retired_command_attrs

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
    attr["Name"] = attr["Name"].replace(u"µ", "u") # replace micro symbol

    # e.g. (0014,0023) and (0018,9445)
    if attr['Retired'] in ['RET', 'RET - See Note']:
        attr['Retired'] = 'Retired'

    # e.g. (0008,0102), (0014,0025), (0040, A170)
    if attr['Retired'] in ['DICOS', 'DICONDE', 'See Note']:
        attr['Retired'] = ''

    # e.g. (0028,1200)
    attr['VM'] = attr['VM'].replace(" or ", " ")

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
        attr["Tag"] = '0x%s%s' %(group, elem)
        main_attributes.append(attr)

py_file = open(PYDICOM_DICT_FILENAME, "w")
FILE_DOCSTRING = '"""DICOM data dictionary auto-generated by %s"""\n' \
                                                % os.path.basename(__file__)
py_file.write(FILE_DOCSTRING)
py_file.write('from __future__ import absolute_import\n\n')
py_file.write('# Each dict entry is Tag : (VR, VM, Name, Retired, Keyword)')
write_dict(py_file, MAIN_DICT_NAME, main_attributes, tag_is_string=False)
write_dict(py_file, MASK_DICT_NAME, mask_attributes, tag_is_string=True)

py_file.close()

print("Finished, wrote %d tags" %(len(main_attributes) + len(mask_attributes)))
