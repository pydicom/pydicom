.. _api_uid:

UID Definitions and Utilities (:mod:`pydicom.uid`)
==================================================

.. module:: pydicom.uid
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
   JPEGLossless
   JPEGLosslessSV1
   JPEGLSLossless
   JPEGLSNearLossless
   JPEG2000Lossless
   JPEG2000
   JPEG2000MCLossless
   JPEG2000MC
   MPEG2MPML
   MPEG2MPMLF
   MPEG2MPHL
   MPEG2MPHLF
   MPEG4HP41
   MPEG4HP41F
   MPEG4HP41BD
   MPEG4HP41BDF
   MPEG4HP422D
   MPEG4HP422DF
   MPEG4HP423D
   MPEG4HP423DF
   MPEG4HP42STEREO
   MPEG4HP42STEREOF
   HEVCMP51
   HEVCM10P51
   RLELossless
   HTJ2KLossless
   HTJ2KLosslessRPCL
   HTJ2K
   JPIPHTJ2KReferenced
   JPIPHTJ2KReferencedDeflate
   SMPTEST211020UncompressedProgressiveActiveVideo
   SMPTEST211020UncompressedInterlacedActiveVideo
   SMPTEST211030PCMDigitalAudio


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
   PrivateTransferSyntaxes


UID Utilities
-------------

.. autosummary::
   :toctree: generated/

   generate_uid
   register_transfer_syntax
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
   ConfocalMicroscopyImageStorage
   ConfocalMicroscopyTiledPyramidalImageStorage
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
   EnhancedContinuousRTImageStorage
   EnhancedMRColorImageStorage
   EnhancedMRImageStorage
   EnhancedPETImageStorage
   EnhancedRTImageStorage
   EnhancedSRStorage
   EnhancedUSVolumeStorage
   EnhancedXAImageStorage
   EnhancedXRFImageStorage
   EnhancedXRayRadiationDoseSRStorage
   ExtensibleSRStorage
   General32bitECGWaveformStorage
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
   InventoryStorage
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
   PhotoacousticImageStorage
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
   RTPatientPositionAcquisitionInstructionStorage
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
   VariableModalityLUTSoftcopyPresentationStateStorage
   VideoEndoscopicImageStorage
   VideoMicroscopicImageStorage
   VideoPhotographicImageStorage
   VisualAcuityMeasurementsStorage
   VolumeRenderingVolumetricPresentationStateStorage
   WaveformAnnotationSRStorage
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
