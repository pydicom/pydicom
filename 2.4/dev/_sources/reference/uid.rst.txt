.. _api_uid:

UID Definitions and Utilities (:mod:`pydicom.uid`)
==================================================

.. currentmodule:: pydicom.uid

Transfer Syntax UIDs
--------------------

.. autosummary::
   :toctree: generated/

   ImplicitVRLittleEndian
   ExplicitVRLittleEndian
   DeflatedExplicitVRLittleEndian
   ExplicitVRBigEndian
   JPEGBaseline8Bit
   JPEGExtended12Bit
   JPEGLosslessP14
   JPEGLosslessSV1
   JPEGLSLossless
   JPEGLSNearLossless
   JPEG2000Lossless
   JPEG2000
   JPEG2000MCLossless
   JPEG2000MC
   MPEG2MPML
   MPEG2MPHL
   MPEG4HP41
   MPEG4HP41BD
   MPEG4HP422D
   MPEG4HP423D
   MPEG4HP42STEREO
   HEVCMP51
   HEVCM10P51
   RLELossless


Transfer Syntax Lists
---------------------

.. autosummary::
   :toctree: generated/

   AllTransferSyntaxes
   JPEGTransferSyntaxes
   JPEGLSTransferSyntaxes
   JPEG2000TransferSyntaxes
   MPEGTransferSyntaxes
   RLETransferSyntaxes
   UncompressedTransferSyntaxes


UID Utilities
-------------

.. autosummary::
   :toctree: generated/

   generate_uid
   PYDICOM_ROOT_UID
   PYDICOM_IMPLEMENTATION_UID
   RE_VALID_UID
   RE_VALID_UID_PREFIX
   UID


Storage SOP Class UIDs
----------------------
.. autosummary::
   :toctree: generated/

   AcquisitionContextSRStorage
   AdvancedBlendingPresentationStateStorage
   AmbulatoryECGWaveformStorage
   ArterialPulseWaveformStorage
   AutorefractionMeasurementsStorage
   BasicStructuredDisplayStorage
   BasicTextSRStorage
   BasicVoiceAudioWaveformStorage
   BlendingSoftcopyPresentationStateStorage
   BodyPositionWaveformStorage
   BreastProjectionXRayImageStorageForPresentation
   BreastProjectionXRayImageStorageForProcessing
   BreastTomosynthesisImageStorage
   CArmPhotonElectronRadiationRecordStorage
   CArmPhotonElectronRadiationStorage
   CTDefinedProcedureProtocolStorage
   CTImageStorage
   CTPerformedProcedureProtocolStorage
   CardiacElectrophysiologyWaveformStorage
   ChestCADSRStorage
   ColonCADSRStorage
   ColorPaletteStorage
   ColorSoftcopyPresentationStateStorage
   CompositingPlanarMPRVolumetricPresentationStateStorage
   Comprehensive3DSRStorage
   ComprehensiveSRStorage
   ComputedRadiographyImageStorage
   ContentAssessmentResultsStorage
   CornealTopographyMapStorage
   DICOS2DAITStorage
   DICOS3DAITStorage
   DICOSCTImageStorage
   DICOSDigitalXRayImageStorageForPresentation
   DICOSDigitalXRayImageStorageForProcessing
   DICOSQuadrupoleResonanceStorage
   DICOSThreatDetectionReportStorage
   DeformableSpatialRegistrationStorage
   DermoscopicPhotographyImageStorage
   DigitalIntraOralXRayImageStorageForPresentation
   DigitalIntraOralXRayImageStorageForProcessing
   DigitalMammographyXRayImageStorageForPresentation
   DigitalMammographyXRayImageStorageForProcessing
   DigitalXRayImageStorageForPresentation
   DigitalXRayImageStorageForProcessing
   EddyCurrentImageStorage
   EddyCurrentMultiFrameImageStorage
   ElectromyogramWaveformStorage
   ElectrooculogramWaveformStorage
   EncapsulatedCDAStorage
   EncapsulatedMTLStorage
   EncapsulatedOBJStorage
   EncapsulatedPDFStorage
   EncapsulatedSTLStorage
   EnhancedCTImageStorage
   EnhancedMRColorImageStorage
   EnhancedMRImageStorage
   EnhancedPETImageStorage
   EnhancedSRStorage
   EnhancedUSVolumeStorage
   EnhancedXAImageStorage
   EnhancedXRFImageStorage
   EnhancedXRayRadiationDoseSRStorage
   ExtensibleSRStorage
   GeneralAudioWaveformStorage
   GeneralECGWaveformStorage
   GenericImplantTemplateStorage
   GrayscalePlanarMPRVolumetricPresentationStateStorage
   GrayscaleSoftcopyPresentationStateStorage
   HangingProtocolStorage
   HemodynamicWaveformStorage
   ImplantAssemblyTemplateStorage
   ImplantTemplateGroupStorage
   ImplantationPlanSRStorage
   IntraocularLensCalculationsStorage
   IntravascularOpticalCoherenceTomographyImageStorageForPresentation
   IntravascularOpticalCoherenceTomographyImageStorageForProcessing
   KeratometryMeasurementsStorage
   KeyObjectSelectionDocumentStorage
   LegacyConvertedEnhancedCTImageStorage
   LegacyConvertedEnhancedMRImageStorage
   LegacyConvertedEnhancedPETImageStorage
   LensometryMeasurementsStorage
   MRImageStorage
   MRSpectroscopyStorage
   MacularGridThicknessAndVolumeReportStorage
   MammographyCADSRStorage
   MediaStorageDirectoryStorage
   MicroscopyBulkSimpleAnnotationsStorage
   MultiFrameGrayscaleByteSecondaryCaptureImageStorage
   MultiFrameGrayscaleWordSecondaryCaptureImageStorage
   MultiFrameSingleBitSecondaryCaptureImageStorage
   MultiFrameTrueColorSecondaryCaptureImageStorage
   MultichannelRespiratoryWaveformStorage
   MultipleVolumeRenderingVolumetricPresentationStateStorage
   NuclearMedicineImageStorage
   OphthalmicAxialMeasurementsStorage
   OphthalmicOpticalCoherenceTomographyBscanVolumeAnalysisStorage
   OphthalmicOpticalCoherenceTomographyEnFaceImageStorage
   OphthalmicPhotography16BitImageStorage
   OphthalmicPhotography8BitImageStorage
   OphthalmicThicknessMapStorage
   OphthalmicTomographyImageStorage
   OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
   ParametricMapStorage
   PatientRadiationDoseSRStorage
   PerformedImagingAgentAdministrationSRStorage
   PlannedImagingAgentAdministrationSRStorage
   PositronEmissionTomographyImageStorage
   ProcedureLogStorage
   ProtocolApprovalStorage
   PseudoColorSoftcopyPresentationStateStorage
   RTBeamsDeliveryInstructionStorage
   RTBeamsTreatmentRecordStorage
   RTBrachyApplicationSetupDeliveryInstructionStorage
   RTBrachyTreatmentRecordStorage
   RTDoseStorage
   RTImageStorage
   RTIonBeamsTreatmentRecordStorage
   RTIonPlanStorage
   RTPhysicianIntentStorage
   RTPlanStorage
   RTRadiationRecordSetStorage
   RTRadiationSalvageRecordStorage
   RTRadiationSetDeliveryInstructionStorage
   RTRadiationSetStorage
   RTSegmentAnnotationStorage
   RTStructureSetStorage
   RTTreatmentPreparationStorage
   RTTreatmentSummaryRecordStorage
   RadiopharmaceuticalRadiationDoseSRStorage
   RawDataStorage
   RealWorldValueMappingStorage
   RespiratoryWaveformStorage
   RoboticArmRadiationStorage
   RoboticRadiationRecordStorage
   RoutineScalpElectroencephalogramWaveformStorage
   SecondaryCaptureImageStorage
   SegmentationStorage
   SegmentedVolumeRenderingVolumetricPresentationStateStorage
   SimplifiedAdultEchoSRStorage
   SleepElectroencephalogramWaveformStorage
   SpatialFiducialsStorage
   SpatialRegistrationStorage
   SpectaclePrescriptionReportStorage
   StereometricRelationshipStorage
   SubjectiveRefractionMeasurementsStorage
   SurfaceScanMeshStorage
   SurfaceScanPointCloudStorage
   SurfaceSegmentationStorage
   TomotherapeuticRadiationRecordStorage
   TomotherapeuticRadiationStorage
   TractographyResultsStorage
   TwelveLeadECGWaveformStorage
   UltrasoundImageStorage
   UltrasoundMultiFrameImageStorage
   VLEndoscopicImageStorage
   VLMicroscopicImageStorage
   VLPhotographicImageStorage
   VLSlideCoordinatesMicroscopicImageStorage
   VLWholeSlideMicroscopyImageStorage
   VideoEndoscopicImageStorage
   VideoMicroscopicImageStorage
   VideoPhotographicImageStorage
   VisualAcuityMeasurementsStorage
   VolumeRenderingVolumetricPresentationStateStorage
   WideFieldOphthalmicPhotography3DCoordinatesImageStorage
   WideFieldOphthalmicPhotographyStereographicProjectionImageStorage
   XADefinedProcedureProtocolStorage
   XAPerformedProcedureProtocolStorage
   XAXRFGrayscaleSoftcopyPresentationStateStorage
   XRay3DAngiographicImageStorage
   XRay3DCraniofacialImageStorage
   XRayAngiographicImageStorage
   XRayRadiationDoseSRStorage
   XRayRadiofluoroscopicImageStorage
