# Remove setup.py in pydicom v3.0
import os
from pathlib import Path
from setuptools import setup, find_packages

try:
    import dicom
    HAVE_DICOM = True
except ImportError:
    HAVE_DICOM = False


BASE_DIR = Path(__file__).parent
with open(BASE_DIR / "pydicom" / "_version.py") as f:
    exec(f.read())

with open(BASE_DIR / 'README.md') as f:
    long_description = f.read()


def data_files_inventory():
    root = BASE_DIR / "pydicom" / "data"
    files = [
        f.relative_to(BASE_DIR / "pydicom")
        for f in root.glob("**/*")
        if f.is_file() and f.suffix != ".pyc"
    ]
    return [os.fspath(f) for f in files]


setup(
    name="pydicom",
    version=__version__,  # noqa: F821
    author="Darcy Mason and contributors",
    author_email="darcymason@gmail.com",
    description="A pure Python package for reading and writing DICOM data",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/pydicom/pydicom",
    download_url="https://github.com/pydicom/pydicom/archive/master.zip",
    license="MIT",
    keywords="dicom python medical imaging",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries"
    ],
    packages=find_packages(),
    py_modules=[] if not HAVE_DICOM else ["dicom"],
    package_data={
        'pydicom': data_files_inventory() + ['py.typed'],
    },
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.7',
    install_requires=[],
    extras_require={
        "docs": [
            "numpy",
            "numpydoc",
            "matplotlib",
            "pillow",
            "sphinx",
            "sphinx_rtd_theme",
            "sphinx-gallery",
            "sphinxcontrib-napoleon",
            "sphinx-copybutton",
        ],
    },
    entry_points={
        "console_scripts": ["pydicom=pydicom.cli.main:main"],
        "pydicom_subcommands": [
            "codify = pydicom.cli.codify:add_subparser",
            "show = pydicom.cli.show:add_subparser"
        ],
    },
)
