# UIDs.py
"""Dicom Unique identifiers"""
#
# Copyright 2004, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

ExplicitVRLittleEndian = '1.2.840.10008.1.2.1'
ImplicitVRLittleEndian = '1.2.840.10008.1.2'
DeflatedExplicitVRLittleEndian = '1.2.840.10008.1.2.1.99'
ExplicitVRBigEndian = '1.2.840.10008.1.2.2'

# Dictionary of the common Media Storage SOP Class UIDs
# I typed in part of the table B.5-1 in Dicom Standard part 4. (PS 3.4-2003 p21)
base = '1.2.840.10008.5.1.4.1.1' # note not all SOP Class UIDS start with all this

from _UID_dict import UID_dictionary

# XXX should be removed. No longer needed after move to full UID_dictionary
SOP_Class_UIDs = {
    'CR Image'            : base + '.1',
    'CT Image'            : base + '.2',
    'US Multi-frame Image' :base + '.3.1',
    'MR Image'            : base + '.4',
    'Enhanced MR Image'    :base + '.4.1',
    'MR Spectroscopy Image': base + '.4.2',
    'US Image'            : base + '.6.1',
    'Secondary Capture Image': base + '.7',
    'Stand-alone Curve'    :base + '.9',
    'X-ray Angio Image'    :base + '.12.1',
    'X-ray Fluoro Image'   :base + '.12.2',
    'Raw Data'            : base + '.66',
    'NucMed Image'        : base + '.20',
    'PET Image'           : base + '.128',
    'RT Image'                    : base + '.481.1',
    'RT Dose'                     : base + '.481.2',
    'RT Structure Set'            : base + '.481.3',
    'RT Beams Treatment Record'   : base + '.481.4',
    'RT Plan'                     : base + '.481.5',    
    'RT Brachy Treatment Record'  : base + '.481.6',
    'RT Treatment Summary Record' : base + '.481.7',
    }

SOP_Names = dict([(uid,name) for name,uid in SOP_Class_UIDs.items()])

def SOP_name(uid):
    return SOP_Names.get(uid, "Unknown SOP Class")

def SOP_Class_UID(name):
    return SOP_Class_UIDs.get(name, "")

# Many thanks to the Medical Connections for offering free valid UIDs (http://www.medicalconnections.co.uk/FreeUID.html)
# Their service was used to obtain the following root UID for pydicom:
root = '1.2.826.0.1.3680043.8.498.'
pydicom_UIDs = {
    root + '1': 'ImplementationClassUID',
    
    }
    