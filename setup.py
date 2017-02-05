#!/usr/bin/env python
try:
    from setuptools import setup
except:
    from ez_setup import use_setuptools
    use_setuptools()

extra = {}

setup(
    name="pydicom",
    packages=['pydicom',
              'pydicom.contrib',
              'pydicom.examples',
              'pydicom.util'],
    include_package_data=True,
    version="1.0.0a1",
    install_requires=[],
    zip_safe=False,  # want users to be able to see included examples,tests
    description="Pure python package for DICOM medical file reading and writing",
    author="Darcy Mason and contributors",
    author_email="darcymason@gmail.com",
    url="http://github.com/darcymason/pydicom",
    license="MIT license",
    keywords="dicom python medical imaging",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.0",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
    ],
    long_description="""
    pydicom is a pure python package for parsing DICOM files.
    DICOM is a standard (http://medical.nema.org) for communicating
    medical images and related information such as reports
    and radiotherapy objects.

    pydicom makes it easy to read these complex files into natural
    pythonic structures for easy manipulation.
    Modified datasets can be written again to DICOM format files.
    See the `Getting Started <http://pydicom.readthedocs.org/en/latest/getting_started.html>`_
    page for installation and basic information, and the
    `Pydicom User Guide <http://pydicom.readthedocs.org/en/latest/pydicom_user_guide.html>`_ page
    for an overview of how to use the pydicom library.
    """,
    test_loader="tests.run_tests:MyTestLoader",
    test_suite="dummy_string",
    **extra
)
