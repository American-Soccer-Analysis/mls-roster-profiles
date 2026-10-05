import re
from enum import StrEnum

from loguru import logger
from rapidfuzz import fuzz, process, utils


class StrEnumCaseInsensitive(StrEnum):
    """
    A case-, space-, and hyphen-insensitive string enumeration.

    Values that still do not match exactly are checked against known aliases (see
    `_aliases`), and are otherwise related to the closest member by fuzzy, word order-
    insensitive matching (e.g., 'Supplemental Slot 31' to 'Supplemental Spot 31', or
    'Player Professional Development Role' to 'Professional Player Development Role'),
    provided the similarity score is at least 90.

    """

    @staticmethod
    def _process_value(value: str) -> str:
        return re.sub(r"–|-|\s", "", value.lower())  # noqa: RUF001

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        """Known variants which fall short of the fuzzy matching cutoff, keyed by
        variant and valued by the corresponding member's value."""
        return {}

    @classmethod
    def _missing_(cls, value: str):
        lower_value = cls._process_value(value)
        for member in cls:
            if cls._process_value(member.value) == lower_value:
                return member

        for alias, member_value in cls._aliases().items():
            if cls._process_value(alias) == lower_value:
                return cls(member_value)

        match = process.extractOne(
            value,
            {member: member.value for member in cls},
            scorer=fuzz.token_sort_ratio,
            processor=utils.default_process,
            score_cutoff=90,
        )
        if match:
            logger.info(f"Related '{value}' to {cls.__name__} value '{match[2].value}' (score: {match[1]:.0f})")
            return match[2]

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

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        return {
            "U22 Initiative Player": cls.U22.value,
            "U22 Initiative/ Homegrown Player": cls.U22.value,  # NOTE: Only relevant in Fall 2024 release
        }


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
    VISA = "Unavailable - Visa"


class RosterConstructionModel(StrEnumCaseInsensitive):
    """Enumerator for roster construction models in Major League Soccer."""

    DESIGNATED_PLAYER = "Designated Player Model"
    U22_INITIATIVE = "U22 Initiative Player Model"

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        return {"U22 Initiative Model": cls.U22_INITIATIVE.value}
