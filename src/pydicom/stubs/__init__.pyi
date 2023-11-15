from collections.abc import MutableSequence
import datetime
from decimal import Decimal

from pydicom.dataset import Dataset
from pydicom.tag import BaseTag
from pydicom.uid import UID
from pydicom.valuerep import PersonName, DA, DSfloat, DSdecimal, DT, IS, ISfloat, TM

BytesSequence = MutableSequence[bytes]
StrSequence = MutableSequence[str]
IntSequence = MutableSequence[int]
FloatSequence = MutableSequence[float]

BytesType = None | bytes
BytesListType = None | BytesSequence
DateType = None | str | datetime.date | DA
DateListType = None | StrSequence | MutableSequence[datetime.date] | MutableSequence[DA]
DateTimeType = None | str | datetime.datetime | DT
DateTimeListType = (
    None | StrSequence | MutableSequence[datetime.datetime] | MutableSequence[DT]
)
DecimalStringType = None | str | int | float | Decimal | DSfloat | DSdecimal
DecimalStringListType = (
    None
    | StrSequence
    | IntSequence
    | FloatSequence
    | MutableSequence[Decimal]
    | MutableSequence[DSfloat]
    | MutableSequence[DSdecimal]
)
FloatType = None | float
FloatListType = None | FloatSequence
IntType = None | int
IntListType = None | IntSequence
IntegerStringType = None | str | int | IS | ISfloat
IntegerStringListType = (
    None | StrSequence | IntSequence | MutableSequence[IS] | MutableSequence[ISfloat]
)
PersonNameType = None | str | PersonName
PersonNameListType = None | StrSequence | MutableSequence[PersonName]
StringType = None | str
StringListType = None | StrSequence
TagType = None | int | str | tuple[int, int] | BaseTag
TagListType = (
    None
    | IntSequence
    | StrSequence
    | MutableSequence[tuple[int, int]]
    | MutableSequence[BaseTag]
)
TimeType = None | str | datetime.time | TM
TimeListType = None | StrSequence | MutableSequence[datetime.time] | MutableSequence[TM]
UIDType = None | str | UID
UIDListType = None | StrSequence | MutableSequence[UID]

# Standard VRs
# _1: VM is 1, _1N: VM is 1-n, _N: VM is 2+-n
AE_1_Type = StringType
AE_1N_Type = StringType | StringListType
AE_N_Type = StringListType

AS_1_Type = StringType
AS_1N_Type = StringType | StringListType
AS_N_Type = StringListType

AT_1_Type = TagType
AT_1N_Type = TagType | TagListType
AT_N_Type = TagListType

CS_1_Type = StringType
CS_1N_Type = StringType | StringListType
CS_N_Type = StringListType

DA_1_Type = DateType
DA_1N_Type = DateType | DateListType
DA_N_Type = DateListType

DS_1_Type = DecimalStringType
DS_1N_Type = DecimalStringType | DecimalStringListType
DS_N_Type = DecimalStringListType

DT_1_Type = DateTimeType
DT_1N_Type = DateTimeType | DateTimeListType
DT_N_Type = DateTimeListType

FD_1_Type = FloatType
FD_1N_Type = FloatType | FloatListType
FD_N_Type = FloatListType

FL_1_Type = FloatType
FL_1N_Type = FloatType | FloatListType
FL_N_Type = FloatListType

IS_1_Type = IntegerStringType
IS_1N_Type = IntegerStringType | IntegerStringListType
IS_N_Type = IntegerStringListType

LO_1_Type = StringType
LO_1N_Type = StringType | StringListType
LO_N_Type = StringListType

LT_1_Type = StringType
LT_1N_Type = StringType | StringListType
LT_N_Type = StringListType

OB_1_Type = BytesType
OB_1N_Type = BytesType | BytesListType
OB_N_Type = BytesListType

OD_1_Type = BytesType
OD_1N_Type = BytesType | BytesListType
OD_N_Type = BytesListType

OF_1_Type = BytesType
OF_1N_Type = BytesType | BytesListType
OF_N_Type = BytesListType

OL_1_Type = BytesType
OL_1N_Type = BytesType | BytesListType
OL_N_Type = BytesListType

OW_1_Type = BytesType
OW_1N_Type = BytesType | BytesListType
OW_N_Type = BytesListType

OV_1_Type = BytesType
OV_1N_Type = BytesType | BytesListType
OV_N_Type = BytesListType

PN_1_Type = PersonNameType
PN_1N_Type = PersonNameType | PersonNameListType
PN_N_Type = PersonNameListType

SH_1_Type = StringType
SH_1N_Type = StringType | StringListType
SH_N_Type = StringListType

SL_1_Type = IntType
SL_1N_Type = IntType | IntListType
SL_N_Type = IntListType

SQType = None | MutableSequence[Dataset]

SS_1_Type = IntType
SS_1N_Type = IntType | IntListType
SS_N_Type = IntListType

ST_1_Type = StringType
ST_1N_Type = StringType | StringListType
ST_N_Type = StringListType

SV_1_Type = IntType
SV_1N_Type = IntType | IntListType
SV_N_Type = IntListType

TM_1_Type = TimeType
TM_1N_Type = TimeType | TimeListType
TM_N_Type = TimeListType

UC_1_Type = StringType
UC_1N_Type = StringType | StringListType
UC_N_Type = StringListType

UI_1_Type = UIDType
UI_1N_Type = UIDType | UIDListType
UI_N_Type = UIDListType

UL_1_Type = IntType
UL_1N_Type = IntType | IntListType
UL_N_Type = IntListType

UN_1_Type = BytesType
UN_1N_Type = BytesType | BytesListType
UN_N_Type = BytesListType

UR_1_Type = StringType
UR_1N_Type = StringType | StringListType
UR_N_Type = StringListType

US_1_Type = IntType
US_1N_Type = IntType | IntListType
US_N_Type = IntListType

UT_1_Type = StringType
UT_1N_Type = StringType | StringListType
UT_N_Type = StringListType

UV_1_Type = IntType
UV_1N_Type = IntType | IntListType
UV_N_Type = IntListType

# Ambiguous VRs
# US or SS or OW: 1, 1-n
US_SS_OW_Type = IntType | BytesType | IntListType | BytesListType
# US or OW: 1, 1-n
US_OW_Type = IntType | BytesType | IntListType | BytesListType
# US or SS: 1, 3, 4
US_SS_Type = IntType | IntListType
# OB or OW: 1
OB_OW_Type = BytesType
