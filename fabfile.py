# fabfile.py
"""Instructions for automated testing, building of pydicom using Fabric"""

from fabric.api import local, settings, abort
from fabric.contrib.console import confirm

import os.path
import pydicom
pydicompath = pydicom.__path__[0]
tox_ini = os.path.join(pydicompath, "../tox.ini")


def syntax():
    local("reindent -r " + pydicompath)
    with settings(warn_only=True):
        result = local("flake8 --ignore=E501 " + pydicompath)
    if result.failed and not confirm("Continue?"):
        abort("Aborted due to user request")


def test():
    local("python setup.py --quiet test")


def fulltest():
    local("tox -c" + tox_ini)


def commit():
    local("hg stat")
ci = commit

