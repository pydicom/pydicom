# valuerep.py
#PZ downloaded 17 Feb 2012
"""Special classes for DICOM value representations (VR)"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from decimal import Decimal
import dicom.config
from dicom.multival import MultiValue
#PZ
import codecs

#PZ
import sys
#PZ maybe hexversion is better
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
    inPy3 = False    
    namebase = object
    strbase = basestring  
    bytestring = basestring
elif sys.hexversion >= 0x03000000: 
    inPy26 = False
    inPy3 = True    
    unicode = str
    namebase = object
    bytestring = bytes
    strbase = str    

#PZ it cannot work in Py3 since there is no bytestring   
"""
from sys import version_info
if version_info[0] < 3:
    namebase = object
    bytestring = str
    strbase = str
else:
    namebase = bytestring
    strbase = basestring
"""
def clean_escseq(element, encodings):      
    """Remove escape sequences that Python does not remove from         
    Korean encoding ISO 2022 IR 149 due to the G1 code element.      """ 
#PZ 'euc_kr' will be unicode in Py3k, need to convert from bytes earlier
#PZ gets bytes, returns bytes, gets str return str
    if ('euc_kr' in encodings):
        if isinstance(element, bytestring):          
            return element.replace(b"\x1b\x24\x29\x43", b"").replace(b"\x1b\x28\x42", b"")      
        elif  isinstance(element, strbase) and inPy3:          
            return element.replace("\x1b\x24\x29\x43", "").replace("\x1b\x28\x42", "")          
    else:    
        return element  
    
def is_stringlike(name):
    """Return True if name is string-like."""
#PZ is it supposed to check if it is "str" like or "bytes" like or both?    
#PZ similar to isString(val): from dataelem.py
#PZ Both will fail to do the job if passed object that implements __str__()
#PZ for example Basetag 
#PZ
#    print('valuerep 59 isstring', type(name))
    try:
#PZ startswith is better since it does not involve __str__ but
#PZ directly calls object method
        name.startswith(" ")
#PZ        name + ""
#PZ    except TypeError:
    except: 
#        print('valuerep 68 is not string', type(name))   
        return False
    else:
#        print('valuerep 68 isstring', type(name))   
        return True

class DS(Decimal):
    """Store values for DICOM VR of DS (Decimal String).
    Note: if constructed by an empty string, returns the empty string,
    not an instance of this class.
    """
    def __new__(cls, val):
        """Create an instance of DS object, or return a blank string if one is
        passed in, e.g. from a type 2 DICOM blank value.
        """
        # DICOM allows spaces around the string, but python doesn't, so clean it
#PZ capture bytes and decode
        if isinstance(val, bytestring):
            val=val.decode('iso8859-1')
        if isinstance(val, strbase):
            val=val.strip()
        if val == '':
            return val
        if isinstance(val, float) and not dicom.config.allow_DS_float:
            msg = ("DS cannot be instantiated with a float value, unless "
                "config.allow_DS_float is set to True. It is recommended to "
                "convert to a string instead, with the desired number of digits, "
                "or use Decimal.quantize and pass a Decimal instance.")
#PZ 3109/3110                
            raise TypeError(msg)
        if not isinstance(val, Decimal):
            val = super(DS, cls).__new__(cls, val)
        if len(str(val)) > 16 and dicom.config.enforce_valid_values:
            msg = ("DS value representation must be <= 16 characters by DICOM "
                "standard. Initialize with a smaller string, or set config.enforce_valid_values "
                "to False to override, "
                "or use Decimal.quantize() and initialize with a Decimal instance.")
#PZ 3109/3110                
            raise OverflowError(msg)
        return val
    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same 
        value later. E.g. if set '1.23e2', Decimal would write '123', but DS
        will use the original
        """ 
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
#PZ original is bytes!!!! not basestring        
        if isinstance(val, bytestring):
            self.original_string = val         
            
    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "'" + self.original_string.decode('iso8859-1') + "'"
        else:
            return "'" + super(DS,self).__str__() + "'"
        
class IS(int):
    """Derived class of int. Stores original integer string for exact rewriting 
    of the string originally read or stored.
    
    Don't use this directly; call the IS() factory function instead.
    """
    # Unlikely that str(int) will not be the same as the original, but could happen
    # with leading zeros.
    def __new__(cls, val):
        """Create instance if new integer string"""
#PZ capture bytes and convert for stripping but save the original later on
        newval = val
        if isinstance(val, bytestring):
            newval = val.decode("iso8859-1")
        if isinstance(newval, strbase) and newval.strip() == '':
            return ''
        newval = super(IS, cls).__new__(cls, newval)
        # check if a float or Decimal passed in, then could have lost info,
        # and will raise error. E.g. IS(Decimal('1')) is ok, but not IS(1.23)
        if isinstance(val, (float, Decimal)) and newval != val:
#PZ 3109/3110        
            raise TypeError( "Could not convert value to integer without loss")
                # Checks in case underlying int is >32 bits, DICOM does not allow this
        if (newval < -2**31 or newval >= 2**31) and dicom.config.enforce_valid_values:
            message = "Value exceeds DICOM limits of -2**31 to (2**31 - 1) for IS"
#PZ 3109/3110            
            raise OverflowError( message)
        return newval
    def __init__(self, val):
        # If a bytestring passed, then store it
#PZ changed to bytestring        
        if isinstance(val, bytestring):
            self.original_string = val             
    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "'" + self.original_string.decode("iso8859-1") + "'"
        else:
            return "'" + int.__str__(self) + "'"

#PZ inPy3 shall we split bytes or str or both
#def MultiString(val, valtype=str):
def MultiString(val, valtype=bytestring):
    """Split a string by delimiters if there are any
    
    val -- DICOM string to split up
    valtype -- default str, but can be e.g. UID to overwrite to a specific type
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made in PET files we are converting

#PZ *************** CRITICAL in  CONVERSION ****************    
#    print("PZ 177 in valuerep Multistring", type(val), valtype)
    _splitchar = "\\"    
    if inPy3 and isinstance(val,bytestring):
#Python3 bytes 
        if val and (val.endswith(b' ') or val.endswith(b'\x00')):
            val = val[:-1]
#PZ prepare for split later            
        _splitchar = b"\\"
    else:
#Python3 string or Python2 all cases        
        if val and (val.endswith(' ') or val.endswith('\x00')):
            val = val[:-1]

    

    # XXX --> simpler version python > 2.4   splitup = [valtype(x) if x else x for x in val.split("\\")]
    splitup = []
#PZ 
    for subval in val.split(_splitchar):
        if subval:
            splitup.append(valtype(subval))
        else:
            splitup.append(subval)
    if len(splitup) == 1:
        return splitup[0]
    else:
#PZ here valtype gets bytes, str, PersonName 
#PZ if string with \ gets here it is sliced!!!!!!!!!
        return MultiValue(valtype, splitup)

class PersonNameBase(namebase):
    """Base class for Person Name classes"""
    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing for properties
        # PS 3.5-2008 section 6.2 (p.28)  and 6.2.1 describes PN. Briefly:
        #  single-byte-characters=ideographic characters=phonetic-characters
        # (each with?):
        #   family-name-complex^Given-name-complex^Middle-name^name-prefix^name-suffix 
#PZ it will be overwritter in can of PersonNameUnicode
#PZ with correct encodings
#PZ this is just to hold PersonName                        
#PZ pass val        
        self.parse()

    def formatted(self, format_str):
#PZ There is an potential issue here in Py2/Py3k conversion 
#PZ should it return bytes or str?
#PZ for now return str
        """Return a formatted string according to the format pattern
        
        Use "...%(property)...%(property)..." where property is one of
           family_name, given_name, middle_name, name_prefix, name_suffix
        """
        return format_str % self.__dict__
        
    def parse(self):
        """Break down the components and name parts"""
#PZ here we should always have string str, unicode by default in Py3        
#PZ preserve common representation                 
        self.components = self.split("=")
        nComponents = len(self.components)
        self.single_byte = self.components[0]
        self.ideographic = ''
        self.phonetic = ''
        if nComponents > 1:
            self.ideographic = self.components[1]
        if nComponents > 2:
            self.phonetic = self.components[2]       
        if self.single_byte:
            name_string = self.single_byte+"^^^^" # in case missing trailing items are left out
            parts = name_string.split("^")[:5]
            (self.family_name, self.given_name, self.middle_name,
                               self.name_prefix, self.name_suffix) = parts
        else:
            (self.family_name, self.given_name, self.middle_name, 
                self.name_prefix, self.name_suffix) = ('', '', '', '', '')

    
class PersonName(PersonNameBase, strbase):
    """Human-friendly class to hold VR of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components (PS3.5-2008 6.2.1)
    family_name,
    given_name,
    middle_name,
    name_prefix,
    name_suffix
    
    """ 
#PZ does it have to accept both str and bytes? Yes. encode if str
#PZ shall it return bytes or str? str representation of bytes except single_byte part
#PZ it should either be called with bytes read from file
#PZ or get a string read from eg input.
    def __new__(cls, val):
        """Return instance of the new class"""
#        print("PZ 274 valuerep in PersonName new type, len", type(val), len(val))        
        # Check if trying to convert a string that has already been converted 
        if isinstance(val, PersonName):
#PZ New str instance
            return super(PersonName, cls).__new__(cls, val)
        if inPy3 and isinstance(val,strbase):
            valb = val.encode('iso8859-1')
        else:
#PZ should have bytes here
            valb = val             

        components = valb.split(b"=")
        unicomponents = []
        for i, component in enumerate(components):
#            unicomponents[i] = ""
            if inPy3 and i == 0:
#PZ DICOM default or shal we use dataset default?
                unicomponents.append (component.decode('iso8859-1'))
            else:
#PZ put the rest here            
                unicomponents.append(str(component)[2:-1] )
#PZ u by default
        new_val = "=".join(unicomponents)
#PZ since there is no __new__ in PersonBaseName
#PZ next in PersonName.mro() is basestring and it is called
        return super(PersonName, cls).__new__(cls, new_val)

    def __init__(self, val):
#PZ explicitly call init in Base
        if inPy3 and isinstance(val, strbase):
            self.byteencoded = val.encode('iso8859')
            #PZ that means we got str like '\\033$)C\\373\\363^\\033$)C'        
        elif isinstance(val, PersonName):
            self.byteencoded = val.byteencoded
        else:
#PZ called with bytes            
            self.byteencoded = val

#PZ pass it on
        PersonNameBase.__init__(self, self)
        
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")
    # def __str__(self):
        # return str(self.byte_string)
        # XXX need to process the ideographic or phonetic components?
    # def __len__(self):
        # return len(self.byte_string)


        
class PersonNameUnicode(PersonNameBase, unicode):
    """Unicode version of Person Name"""

    def __new__(cls, val, encodings):
        """Return unicode string after conversion of each part
        val -- the PN value to store
        encodings -- a list of python encodings, generally found
                 from dicom.charset.python_encodings mapping
                 of values in DICOM data element (0008,0005).
        """
#        print("PZ 321 valuerep in PersonNameUnicode type,len, encod[]", type(val), len(val), encodings)
#PZ if called with same type return copy  
        if isinstance(val, PersonNameUnicode):
            return unicode.__new__(cls, val)        
#PZ if called with PersonName init on its byteencoded              
        if isinstance(val, PersonName):
            valb = val.byteencoded
#PZ by default we get bytes like it has been read from file
#PZ but in case of new entry it will be read eg by input() and we will get unicode string
#PZ in Py2 val is a bytes instance so pass it through
#PZ in Python 3 we must encode str to bytes for decoding
        elif inPy3 and isinstance(val,unicode):
            valb = val.encode('iso8859-1')
        else:
#PZ should have bytes here
            valb = val 
        # Make the possible three character encodings explicit:
        if not isinstance(encodings, list):
            encodings = [encodings]*3            
        elif len(encodings) == 2:
            encodings.append(encodings[1])
        # print encodings
#PZ bytes here so have to split with byte '='                
        components = valb.split(b"=")        
#PZ they can be bytes if passed from file 
#PZ or str if taken from dictionary so we have to check 
        unicomponents = []
        for i, component in enumerate(components):
            if inPy3 and isinstance(encodings[i], bytestring):
                encodings[i] = [encodings[i].decode('iso8859-1')  ]
            unicomponents.append(clean_escseq(component,encodings[i]).decode(encodings[i]) )
#PZ u by default
        new_val = "=".join(unicomponents)
#PZ could pass it up in MRO with super but 
#PZ it does it explicitly
#PZ after that it will pass to PersonNameUniode.__init__
#PZ which will pass it for parse to PersonNameBase.__init
        return unicode.__new__(cls, new_val)
        
    def __init__(self, val, encodings):
        self.encodings = encodings
#PZ val is now unicode str
        PersonNameBase.__init__(self, val)  
#PZ encode for internal storage, no problem here
        if inPy3 and isinstance(val, bytestring):
            self.byteencoded = val
        else:     
            self.byteencoded = self.single_byte.encode(self.encodings[0]) + b'='
            self.byteencoded += self.ideographic.encode(self.encodings[1]) + b'=' 
            self.byteencoded += self.phonetic.encode(self.encodings[1]) 
        
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")

class OtherByte(bytestring):
    pass

#PZ function to translate string of encoded bytes into bytes
#PZ that means 