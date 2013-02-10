# fabfile.py
"""Instructions for automated testing, building of pydicom using Fabric"""

from fabric.api import local, settings, abort
from fabric.contrib.console import confirm


def syntax():
    local("reindent -r dicom")
    with settings(warn_only=True):
        result = local("flake8 --ignore=E501 dicom")
    if result.failed and not confirm("Continue?"):
        abort("Aborted due to user request")


def test():
    local("python setup.py --quiet test")


def commit():
    local("hg stat")
ci = commit

