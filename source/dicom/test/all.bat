echo OFF
echo all.bat
echo run pydicom test suite on all supported python versions
echo ------- python 2.6 ------------
c:\python26\python run_tests.py
echo ------- python 2.7 ------------
c:\python27\python run_tests.py

REM Check location for each version -- to make sure are not running old pydicom versions
echo -
echo -----------------
echo Check locations, make sure not pointing to old pydicom code:
echo Python 2.6
c:\python26\python -c "import dicom; print dicom.__file__"
echo Python 2.7
c:\python27\python -c "import dicom; print dicom.__file__"