import re
from enum import StrEnum


class StrEnumCaseInsensitive(StrEnum):
    @staticmethod
    def _process_value(value: str) -> str:
        return re.sub(r"–|-|\s", "", value.lower())  # noqa: RUF001

    @classmethod
    def _missing_(cls, value: str):
        lower_value = cls._process_value(value)
        for member in cls:
            if cls._process_value(member.value) == lower_value:
                return member
        return None


class RosterSlot(StrEnumCaseInsensitive):
    """Enumerator for roster slots in Major League Soccer."""

    SENIOR = "Senior Roster"
    SUPPLEMENTAL = "Supplemental Roster"
    SUPPLEMENTAL_31 = "Supplemental Spot 31"
    OFF_ROSTER = "Off-Roster (Unavailable)"


class RosterDesignation(StrEnumCaseInsensitive):
    """Enumerator for roster designations in Major League Soccer."""

    YOUNG_DP = "Young Designated Player"
    TAM = "TAM Player"
    DP = "Designated Player"
    U22 = "U22 Initiative"
    HOMEGROWN = "Homegrown Player"
    GENERATION_ADIDAS = "Generation adidas"
    PROFESSIONAL_DEVELOPMENT = "Professional Player Development Role"
    SPECIAL_DISCOVERY = "Special Discovery Player"


class CurrentStatus(StrEnumCaseInsensitive):
    """Enumerator for current status of players in Major League Soccer."""

    ON_LOAN = "Unavailable - On Loan"
    SEI = "Unavailable - SEI"
    P1_ITC = "Unavailable - P1/ITC"
    UNAVAILABLE_OTHER = "Unavailable - Other"
    UNAVAILABLE_UNSPECIFIED = "Unavailable"
    OFF_BUDGET = "Off-Budget"
    LOAN_PLAYER = "Loan Player"
    INJURED = "Unavailable - Injured List"


class RosterConstructionModel(StrEnumCaseInsensitive):
    """Enumerator for roster construction models in Major League Soccer."""

    DESIGNATED_PLAYER = "Designated Player Model"
    U22_INITIATIVE = "U22 Initiative Player Model"
