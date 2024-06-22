#!/usr/bin/env python
# Encoding required to deal with 'micro' character
"""Script for auto-generating DICOM SR context groups from FHIR JSON value set
resources.


"""

import argparse
from io import BytesIO
import json
from keyword import iskeyword
import ftplib
import logging
import os
from pathlib import Path
import re
from pprint import pprint
import urllib.request as urllib_request
from xml.etree import ElementTree as ET
import zipfile


LOGGER = logging.getLogger(__name__)


PYDICOM_SRC = Path(__file__).parent.parent.parent / "src" / "pydicom"
SR_DIRECTORY = PYDICOM_SRC / "sr"

FTP_HOST = "medical.nema.org"
FTP_PATH = "medical/dicom/resources/valuesets/"
FTP_FHIR_REGEX = re.compile(
    r".+/DICOM_ValueSets(?P<version>[0-9]{4}[a-z])_release_fhir_json_[0-9]+.zip"
)
CID_ID_REGEX = re.compile("^dicom-cid-([0-9]+)-[a-zA-Z]+")

P16_TO1_URL = (
    "http://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_O.html"
)
P16_TD1_URL = (
    "http://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_D.html"
)


# Example excerpt fhir JSON for reference
"""
    "resourceType":"ValueSet",
    "id":"dicom-cid-10-InterventionalDrug",
    ...
    "name":"InterventionalDrug",
    ...
    "compose":{
        "include":[
            {
                "system":"http://dicom.nema.org/resources/ontology/DCM",
                "concept":[
                    {
                        "code":"130290",
                        "display":"Median"
                    }
                ]
            },
            {
                "system":"http://snomed.info/sct",
                "concept":[
                    {
                        "code":"387362001",
                        "display":"Epinephrine"
                    },
                ], ...
            }, ...
        ],
"""
# The list of scheme designators is not complete.
# For full list see table 8-1 in part 3.16 chapter 8:
# http://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_8.html#table_8-1
FHIR_SYSTEM_TO_DICOM_SCHEME_DESIGNATOR = {
    "http://snomed.info/sct": "SCT",
    "http://dicom.nema.org/resources/ontology/DCM": "DCM",
    "http://loinc.org": "LN",
    "http://www.radlex.org": "RADLEX",
    "http://sig.biostr.washington.edu/projects/fm/AboutFM.html": "FMA",
    "http://www.nlm.nih.gov/mesh/meshhome.html": "MSH",
    "http://ncit.nci.nih.gov": "NCIt",
    "http://unitsofmeasure.org": "UCUM",
    "http://hl7.org/fhir/sid/ndc": "NDC",
    "urn:iso:std:iso:11073:10101": "MDC",
    "doi:10.1016/S0735-1097(99)00126-6": "BARI",
    "http://www.nlm.nih.gov/research/umls": "UMLS",
    "http://pubchem.ncbi.nlm.nih.gov": "PUBCHEM_CID",
    "http://braininfo.rprc.washington.edu/aboutBrainInfo.aspx#NeuroNames": "NEU",
    "http://www.itis.gov": "ITIS_TSN",
    "http://arxiv.org/abs/1612.07003": "IBSI",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RXNORM",
    "http://hl7.org/fhir/sid/icd-10": "I10",
}

DOC_LINES = [
    f"# Auto-generated by {os.path.basename(__file__)}.\n",
    "# -*- coding: utf-8 -*-\n",
    "\n",
]
KEYWORD_FIXES = {
    # scheme: {code: keyword}
    "SCT": {
        "399136008": "LeftPosteriorObliqueEmissiveProjection",  # CIDs [26], [501]
        "399159002": "LateroMedialObliqueEmissiveProjection",  # CIDs [26], [501]
        "399089007": "ObliqueAxialEmissiveProjection",  # CIDs [26], [501]
        "399075002": "RightPosteriorObliqueEmissiveProjection",  # CIDs [26], [501]
        "399061009": "AxialProjection",  # CIDs [26], [501]
        "399074003": "LeftAnteriorObliqueEmissiveProjection",  # CIDs [26], [501]
        "399182000": "ObliqueProjection",  # CIDs [26], [501]
        "399108003": "RightAnteriorObliqueEmissiveProjection",  # CIDs [26], [501]
        "399273000": "SagittalObliqueAxisEmissiveProjection",  # CIDs [26], [501]
        "399300004": "LateralMedialEmissiveProjection",  # CIDs [26], [501]
        "399012007": "MedialLateralEmissiveProjection",  # CIDs [26], [501]
        "399268006": "MedioLateralObliqueEmissiveProjection",  # CIDs [26], [501]
        "399067008": "LateralProjection",  # CIDs [2, ...], [501]
        "32672002": "StructureOfDescendingThoracicAorta",  # [4, ...], [3827, ...]
        "118378005": "PacemakerPulseGenerator",  # CIDs [1000, ...], [6040, ...]
        "468115008": "Armrest",  # CIDs [7151], [7151]
        "430757002": "PulmonaryVeinGreatVessel",  # CIDs [4, ...], [3827, ...]
        "71836000": "Nasopharyngeal",  # CIDs [4, ...], [7601, 8134]
        "118645006": "BoneStructureOfPelvis",  # CIDs [4, ...], [7304, ...]
        "243898001": "AnatomicalReferencePlane",  # CIDs 1217253001 [4, ...], 243898001 [7304, ...]
        "3138006": "BoneTissue",  # CIDs [645, ...], [6202, ...]
        "399220000": "TransverseBodyPosition",
        "62824007": "Transverse",
        "768763008": "GadoliniumContainingProduct",  # CIDs [12], [13]
        "62413002": "RadiusBone",  # CIDs [218, ...], [7304, ...]
        "91727004": "MuscleTissue",  # CIDs [6202, ...], [7151, ...]
        "164854000": "ECGNormal",  # CIDs [222, ...], [3230]
        "55603005": "AdiposeTissue",  # CIDs [218, ...], [7151, ...]
        "399366008": "ObliqueBodyPosition",  # CIDs [6, ...], [21]
        "44808001": "ConductionDisorderOfTheHeart",  # CIDs [3201, ...], [3700]
        "81839001": "AnticoagulantAgent",  # CIDs [10], [621]
        "30492008": "DiureticAgent",  # CIDs [10], [621]
        "372681003": "HaemostaticAgent",  # CIDs [10], [621]
        "372806008": "HistomineReceptorAntagonist",  # CIDs [10], [621]
        "82573000": "LidocaineContainingProduct",  # CIDs [10], [623]
        "373148008": "ThrombolyticAgentContraindicated",  # CIDs [3740], [3741]
        "44241007": "HeartValveStenosis",  # CIDs [3711], [3810]
        "733020007": "SyringeUnit",  # CIDs [68], [69]
        "37058002": "ForeignBodyGiantCellGranuloma",  # CIDs [6030, ...], [6054]
        "119406000": "ThalamusPart",  # CIDs [7140], [7151, ...]
        "19695001": "HypochondriacRegion",  # CIDs [4, ...], [5]
        "129759000": "VascularCalcificationRadiographicFinding",  # CIDs [3491, ...], [6010]
        "442726008": "FindingOfDifferenceInLocation",  # CIDs [], []
        "442714003": "FindingOfDifferenceInSize",  # CIDs [], []
        "91747007": "LumenOfBloodVessel",  # CIDs [5], [7156]
        "33252009": "BetaBlockerContainingProduct",  # CIDs [3760], [621]
        "48698004": "CalciumChannelBlockerContainingProduct",  # CIDs [3760], [621]
        "118927008": "ThromboticDisorder",  # CIDs [3815], [3805]
        "354064008": "MethylthioniniumChlorideContainingProduct",  # CIDs [4200], [10]
        "771928002": "AtropineInOcularDoseForm",  # CIDs [4208], [10]
        "399368009": "MedioLateralObliqueProjection",  # CIDs [7302], [4014]
        "422996004": "WolfProjection",  # CIDs [7480], [4012]
        "122456005": "LaserDevice",  # CIDs [8125], [8, ...]
        "441950002": "HistopathologyDepartment",  # CIDs [8131], [7030]
        "13576009": "FetalUmbilicalVein",  # CIDs [12140], [4, ...]
        "439470001": "ArteriovenousFistulaDisorder",  # CIDs [12293], [3810]
        "88619007": "VascularResistanceFunction",  # CIDs [12304], [3641]
        "118538004": "MassQuantity",  # CIDs [12304], [6102, ...]
    },
    "MDC": {
        "2:98": "ChestLeadSymmetricPlacement",  # CID 3001
        "3:3146": "Grade1AVBlock",  # CID 3415, 3038
        "3:3148": "Grade2AVBlock",  # CID 3415, 3038
        "7:756": "MusculusAbductorDigitiMinimiHand",  # CID 3031
        "7:757": "MusculusAbductorDigitiMinimiHandLeft",  # CID 3031
        "7:758": "MusculusAbductorDigitiMinimiHandRight",  # CID 3031
        "7:760": "MusculusFlexorDigitiMinimiBrevisHand",  # CID 3031
        "7:761": "MusculusFlexorDigitiMinimiBrevisHandLeft",  # CID 3031
        "7:762": "MusculusFlexorDigitiMinimiBrevisHandRight",  # CID 3031
        "7:968": "MusculusAdductorHallucis",  # CID 3031
        "7:969": "MusculusAdductorHallucisLeft",  # CID 3031
        "7:970": "MusculusAdductorHallucisRight",  # CID 3031
        "7:972": "MusculusAbductorDigitiMinimiFoot",  # CID 3031
        "7:973": "MusculusAbductorDigitiMinimiFootLeft",  # CID 3031
        "7:974": "MusculusAbductorDigitiMinimiFootRight",  # CID 3031
        "7:976": "MusculusFlexorDigitiMinimiBrevisFoot",  # CID 3031
        "7:977": "MusculusFlexorDigitiMinimiBrevisFootLeft",  # CID 3031
        "7:978": "MusculusFlexorDigitiMinimiBrevisFootRight",  # CID 3031
        "10:8624": "PreExcitationBeat",  # CID 3415, 3335
        "10:8640": "WolfParkinsonWhiteSyndromeLessSpecific",  # CID 3415, 3335
        "10:8656": "WolfParkinsonTypeAQRSPositiveInV1V2",  # CID 3415, 3335
        "10:8672": "WolfParkinsonTypeBQRSNegativeInV1V2",  # CID 3415, 3335
        "10:8688": "LownGanongLevineSyndromeNormalQRS",  # CID 3415, 3335
        "10:9264": "SinusTachycardiaRhythm",  # CID 3415, 3038
        "10:9456": "AtrialFlutterRhythm",  # CID 3415, 3038
        "10:9472": "AtrialFibrillationRhythm",  # CID 3415, 3038
        "10:10336": "AsystoleRhythm",  # CID 3415, 3038
        "10:10352": "IrregularRhythmLowHeartRate",  # CID 3415, 3038
        "10:10432": "BrachycardiaAny",  # CID 3415, 3038
    },
    "DCM": {
        "109018": "BeatsDetectedAccepted",  # CID 3337
        "109019": "BeatsDetectedRejected",  # CID 3337
        "109045": "StartOfAtrialContraction",  # CID 3339
        "109046": "StartOfAtrialContractionSubsequent",  # CID 3339
        "110818": "T2StarWeightedDynamicContrastEnhancedMRSignalIntensity",  # CID 218
        "110806": "T2StarWeightedMRSignalIntensity",  # CID 218
        "111487": "MammographicCrosshair",  # CID 6058
        "111488": "MammographicGrid",  # CID 6058
        "112300": "APPlus45",  # CID 7303
        "112301": "APMinus45",  # CID 7303
        "112702": "SlideMicroscopyPathologyImaging",  # CID 8131, 29, 30, 33
        "113064": "T2Star",  # CID 218
        "113076": "SegmentationImageDerivation",  # CID 7203, 32, 33
        "113806": "StationaryAcquisitionCT",  # CID 10013, 10002
        "113951": "FilmDetectorType",  # CID 10030, 405
        "126395": "R2Star",  # CID 218
        "128186": "RTPrescriptionResultForRTTreatmentPlanning",  # CID 9510, 7010, 7023
        "128304": "OCTAOneSidedRatioLesser",  # CID 4270
        "128305": "OCTAOneSidedRatioGreater",  # CID 4270
    },
    "RADLEX": {
        "RID50296": "PIRADS1VeryLowLesion",  # CID 6328, 6324, 6325
        "RID50297": "PIRADS2LowLesion",  # CID 6328 6324 6325
        "RID50298": "PIRADS3IntermediateLesion",  # CID 6328, 6324, 6325
        "RID50299": "PIRADS4HighLesion",  # CID 6328, 6324, 6325
        "RID50300": "PIRADS5VeryHighLesion",  # CID 6328, 6324, 6325
        "RID50320": "PIRADS_DCENegative",  # CID 6332
        "RID50321": "PIRADS_DCEPositive",  # CID 6332
        "RID50323": "PIRADSXInadequateOrAbsentLesion",  # CID 6328, 6324, 6325
    },
    "UCUM": {
        "/cm": "PerCentimeter",  # CIDs 83, 84, 7181
        "cm": "Centimeter",  # CID 7181
        "cm2": "SquareCentimeter",  # CID 7181
        "/s": "PerSecond",
        "s": "Second",
        "mgcm3": "MilligramsPerCubicCentimeter",
        "mmHg": "MillimetersHg",
        "mm[Hg]": "MillimetersHg",
        "kPa": "Kilopascal",
        "mm": "Millimeter",
        "mm/s": "MillimeterPerSecond",
        "mg/ml": "MilligramsPerMilliliter",
        "mg/cm3": "MilligramsPerCubicCentimeter",
        "m": "Meter",
        "um": "Micrometer",
        "um2/s": "SquareMicrometerPerSecond",
        "cm2/ml": "SquareCentimeterPerMilliliter",
        "mm2/s": "SquareMillimeterPerSecond",
        "um2/ms": "SquareMicrometerPerMillisecond",
        "umol/min/ml": "MicromolePerMinutePerMilliliter",
        "ml/g": "MilliliterPerGram",
        "ml/min/g": "MilliliterPerMinutePerGram",
        "umol/ml": "MicromolePerMilliliter",
        "mg/min/ml": "MilligramsPerMinutePerMilliliter",
        "Bq/ml": "BecquerelsPerMilliliter",
        "Monitor Units/s": "MonitorUnitsPerSecond",
        "Gy/s": "GrayPerSecond",
        "rad/s": "RadiansPerSecond",
        "uV": "Microvolt",
        "mV": "Millivolt",
        "dB[mV]": "DecibelsMillivolt",
        "dB[uV]": "DecibelsMicrovolt",
        "km/h": "KilometersPerHour",
        "[mi_i]/h": "MilesPerHour",
        "[PRU]/m2": "PRUPerSquareMeter",
        "/min": "PerMinute",
        "cm/s": "CentimeterPerSecond",
        "10-6.mm2/s": "_10EMinus6SquareMillimetersPerSecond",
        "MeV": "MegaElectronVolt",
        "{MU}/s": "MonitorUnitsPerSecond",
        "mmol/kg{WetWeight}": "MillimolesPerKilogramWetWeight",
    },
    "LN": {
        "18015-8": "AorticRootAnnuloAorticJunctionDiameter",  # CID 12300, 12212
        "79967-6": "InferiorVenaCavaDiameterAtEndExpiration",  # CIDs 12300, 12215
        "79987-4": "LeftPulmonaryArteryDiameterAtEndSystole",  # CID 12300, 12210
        "80009-4": "LeftVentricularInternalDiastolicDimensionByUSMModeBSA",  # CID 12300
        "80010-2": "LeftVentricularInternalDiastolicDimensionByUS2DBSA",  # CID 12300
        "80013-6": "LeftVentricularInternalSystolicDimensionByUSMModeBSA",  # CID 12300
        "80014-4": "LeftVentricularInternalSystolicDimensionByUS2DBSA",  # CID 12300
        "80031-8": "LeftVentricularPosteriorWallDiastolicThicknessByUSMMode",  # CID 12300
        "80032-6": "LeftVentricularPosteriorWallDiastolicThicknessByUS2D",  # CID 12300
        "80033-4": "LeftVentricularPosteriorWallSystolicThicknessByUSMMode",  # CID 12300
        "80034-2": "LeftVentricularPosteriorWallSystolicThicknessByUS2D",  # CID 12300
        "80049-0": "MainPulmonaryArteryDiameterAtEndSystole",  # CID 12300, 12210
        "80079-7": "RightPulmonaryArteryDiameterAtEndSystole",  # CID 12300, 12210
    },
}


def camel_case(s):
    leave_alone = (
        "mm",
        "cm",
        "km",
        "um",
        "ms",  #  'us'?-doesn't seem to be there
        "ml",
        "mg",
        "kg",
    )  # ... probably need others
    return "".join(
        word.capitalize() if word != word.upper() and word not in leave_alone else word
        for word in re.split(r"\W", s, flags=re.UNICODE)
        if word.isalnum()
    )


def keyword_from_meaning(name):
    """Return a camel case valid python identifier"""
    # Try to adhere to keyword scheme in DICOM (CP850)
    # singular/plural alternative forms are made plural
    #     e.g., “Physician(s) of Record” becomes “PhysiciansOfRecord”
    kw = name.replace("(s)", "s")

    # “Patient’s Name” -> “PatientName”
    # “Operators’ Name” -> “OperatorsName”
    kw = kw.replace("’s ", " ")
    kw = kw.replace("'s ", " ")
    kw = kw.replace("s’ ", "s ")
    kw = kw.replace("s' ", "s ")

    # Mathematical symbols
    kw = kw.replace("%", " Percent ")
    kw = kw.replace(">", " Greater Than ")
    kw = kw.replace("=", " Equals ")
    kw = kw.replace("<", " Lesser Than ")

    kw = kw.replace("_", " ")

    kw = re.sub(r"([0-9]+)\.([0-9]+)", "\\1 Point \\2", kw)
    kw = re.sub(r"\s([0-9.]+)-([0-9.]+)\s", " \\1 To \\2 ", kw)

    kw = re.sub(r"([0-9]+)day", "\\1 Day", kw)
    kw = re.sub(r"([0-9]+)y", "\\1 Years", kw)

    # Remove category modifiers, such as "(specimen)", "(procedure)",
    # "(body structure)", etc.
    kw = re.sub(r"^(.+) \([a-z ]+\)$", "\\1", kw)

    kw = camel_case(kw.strip())

    # Python variables must not begin with a number.
    if re.match(r"[0-9]", kw):
        kw = "_" + kw

    if kw == "None":
        kw = "None_"

    if not kw.isidentifier() or iskeyword(kw):
        raise ValueError(f"Invalid keyword '{kw}' generated from '{name}'")

    return kw


def setup_logger(debug_level=logging.INFO) -> None:
    """Setup the logging."""
    LOGGER = logging.getLogger(__name__)
    # Ensure only have one StreamHandler
    LOGGER.handlers = []
    handler = logging.StreamHandler()
    LOGGER.setLevel(debug_level)
    formatter = logging.Formatter("%(levelname).1s: %(message)s")
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)


def download_fhir_value_sets(local_dir: Path) -> None | str:
    """Log into the DICOM FTP server and download the zip file containing the
    FHIR JSON files.

    Parameters
    ----------
    local_dir : pathlib.Path
        The directory where the zip file will be written to, as
        ``local_dir/version/*.zip``.

    Returns
    -------
    str | None
        If the download failed then returns ``None``, otherwise returns the
        DICOM version as :class:`str`.
    """
    LOGGER.debug(f"  Logging into FTP server: {FTP_HOST}")
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login("anonymous")

    version = None

    try:
        LOGGER.debug(f"  Searching contents of '{FTP_PATH}' for JSON ZIP file")
        for remote_path in ftp.nlst(FTP_PATH):
            LOGGER.debug(f"    {remote_path}")
            match = FTP_FHIR_REGEX.match(remote_path)
            if match:
                LOGGER.debug("  Found FHIR JSON ZIP file, downloading...")
                with BytesIO() as fp:
                    ftp.retrbinary(f"RETR {remote_path}", fp.write)
                    data = fp.getvalue()

                version = match.group("version")
                (local_dir / version).mkdir(parents=True, exist_ok=True)
                local_path = local_dir / version / Path(remote_path).name

                LOGGER.debug(f"    Writing data to {local_path}")
                with open(local_path, "wb") as f:
                    f.write(data)

                break
    finally:
        ftp.quit()

    return version


def extract_cid_files(path: Path, version: str, cid_folder="CIDs") -> None:
    """Extract the JSON files in the downloaded ZIP file to ``path / cid_folder``.

    Parameters
    ----------
    path : pathlib.Path
        The base directory.
    version : str
        The name of the version subdirectory containing the ZIP file.
    cid_folder : str, optional
        The name of the subdirectory the CID files will be extracted to, default
        ``CIDs``.
    """
    files = list((path / version).glob("*.zip"))
    if not files:
        raise ValueError(f"No zip files found in {path / version}")

    if len(files) > 1:
        raise ValueError(f"Multiple zip files found in {path / version}")

    # Create the output directory (if it doesn't already exist)
    cid_dir = path / cid_folder
    cid_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.debug(f"  Extracting FHIR JSON files to {cid_dir}")
    with zipfile.ZipFile(files[0]) as z:
        # Forcibly flatten the ZIP contents into the `cid_folder`
        for zip_path in (Path(x) for x in z.namelist()):
            with open(cid_dir / zip_path.name, "wb") as f:
                f.write(z.read(str(zip_path)))


def extract_table_data(
    path: Path, version: str, ext: tuple[str, ...] = (".htm", ".html")
) -> list[bytes]:
    """Extract the table data from the downloaded HTML files.

    Parameters
    ----------
    path : pathlib.Path
        The base directory.
    version : str
        The name of the version subdirectory containing the HTML files.
    ext : str, optional
        The extension of the downloaded HTML files.
    """
    files = [p for p in (path / version).iterdir() if p.suffix in ext]
    if len(files) != 2:
        raise ValueError(
            f"The Part 16, Chapter D and O HTML files were not found in {path / version}"
        )

    # Chapter D
    # <html xmlns="http://www.w3.org/1999/xhtml">
    #    <head>
    #       <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    #       <title>D DICOM Controlled Terminology Definitions (Normative)</title>

    # Chapter O
    # <html xmlns="http://www.w3.org/1999/xhtml">
    #    <head>
    #       <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    #       <title>O SNOMED Concept ID to SNOMED ID Mapping</title>

    data = [None, None]

    for html_file in files:
        with open(html_file, "rb") as f:
            file_data = f.read()
            root = ET.fromstring(file_data, parser=ET.XMLParser(encoding="utf-8"))
            for element in root.iter():
                if element.tag.endswith("title"):
                    title = element.text
                    if title.startswith("D"):
                        data[0] = file_data
                    elif title.startswith("O"):
                        data[1] = file_data

                    break

    if None in data:
        raise ValueError("One or both HTML files do not contain the expected data")

    return data


def _get_text(element) -> str:
    return "".join(element.itertext()).strip()


def get_table_o1(data: bytes) -> list[tuple[str, str, str]]:
    """Return a list of SNOMED-CT to SNOMED RT mappings.

    Returns
    -------
    list[tuple[str, str, str]]
        A list of (SCT, SRT, SNOMED Fully Specified Name) generated from
        Table O-1 in Part 16 of the DICOM Standard.
    """
    LOGGER.info("Download and process SNOMED mappings from Part 16, Table O-1")
    root = ET.fromstring(data, parser=ET.XMLParser(encoding="utf-8"))
    namespaces = {"w3": root.tag.split("}")[0].strip("{")}
    body = root.find("w3:body", namespaces=namespaces)
    table = body.findall(".//w3:tbody", namespaces=namespaces)[0]
    rows = table.findall("./w3:tr", namespaces=namespaces)
    data = []
    for row in rows:
        data.append(
            (
                _get_text(row[0].findall(".//w3:p", namespaces=namespaces)[-1]),
                _get_text(row[1].findall(".//w3:p", namespaces=namespaces)[0]),
                _get_text(row[2].findall(".//w3:p", namespaces=namespaces)[0]),
            )
        )

    return data


def get_table_d1(data: bytes) -> list[tuple[str, str]]:
    """Return a list of DICOM code values to code meaning mappings.

    Returns
    -------
    list[tuple[str, str]]
        A list of (Code Value, Code Meaning) generated from Table D-1 in Part
        16 of the DICOM Standard.
    """
    LOGGER.info("Processing Part 16, Table D-1")
    root = ET.fromstring(data, parser=ET.XMLParser(encoding="utf-8"))
    namespaces = {"w3": root.tag.split("}")[0].strip("{")}
    body = root.find("w3:body", namespaces=namespaces)
    table = body.findall(".//w3:tbody", namespaces=namespaces)[0]
    rows = table.findall("./w3:tr", namespaces=namespaces)
    return [
        (
            _get_text(row[0].findall(".//w3:p", namespaces=namespaces)[0]),
            _get_text(row[1].findall(".//w3:p", namespaces=namespaces)[0]),
        )
        for row in rows
    ]


def write_concepts(
    concepts: dict[str, dict[str, dict[str, tuple[str, list[int]]]]],
    cid_lists: dict[int, dict[str, list[str]]],
    name_for_cid: dict[int, str],
) -> None:
    """Write.

    Parameters
    ----------
    concepts : dict[str, dict[str, dict[str, tuple[str, list[int]]]]]
        A :class:`dict` containing the concept schemes and their contents as
        ``concepts[scheme_designator][keyword] = {code: (display, [cid, ...])}``
    cid_lists : dict[int, dict[str, list[str]]]
        The schemes and code keywords for each CID ID as
    name_for_cid : dict[int, str]
        A :class:`dict:` mapping CID IDs their name.
    """
    # Write the concepts dict
    path = SR_DIRECTORY / "_concepts_dict.py"
    LOGGER.info(f"Writing concepts to '{path}'")

    lines = DOC_LINES + [
        "# Dict with scheme designator keys; value format is:\n",
        "#   {keyword: {code1: (meaning, cid_list), code2: ...}\n",
        "#\n",
        "# Most keyword identifiers map to a single code, but not all\n",
        "\n",
    ]

    with open(path, "w", encoding="UTF8") as f:
        f.writelines(lines)
        f.write("concepts = {}\n")  # start with empty dict
        for scheme, value in concepts.items():
            f.write(f"\nconcepts['{scheme}'] = \\\n")
            pprint(value, f)

    # Write the CID dict
    path = SR_DIRECTORY / "_cid_dict.py"
    LOGGER.info(f"Writing CIDs to '{path}'")

    lines = DOC_LINES + [
        "# Dict with cid number as keys; value format is:\n",
        "#   {scheme designator: <list of keywords for current cid>\n",
        "#    scheme_designator: ...}\n",
        "\n",
    ]

    with open(path, "w", encoding="UTF8") as f:
        f.writelines(lines)
        f.write("name_for_cid = {}\n")
        f.write("cid_concepts = {}\n")
        for cid, value in cid_lists.items():
            f.write(f"\nname_for_cid[{cid}] = '{name_for_cid[cid]}'\n")
            f.write(f"cid_concepts[{cid}] = \\\n")
            pprint(value, f)


def write_snomed_mapping(snomed_codes: list[tuple[str, str, str]]) -> None:
    """Write the SNOMED-CT <-> SNOMED RT mapping dict to ``_snomed_dict.py``."""
    path = SR_DIRECTORY / "_snomed_dict.py"
    LOGGER.info(f"Writing SNOMED-CT to RT mappings to '{path}'")

    with open(path, "w", encoding="UTF8") as f:
        lines = DOC_LINES + [
            "# Dict with scheme designator keys; value format is:\n",
            "#   {concept_id1: snomed_id1, concept_id2: ...}\n",
            "# or\n",
            "#   {snomed_id1: concept_id1, snomed_id2: ...}\n",
            "\n",
        ]

        f.writelines(lines)
        f.write("mapping = {}\n")

        # Write the SCT -> SRT mapping
        f.write("\nmapping['SCT'] = {\n")
        for sct, srt, _ in snomed_codes:
            f.write(f"    '{sct}': '{srt}',\n")

        f.write("}\n")

        # Write the SRT -> SCT mapping
        f.write("\nmapping['SRT'] = {\n")
        for sct, srt, _ in snomed_codes:
            f.write(f"     '{srt}': '{sct}',\n")

        f.write("}")


def setup_argparse():
    parser = argparse.ArgumentParser(
        description=("Update the sr/ code and concepts dictionaries"),
        usage="generate_concept_dicts.py path [options]",
    )

    opts = parser.add_argument_group("Options")
    opts.add_argument(
        "path",
        help="The path to download the JSON CID files to",
        type=str,
    )
    opts.add_argument(
        "--download",
        help="Download the FHIR JSON CID files",
        action="store_true",
    )
    opts.add_argument(
        "--cid-directory",
        help="The name of the directory where the CID should be located",
        type=str,
        default="CIDs",
    )
    opts.add_argument(
        "--version",
        help="The version of the downloaded CID ZIP file",
        type=str,
    )
    opts.add_argument(
        "--debug",
        help="Set logging to debug mode",
        action="store_true",
        default=False,
    )

    return parser.parse_args()


def process_files(cid_directory: Path, snomed_mapping, dicom_mapping) -> None:
    LOGGER.info(f"Processing the CID JSON files in {cid_directory}")

    # Mapping of:
    #   Scheme: Keywords
    #       Keyword: Codes
    #           Code: (Display, [CIDs containing the code])
    # concepts[scheme_designator][name] = {code: (display, [cid])}
    concepts: dict[str, dict[str, dict[str, tuple[str, list[int]]]]] = {}

    # The schemes and code keywords for each CID ID
    cid_lists: dict[int, dict[str, list[str]]] = {}

    # Mapping of CID ID to CID name
    name_for_cid: dict[int, str] = {}

    # Mapping code <-> keyword(s)
    # codes_kw = {}
    kw_codes = {}

    cid_paths = sorted(
        cid_directory.glob("*.json"), key=lambda x: int(x.name.split("-")[3])
    )
    for path in cid_paths:
        LOGGER.debug(f"  Processing '{path.name}'")
        with open(path, "rb") as f:
            data = json.loads(f.read())

        cid = int(CID_ID_REGEX.match(data["id"]).group(1))
        name_for_cid[cid] = data["name"]

        # A mapping of scheme to a list of code keywords
        cid_concepts: dict[str, list[str]] = {}
        for group in data["compose"]["include"]:
            system = group["system"]
            try:
                scheme_designator = FHIR_SYSTEM_TO_DICOM_SCHEME_DESIGNATOR[system]
            except KeyError:
                raise NotImplementedError(
                    "The DICOM scheme designator for the following FHIR system "
                    f"has not been specified: {system}"
                )
            if scheme_designator not in concepts:
                concepts[scheme_designator] = {}

            if scheme_designator not in kw_codes:
                kw_codes[scheme_designator] = {}

            for concept in group["concept"]:
                code = concept["code"].strip()
                display = concept["display"].strip()
                try:
                    code_keyword = KEYWORD_FIXES[scheme_designator][code]
                except KeyError:
                    code_keyword = keyword_from_meaning(concept["display"])

                if not code_keyword.isidentifier() or iskeyword(code_keyword):
                    raise ValueError(
                        f"Invalid keyword '{code_keyword}' generated from '{display}'"
                    )

                # Check each keyword matches only one code in a given scheme
                codes = kw_codes[scheme_designator].setdefault(code_keyword, [])
                codes.append(code)
                if len(set(codes)) > 1:
                    previous = concepts[scheme_designator][code_keyword]
                    current = {code: (display, [cid])}
                    current.update(previous)
                    LOGGER.error(
                        f"  {scheme_designator}: keyword '{code_keyword}' is being "
                        f"used for different codes {current}"
                    )

                # If new code_keyword under this scheme, start dict of codes/cids that use that code
                if code_keyword not in concepts[scheme_designator]:
                    concepts[scheme_designator][code_keyword] = {code: (display, [cid])}
                else:
                    prior = concepts[scheme_designator][code_keyword]
                    if code in prior:
                        prior[code][1].append(cid)
                    else:
                        prior[code] = (display, [cid])

                    if prior[code][0].lower() != display.lower():
                        # Multiple 'display' values for the same code found
                        LOGGER.info(
                            f"  Found multiple 'display' values for code {code} in "
                            f"scheme {scheme_designator}: CID{cid}: '{display}', "
                            f"previously '{prior[code][0]}'"
                        )

                # Keep track of this cid referencing that code_keyword
                if scheme_designator not in cid_concepts:
                    cid_concepts[scheme_designator] = []

                # Same keyword is being used for different codes in the same scheme
                if code_keyword in cid_concepts[scheme_designator]:
                    previous = concepts[scheme_designator][code_keyword]
                    LOGGER.error(
                        f"  {scheme_designator}: keyword '{code_keyword}' is being "
                        f"used for different codes {previous}"
                    )

                cid_concepts[scheme_designator].append(code_keyword)

        cid_lists[cid] = cid_concepts

    LOGGER.debug("Applying SCT mappings to the concepts")
    scheme_designator = "SCT"
    # snomed_codes = get_table_o1()
    for code, srt_code, meaning in snomed_mapping:
        name = keyword_from_meaning(meaning)
        if name not in concepts[scheme_designator]:
            concepts[scheme_designator][name] = {code: (meaning, [])}
        else:
            prior = concepts[scheme_designator][name]
            if code not in prior:
                prior[code] = (meaning, [])

    LOGGER.debug("Applying DCM mappings to the concepts")
    scheme_designator = "DCM"
    for code, meaning in dicom_mapping:
        # 2023b has row with ellipses after 113270 for some reason
        if code == "..." or meaning == "...":
            continue

        name = keyword_from_meaning(meaning)
        if name not in concepts[scheme_designator]:
            concepts[scheme_designator][name] = {code: (meaning, [])}
        else:
            prior = concepts[scheme_designator][name]
            if code not in prior:
                prior[code] = (meaning, [])

    for scheme in kw_codes:
        for codes in kw_codes[scheme].values():
            if len(set(codes)) != 1:
                raise ValueError(
                    "Each keyword must correspond to one and only one code"
                )

    return concepts, cid_lists, name_for_cid


if __name__ == "__main__":
    args = setup_argparse()
    level = logging.DEBUG if args.debug else logging.ERROR
    setup_logger(level)

    path = Path(args.path).resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise ValueError("'path' must be a path to a directory")

    if args.download:
        # Download the ZIP file containing the JSON data
        LOGGER.info(f"Downloading CID files to {path / args.cid_directory}")
        version = download_fhir_value_sets(path)
        if version:
            extract_cid_files(path, version, args.cid_directory)
        else:
            LOGGER.error("Failed to download the CID files")

        LOGGER.info(f"Downloading Part 16, Chapters D and O to {path / version}")
        snomed_data = urllib_request.urlopen(P16_TO1_URL).read()
        with open(path / version / "Table_O1.html", "wb") as f:
            f.write(snomed_data)

        dicom_data = urllib_request.urlopen(P16_TD1_URL).read()
        with open(path / version / "Table_D1.html", "wb") as f:
            f.write(dicom_data)

    elif args.version:
        # Use the already downloaded ZIP file
        extract_cid_files(path, args.version, args.cid_directory)
        # Parse the already downloaded HTM files
        dicom_data, snomed_data = extract_table_data(path, args.version)

    # Process the data files
    snomed_mapping = get_table_o1(snomed_data)
    dicom_mapping = get_table_d1(dicom_data)
    concepts, cid_lists, name_for_cid = process_files(
        path / args.cid_directory, snomed_mapping, dicom_mapping
    )

    # Write the results
    write_concepts(concepts, cid_lists, name_for_cid)
    write_snomed_mapping(snomed_mapping)
