#!/usr/bin/env python
"""
Create UIDs for the Storage SOP Classes taken from the generated ``_uids.py``.
"""
from pathlib import Path
import re

from pydicom._uid_dict import UID_dictionary


STORAGE_REGEX = re.compile(
    ".*(Storage|Storage SOP Class|Storage - For Presentation|Storage - For "
    "Processing)$"
)

AUTOGEN_COMMENT = "# Only auto-generated Storage SOP Class UIDs below"
API_DOC_HEADING = "Storage SOP Class UIDs"


def is_storage_class(attributes):
    return (
        attributes[1] == "SOP Class"
        and STORAGE_REGEX.match(attributes[0])
        and attributes[3] != "Retired"
    )


def uid_line(uid, keyword):
    """Return the UID class definition line to be written to the file."""
    return f"{keyword} = UID('{uid}')  # noqa\n"


def update_uids(path: Path) -> None:
    """Update pydicom.uid with Storage SOP Class UID definitions."""
    retained_lines = []
    with open(path, "r") as f:
        for line in f:
            retained_lines.append(line)
            if line.startswith(AUTOGEN_COMMENT):
                break

        retained_lines.append("\n\n")

    with open(path, "w") as f:
        for line in retained_lines:
            f.write(line)

        for uid, attr in sorted(UID_dictionary.items()):
            if is_storage_class(attr):
                f.write(uid_line(uid, attr[4]))
                f.write(f'"""{uid}"""\n')


def update_api_reference(path: Path) -> None:
    """Update the API reference with the Storage SOP Class UIDs"""
    retained_lines = []
    with open(path, "r") as f:
        for line in f:
            retained_lines.append(line)
            if line.startswith(API_DOC_HEADING):
                break

        retained_lines.append("----------------------\n")
        retained_lines.append(".. autosummary::\n")
        retained_lines.append("   :toctree: generated/\n")
        retained_lines.append("\n")

    with open(path, "w") as f:
        for line in retained_lines:
            f.write(line)

        attr = UID_dictionary.values()
        attr = [v for v in attr if is_storage_class(v)]
        for attr in sorted(attr, key=lambda x: x[4]):
            f.write(f"   {attr[4]}\n")


if __name__ == "__main__":
    p = Path(__file__).parent.parent.parent / "pydicom" / "uid.py"
    p.resolve(strict=True)
    update_uids(p)

    p = Path(__file__).parent.parent.parent / "doc" / "reference" / "uid.rst"
    p.resolve(strict=True)
    update_api_reference(p)
