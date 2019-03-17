from pydicom.sr.srdict import codes

SR_SOP_CLASS_UIDS = {
    '1.2.840.10008.5.1.4.1.1.88.1',   # Text SR Storage
    '1.2.840.10008.5.1.4.1.1.88.2',   # Audio SR Storage
    '1.2.840.10008.5.1.4.1.1.88.3',   # Detail SR Storage
    '1.2.840.10008.5.1.4.1.1.88.4',   # Comprehensive SR Storage
    '1.2.840.10008.5.1.4.1.1.88.11',  # Basic Text SR Storage
    '1.2.840.10008.5.1.4.1.1.88.22',  # Enhanced SR Storage
    '1.2.840.10008.5.1.4.1.1.88.33',  # Comprehensive SR Storage
    '1.2.840.10008.5.1.4.1.1.88.34',  # Comprehensive 3D SR Storage
    '1.2.840.10008.5.1.4.1.1.88.35',  # Extensible SR Storage
    '1.2.840.10008.5.1.4.1.1.88.40',  # Procedure Log Storage
    '1.2.840.10008.5.1.4.1.1.88.50',  # Mammography CAD SR StorageSOP
    '1.2.840.10008.5.1.4.1.1.88.65',  # Chest CAD SR Storage
    '1.2.840.10008.5.1.4.1.1.88.67',  # X-Ray Radiation Dose SR Storage
    '1.2.840.10008.5.1.4.1.1.88.68',  # Radiopharmaceutical Radiation Dose SR Storage
    '1.2.840.10008.5.1.4.1.1.88.69',  # Colon CAD SR Storage
    '1.2.840.10008.5.1.4.1.1.88.70',  # Implantation Plan SR Storage
    '1.2.840.10008.5.1.4.1.1.88.71',  # Acquisition Context SR Storage
    '1.2.840.10008.5.1.4.1.1.88.72',  # Simplified Adult Echo SR Storage
    '1.2.840.10008.5.1.4.1.1.88.73',  # Patient Radiation Dose SR Storage
}
