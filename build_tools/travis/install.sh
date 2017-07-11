#!/bin/bash
# This script is meant to be called by the "install" step defined in
# .travis.yml. See http://docs.travis-ci.com/ for more details.
# The behavior of the script is controlled by environment variabled defined
# in the .travis.yml in the top level folder of the project.

# License: 3-clause BSD

# Travis clone scikit-learn/scikit-learn repository in to a local repository.
# We use a cached directory with three scikit-learn repositories (one for each
# matrix entry) from which we pull from local Travis repository. This allows
# us to keep build artefact for gcc + cython, and gain time

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

    # Configure the conda environment and put it in the path using the
    # provided versions
    conda create -n testenv --yes python=$PYTHON_VERSION pip
    source activate testenv
    conda install --yes nose pytest pytest-cov
    if [[ "$DEPS" == "true" ]]; then
        conda install --yes numpy
    fi
    # Install nose-timer via pip
    pip install nose-timer codecov

elif [[ "$DISTRIB" == "ubuntu" ]]; then
    # At the time of writing numpy 1.9.1 is included in the travis
    # virtualenv but we want to use the numpy installed through apt-get
    # install.
    deactivate
    # Create a new virtualenv using system site packages for python, numpy
    virtualenv --system-site-packages testvenv
    source testvenv/bin/activate
    pip install nose nose-timer pytest pytest-cov codecov

elif [[ "$DISTRIB" == "pypy" ]]; then
    deactivate
    if [[ "$PYTHON_VERSION" == "2.7" ]]; then
        PYPY_TAR=pypy2-v5.8.0-linux64
    else
        PYPY_TAR=pypy3-v5.8.0-linux64
    fi
    wget "https://bitbucket.org/pypy/pypy/downloads/"$PYPY_TAR".tar.bz2"
    tar -xvjf $PYPY_TAR".tar.bz2"
    CURRENT_PATH=$(pwd)
    BIN_PATH="$CURRENT_PATH/$PYPY_TAR/bin"
    if [[ "$PYTHON_VERSION" == "2.7" ]]; then
        ln -s "$BIN_PATH/pypy" "$BIN_PATH/python"
    else
        ln -s "$BIN_PATH/pypy3" "$BIN_PATH/python"
    fi
    export PATH="$BIN_PATH:$PATH"
    python -m ensurepip
    pip install -U pip wheel
    if [[ "$DEPS" == "true" ]]; then
        python -m pip install git+https://bitbucket.org/pypy/numpy.git
    fi
    pip install nose nose-timer pytest pytest-cov codecov
fi

python --version
if [[ "$DEPS" == "true" ]]; then
    python -c "import numpy; print('numpy %s' % numpy.__version__)"
fi

python setup.py develop
ccache --show-stats
# Useful for debugging how ccache is used
# cat $CCACHE_LOGFILE
