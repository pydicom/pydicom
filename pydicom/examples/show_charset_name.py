# show_charset_name.py
"""Very simple app to display unicode person names"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import Tkinter
from dicom.valuerep import PersonNameUnicode

default_encoding = 'iso8859'

root = Tkinter.Tk()
# root.geometry("%dx%d%+d%+d" % (800, 600, 0, 0))

person_names = [
    PersonNameUnicode(
        """Yamada^Tarou=\033$B;3ED\033(B^\033$BB@O:\033(B=\033$B$d$^$@\033(B^\033$B$?$m$&\033(B""",
        [default_encoding, 'iso2022_jp']),  # DICOM standard 2008-PS3.5 H.3 p 98
    PersonNameUnicode(
        """Wang^XiaoDong=\xcd\xf5\x5e\xd0\xa1\xb6\xab=""",
        [default_encoding, 'GB18030']),  # DICOM standard 2008-PS3.5 J.3 p 105
    PersonNameUnicode(
        """Wang^XiaoDong=\xe7\x8e\x8b\x5e\xe5\xb0\x8f\xe6\x9d\xb1=""",
        [default_encoding, 'UTF-8']),  # DICOM standard 2008-PS3.5 J.1 p 104
    PersonNameUnicode(
        """Hong^Gildong=\033$)C\373\363^\033$)C\321\316\324\327=\033$)C\310\253^\033$)C\261\346\265\277""",
        [default_encoding, 'euc_kr']),  # DICOM standard 2008-PS3.5 I.2 p 101
]
for person_name in person_names:
    label = Tkinter.Label(text=person_name)
    label.pack()
root.mainloop()
