from enum import StrEnum


class StrEnumCaseInsensitive(StrEnum):
    @classmethod
    def _missing_(cls, value: str):
        lower_value = value.lower().replace("–", "-")  # noqa: RUF001
        for member in cls:
            if member.value.lower().replace("–", "-") == lower_value:  # noqa: RUF001
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
    PROFESSIONAL_DEVELOPMENT = "Player Professional Development Role"


class CurrentStatus(StrEnumCaseInsensitive):
    """Enumerator for current status of players in Major League Soccer."""

    ON_LOAN = "Unavailable - On Loan"
    SEI = "Unavailable - SEI"
    P1_ITC = "Unavailable - P1/ITC"
    UNAVAILABLE_OTHER = "Unavailable - Other"
    OFF_BUDGET = "Off-Budget"
    LOAN_PLAYER = "Loan Player"
    INJURED = "Unavailable - Injured List"


class RosterConstructionModel(StrEnumCaseInsensitive):
    """Enumerator for roster construction models in Major League Soccer."""

    DESIGNATED_PLAYER = "Designated Player Model"
    U22_INITIATIVE = "U22 Initiative Player Model"
