# charset.py
"""Handle alternate character sets for character strings."""
#
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#
from __future__ import absolute_import

import logging
logger = logging.getLogger('pydicom')

# Map DICOM Specific Character Set to python equivalent
python_encoding = {
    b'': b'iso8859',           # default character set for DICOM
    b'ISO_IR 6': b'iso8859',   # alias for latin_1 too
    b'ISO_IR 100': b'latin_1',
    b'ISO 2022 IR 87': b'iso2022_jp',
    b'ISO 2022 IR 13': b'shift_jis',
    b'ISO 2022 IR 149': b'euc_kr', # needs cleanup via clean_escseq from valuerep
    b'ISO_IR 192': b'UTF8',     # from Chinese example, 2008 PS3.5 Annex J p1-4
    b'GB18030': b'GB18030',
    b'ISO_IR 126': b'iso_ir_126',  # Greek
    b'ISO_IR 127': b'iso_ir_127',  # Arab
    b'ISO_IR 138': b'iso_ir_138', # Hebrew
    b'ISO_IR 144': b'iso_ir_144', # Russian
    }

from dicom.valuerep import PersonNameUnicode, PersonName, clean_escseq

# PS3.5-2008 6.1.1 (p 18) says:
#   default is ISO-IR 6 G0, equiv to common chr set of ISO 8859 (PS3.5 6.1.2.1)
#    (0008,0005)  value 1 can *replace* the default encoding... 
#           for VRs of SH, LO, ST, LT, PN and UT (PS3.5 6.1.2.3)...
#           with a single-byte character encoding
#  if (0008,0005) is multi-valued, then value 1 (or default if blank)...
#           is used until code extension escape sequence is hit,
#          which can be at start of string, or after CR/LF, FF, or
#          in Person Name PN, after ^ or =
# NOTE also that 7.5.3 SEQUENCE INHERITANCE states that if (0008,0005) 
#       is not present in a sequence item then it is inherited from its parent.
def decode(data_element, dicom_character_set):
    """Apply the DICOM character encoding to the data element
    
    data_element -- DataElement instance containing a value to convert
    dicom_character_set -- the value of Specific Character Set (0008,0005),
                    which may be a single value,
                    a multiple value (code extension), or
                    may also be '' or None.
                    If blank or None, ISO_IR 6 is used.
    
    """
    if not dicom_character_set:
        dicom_character_set = [b'ISO_IR 6']
    have_character_set_list = True
    try:
        dicom_character_set.append # check if is list-like object
    except AttributeError:
        have_character_set_list = False

    if have_character_set_list:
        if not dicom_character_set[0]:
            dicom_character_set[0] = b"ISO_IR 6"
    else:
        dicom_character_set = [dicom_character_set]
    encodings = [python_encoding[x] for x in dicom_character_set]
    if len(encodings) == 1:
        encodings = [encodings[0]]*3
    if len(encodings) == 2:
        encodings.append(encodings[1])

    # decode the string value to unicode
    # PN is special case as may have 3 components with differenct chr sets
    if data_element.VR == b"PN": 
        # logger.warn("%s ... type: %s" %(str(data_element), type(data_element.VR)))
        if data_element.VM == 1:
            data_element.value = PersonNameUnicode(data_element.value, encodings)
        else:
            data_element.value = [PersonNameUnicode(value, encodings) 
                                    for value in data_element.value]
    if data_element.VR in [b'SH', b'LO', b'ST', b'LT', b'UT']:
        # Remove the first encoding if this is a multi-byte encoding
        if len(encodings) > 1:
            del encodings[0]
        if data_element.VM == 1:
            data_element.value = clean_escseq(
                                    data_element.value.decode(
                                    encodings[0]), encodings)
        else:
            data_element.value = [clean_escseq(
                                    value.decode(encodings[0]), encodings)
                                    for value in data_element.value]
