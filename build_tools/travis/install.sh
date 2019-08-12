#!/bin/bash
# This script is meant to be called by the "install" step defined in
# .travis.yml. See http://docs.travis-ci.com/ for more details.
# The behavior of the script is controlled by environment variabled defined
# in the .travis.yml in the top level folder of the project.

# License: 3-clause BSD

# Travis clone pydicom/pydicom repository in to a local repository.

set -e

echo 'List files from cached directories'
echo 'pip:'
ls $HOME/.cache/pip

export CC=/usr/lib/ccache/gcc
export CXX=/usr/lib/ccache/g++
# Useful for debugging how ccache is used
# export CCACHE_LOGFILE=/tmp/ccache.log
# ~60M is used by .ccache when compiling from scratch at the time of writing
ccache --max-size 100M --show-stats

if [[ "$DISTRIB" == "conda" ]]; then
    # Deactivate the travis-provided virtual environment and setup a
    # conda-based environment instead
    deactivate

    # Install miniconda
    wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
        -O miniconda.sh
    MINICONDA_PATH=/home/travis/miniconda
    chmod +x miniconda.sh && ./miniconda.sh -b -p $MINICONDA_PATH
    export PATH=$MINICONDA_PATH/bin:$PATH
    conda update --yes conda
    conda --version
    # the free channel is needed for Python 3.4 and can probably be skipped
    # after Python 3.4 is no longer used
    conda config --set restore_free_channel true

    # Configure the conda environment and put it in the path using the
    # provided versions
    conda create -n testenv --yes python=$PYTHON_VERSION pip
    source activate testenv
    conda install --yes nose pytest pytest-cov setuptools
    if [[ "$NUMPY" == "true" ]]; then
        conda install --yes numpy
    fi
    if [[ "$JPEG_LS" == "true" ]]; then
        conda install --yes cython
        export MSCV=False
        pip install git+https://github.com/glemaitre/CharPyLS
    fi
    if [[ "$GDCM" == "true" ]]; then
        conda install --yes -c conda-forge gdcm
    elif [[ "$GDCM" == "old" ]]; then
        conda install --yes -c conda-forge gdcm=2.8.4
    fi
    # Install nose-timer via pip
    pip install nose-timer

elif [[ "$DISTRIB" == "ubuntu" ]]; then
    # At the time of writing numpy 1.9.1 is included in the travis
    # virtualenv but we want to use the numpy installed through apt-get
    # install.
    #deactivate
    # Create a new virtualenv using system site packages for python, numpy
    #virtualenv --system-site-packages testvenv
    #source testvenv/bin/activate
    pip install --upgrade pytest
    pip uninstall -y numpy
    pip install nose nose-timer pytest-cov setuptools
    if [[ "$NUMPY" == "true" ]]; then
        pip install --upgrade --force-reinstall numpy
    fi
    if [[ "$PILLOW" == "both" ]]; then
        sudo apt install libopenjpeg
        pip install pillow --global-option="build_ext" --global-option="--enable-jpeg2000"
        python -c "from PIL.features import check_codec; print('JPEG plugin:', check_codec('jpg'))"
        python -c "from PIL.features import check_codec; print('JPEG2k plugin:', check_codec('jpg_2000'))"
    elif [[ "$PILLOW" == "jpeg" ]]; then
        pip install pillow --global-option="build_ext" --global-option="--disable-jpeg2000"
        python -c "from PIL.features import check_codec; print('JPEG plugin:', check_codec('jpg'))"
        python -c "from PIL.features import check_codec; print('JPEG2k plugin:', check_codec('jpg_2000'))"
    fi

elif [[ "$DISTRIB" == "pypy" ]]; then
    # This is to see if we are supporting pypy. With pypy3, numpypy is not
    # supported. Therefore, we fallback on the install of numpy.
    deactivate
    if [[ "$PYTHON_VERSION" == "2.7" ]]; then
        PYPY_TAR=pypy2-v5.8.0-linux64
    else
        PYPY_TAR=pypy3-v5.8.0-linux64
    fi
    wget "https://bitbucket.org/pypy/pypy/downloads/"$PYPY_TAR".tar.bz2"
    tar -xvjf $PYPY_TAR".tar.bz2"
    # setup the path to get pypy by default
    CURRENT_PATH=$(pwd)
    BIN_PATH="$CURRENT_PATH/$PYPY_TAR/bin"
    if [[ "$PYTHON_VERSION" == "2.7" ]]; then
        ln -s "$BIN_PATH/pypy" "$BIN_PATH/python"
    else
        ln -s "$BIN_PATH/pypy3" "$BIN_PATH/python"
    fi
    # add the binary to the path
    export PATH="$BIN_PATH:$PATH"
    # install pip
    python -m ensurepip --upgrade
    if [[ "$NUMPY" == "true" ]]; then
        # see #794 - avoid PyPy bug with newer NumPy versions
        python -m pip install cython numpy==1.15.4
    fi
    python -m pip install nose nose-timer pytest pytest-cov setuptools
fi

python --version
if [[ "$NUMPY" == "true" ]]; then
    python -c "import numpy; print('numpy %s' % numpy.__version__)"
fi

python setup.py develop
ccache --show-stats
# Useful for debugging how ccache is used
# cat $CCACHE_LOGFILE
