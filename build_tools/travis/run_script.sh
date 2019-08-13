#!/bin/bash

set -e

if [[ "$DISTRIB" == "ubuntu" ]]; then
    py.test --cov=pydicom -r sx --pyargs pydicom
    bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash) ||
        (sleep 30 && bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash))

    NUMPY="true"
    pip install --force-reinstall numpy

    py.test --cov=pydicom -r sx --pyargs pydicom
    bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash) ||
        (sleep 30 && bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash))

    PILLOW="jpeg"
    pip install pillow --global-option="build_ext" --global-option="--disable-jpeg2000"
    python -c "from PIL.features import check_codec; print('JPEG plugin:', check_codec('jpg'))"
    python -c "from PIL.features import check_codec; print('JPEG2k plugin:', check_codec('jpg_2000'))"

    py.test --cov=pydicom -r sx --pyargs pydicom
    bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash) ||
        (sleep 30 && bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash))

    pip uninstall pillow

    PILLOW="both"
    sudo apt-get update
    sudo apt-get install -y libopenjp2-7 libopenjp2-7-dev
    pip install pillow --global-option="build_ext" --global-option="--enable-jpeg2000"
    python -c "from PIL.features import check_codec; print('JPEG plugin:', check_codec('jpg'))"
    python -c "from PIL.features import check_codec; print('JPEG2k plugin:', check_codec('jpg_2000'))"

    py.test --cov=pydicom -r sx --pyargs pydicom
    bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash) ||
        (sleep 30 && bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash))
else
    py.test --cov=pydicom -r sx --pyargs pydicom
    bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash) ||
        (sleep 30 && bash <(curl --connect-timeout 10 --retry 10 --retry-max-time 0 https://codecov.io/bash))
fi
