import pytest

from pydicom.sr.codedict import codes
from pydicom.sr.coding import Code


class TestCodeDict:
    def test_dcm_1(self):
        assert codes.DCM.Modality == Code(
            value="121139", scheme_designator="DCM", meaning="Modality"
        )

    def test_dcm_2(self):
        assert codes.DCM.ProcedureReported == Code(
            value="121058",
            scheme_designator="DCM",
            meaning="Procedure Reported",
        )

    def test_dcm_3(self):
        assert codes.DCM.ImagingStartDatetime == Code(
            value="122712",
            scheme_designator="DCM",
            meaning="Imaging Start DateTime",
        )

    def test_sct_1(self):
        assert codes.SCT._1SigmaLowerValueOfPopulation == Code(
            value="371919006",
            scheme_designator="SCT",
            meaning="1 Sigma Lower Value of Populuation",
        )

    def test_sct_2(self):
        assert codes.SCT.FindingSite == Code(
            value="363698007", scheme_designator="SCT", meaning="Finding Site"
        )

    def test_cid250(self):
        assert codes.cid250.Positive == Code(
            value="10828004", scheme_designator="SCT", meaning="Positive"
        )

    def test_cid300(self):
        assert codes.cid300.NickelCobaltChromium == Code(
            value="261249004",
            scheme_designator="SCT",
            meaning="Nickel cobalt chromium",
        )

    def test_cid301(self):
        assert codes.cid301.mgcm3 == Code(
            value="mg/cm3", scheme_designator="UCUM", meaning="mg/cm^3"
        )

    def test_cid402(self):
        assert codes.cid402.DestinationRoleID == Code(
            value="110152",
            scheme_designator="DCM",
            meaning="Destination Role ID",
        )

    def test_cid405(self):
        assert codes.cid405.MultiMediaCard == Code(
            value="110035", scheme_designator="DCM", meaning="Multi-media Card"
        )

    def test_cid610(self):
        assert codes.cid610.ReverseOsmosisPurifiedHclAcidifiedWater == Code(
            value="127291",
            scheme_designator="DCM",
            meaning="Reverse osmosis purified, HCl acidified water",
        )

    def test_cid612(self):
        assert codes.cid612.MonitoredAnesthesiaCareMAC == Code(
            value="398239001",
            scheme_designator="SCT",
            meaning="Monitored Anesthesia Care (MAC)",
        )

    def test_cid622(self):
        assert codes.cid622.NeuromuscularBlockingNMBNonDepolarizing == Code(
            value="372790002",
            scheme_designator="SCT",
            meaning="NeuroMuscular Blocking (NMB) - non depolarizing",
        )

    def test_cid630(self):
        assert codes.cid630.LidocainePrilocaine == Code(
            value="346553009",
            scheme_designator="SCT",
            meaning="Lidocaine + Prilocaine",
        )

    def test_cid643(self):
        assert codes.cid643._6Hydroxydopamine == Code(
            value="4624",
            scheme_designator="PUBCHEM_CID",
            meaning="6-Hydroxydopamine",
        )

    def test_cid646(self):
        assert codes.cid646.SPECTCTOfWholeBody == Code(
            value="127902",
            scheme_designator="DCM",
            meaning="SPECT CT of Whole Body",
        )

    def test_cid1003(self):
        assert codes.cid1003.LevelOfT11T12IntervertebralDisc == Code(
            value="243918001",
            scheme_designator="SCT",
            meaning="Level of T11/T12 intervertebral disc",
        )

    def test_cid3000(self):
        assert codes.cid3000.OperatorNarrative == Code(
            value="109111",
            scheme_designator="DCM",
            meaning="Operator's Narrative",
        )

    def test_cid3001_1(self):
        assert codes.cid3001.Avr == Code(
            value="2:65", scheme_designator="MDC", meaning="-aVR"
        )

    def test_cid3001_2(self):
        assert codes.cid3001.NegativeLowRightScapulaLead == Code(
            value="2:124",
            scheme_designator="MDC",
            meaning="negativ: low right scapula Lead",
        )

    def test_cid3107(self):
        assert codes.cid3107._13Nitrogen == Code(
            value="21576001", scheme_designator="SCT", meaning="^13^Nitrogen"
        )

    def test_cid3111(self):
        assert codes.cid3111.Tc99mTetrofosmin == Code(
            value="404707004",
            scheme_designator="SCT",
            meaning="Tc-99m tetrofosmin",
        )

    def test_cid3263(self):
        meaning = (
            "12-lead from EASI leads (ES, AS, AI)"
            " by Dower/EASI transformation"
        )
        assert (
            codes.cid3263._12LeadFromEASILeadsESASAIByDowerEASITransformation
            == Code(
                value="10:11284", scheme_designator="MDC", meaning=meaning,
            )
        )

    def test_cid3335(self):
        assert codes.cid3335.PWaveSecondDeflectionInPWave == Code(
            value="10:320",
            scheme_designator="MDC",
            meaning="P' wave (second deflection in P wave)",
        )

    def test_contained(self):
        c = Code("24028007", "SCT", "Right")
        assert c in codes.cid244

    def test_not_contained(self):
        c = Code("130290", "DCM", "Median")
        assert c not in codes.cid244
