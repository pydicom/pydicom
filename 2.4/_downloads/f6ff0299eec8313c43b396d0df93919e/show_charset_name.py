"""
============================
Display unicode person names
============================

Very simple app to display unicode person names.

"""

# authors : Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : MIT

from pydicom.valuerep import PersonNameUnicode

import tkinter

print(__doc__)

default_encoding = 'iso8859'

root = tkinter.Tk()
# root.geometry("%dx%d%+d%+d" % (800, 600, 0, 0))

person_names = [
    PersonNameUnicode(
        b"Yamada^Tarou=\033$B;3ED\033(B^\033$BB@O:"
        b"\033(B=\033$B$d$^$@\033(B^\033$B$?$m$&\033(B",
        [default_encoding, 'iso2022_jp']),  # DICOM standard 2008-PS3.5 H.3 p98
    PersonNameUnicode(
        b"Wang^XiaoDong=\xcd\xf5\x5e\xd0\xa1\xb6\xab=",
        [default_encoding, 'GB18030']),  # DICOM standard 2008-PS3.5 J.3 p 105
    PersonNameUnicode(
        b"Wang^XiaoDong=\xe7\x8e\x8b\x5e\xe5\xb0\x8f\xe6\x9d\xb1=",
        [default_encoding, 'UTF-8']),  # DICOM standard 2008-PS3.5 J.1 p 104
    PersonNameUnicode(
        b"Hong^Gildong=\033$)C\373\363^\033$)C\321\316\324\327="
        b"\033$)C\310\253^\033$)C\261\346\265\277",
        [default_encoding, 'euc_kr']),  # DICOM standard 2008-PS3.5 I.2 p 101
]
for person_name in person_names:
    label = tkinter.Label(text=person_name)
    label.pack()
root.mainloop()
