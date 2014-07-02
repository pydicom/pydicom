# show_dicomdir.py
"""Example file to show use of read_dicomdir()
"""
# Copyright (c) 2013 Darcy Mason
# This file is part of pydicom, relased under an MIT-style license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#

import sys
import dicom
import os.path
from pprint import pprint
# dicom.debug()


if __name__ == "__main__":
    print "------------------------------------------------------------"
    print "Example program showing DICOMDIR contents, assuming standard"
    print "Patient -> Study -> Series -> Images hierarchy"
    print "------------------------------------------------------------"
    print
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if os.path.isdir(filepath):  # only gave directory, add standard name
            filepath = os.path.join(filepath, "DICOMDIR")
        dcmdir = dicom.read_dicomdir(filepath)
        base_dir = os.path.dirname(filepath)
    else:
        # Read standard "DICOMDIR" filename from current directory
        dcmdir = dicom.read_dicomdir()
        base_dir = "."

    for patrec in dcmdir.patient_records:
        print "Patient: {0.PatientID}: {0.PatientsName}".format(patrec)
        studies = patrec.children
        for study in studies:
            print("    Study {0.StudyID}: {0.StudyDate}:"
                  " {0.StudyDescription}".format(study))
            all_series = study.children
            for series in all_series:
                image_count = len(series.children)
                plural = ('', 's')[image_count > 1]

                # Write basic series info and image count

                # Put N/A in if no Series Description
                if 'SeriesDescription' not in series:
                    series.SeriesDescription = "N/A"
                print(" " * 8 + "Series {0.SeriesNumber}:  {0.Modality}: {0.SeriesDescription}"
                      " ({1} image{2})".format(series, image_count, plural))

                # Open and read something from each image, for demonstration purposes
                # For simple quick overview of DICOMDIR, leave the following out
                print " " * 12 + "Reading images..."
                image_records = series.children
                image_filenames = [os.path.join(base_dir, *image_rec.ReferencedFileID)
                                   for image_rec in image_records]

                # slice_locations = [dicom.read_file(image_filename).SliceLocation
                #                   for image_filename in image_filenames]

                datasets = [dicom.read_file(image_filename)
                            for image_filename in image_filenames]

                patient_names = set(ds.PatientName for ds in datasets)
                patient_IDs = set(ds.PatientID for ds in datasets)

                # List the image filenames
                print "\n" + " " * 12 + "Image filenames:"
                print " " * 12,
                pprint(image_filenames, indent=12)

                # Expect all images to have same patient name, id
                # Show the set of all names, IDs found (should each have one)
                print(" " * 12 + "Patient Names in images..: "
                      "{0:s}".format(patient_names))
                print(" " * 12 + "Patient IDs in images..:"
                      "{0:s}".format(patient_IDs))

                # print (" " * 12 + "Slice Locations from "
                #       "{0} to {1}".format(min(slice_locations), max(slice_locations)))
