# Change to a non-source folder to make sure we run the tests on the
# installed library.
- "cd C:\\"

$installed_pydicom_folder = $(python -c "import os; os.chdir('c:/'); import pydicom;\
print(os.path.dirname(pydicom.__file__))")
echo "pydicom found in: $installed_pydicom_folder"

# --pyargs argument is used to make sure we run the tests on the
# installed package rather than on the local folder
py.test --pyargs pydicom $installed_pydicom_folder -k 'not performance'
exit $LastExitCode
