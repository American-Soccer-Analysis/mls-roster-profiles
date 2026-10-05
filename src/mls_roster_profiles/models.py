import datetime
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from mls_roster_profiles.enum import CurrentStatus, RosterConstructionModel, RosterDesignation, RosterSlot


class Player(BaseModel):
    """
    Represents a Major League Soccer player and details about their current contract.

    Attributes:
        id_ (str | None): Unique identifier for the player.
        name (str): Full name of the player.
        entered_via_homegrown_contract (bool | None): Indicates whether the player entered MLS via a Homegrown contract, denoted by an 'HG' tag beneath the player's name. Set to None for releases which do not note this (i.e., prior to September 2026).
        roster_slot (RosterSlot): Roster slot of the player, such as 'Senior Roster' or 'Supplemental Roster.'
        roster_designation (RosterDesignation | None): Roster designation of the player, such as 'Designated Player' or 'Homegrown Player.'
        current_status (list[CurrentStatus] | None): Current status(es) of the player, such as 'Unavailable - On Loan' or 'Unavailable - Injured List.'
        contract_through (str | None): Contract end date for the player. Most often a year (e.g., '2025'), but can also be a month (e.g., 'July 2025').
        option_years (list[str] | None): Contract option years for the player. Most often a year (e.g., '2025') or season (e.g., '2027-28'), but can also be a month (e.g., 'June 2027').
        permanent_transfer_option_years (list[str] | None): Year(s) through which the club may execute a permanent transfer option for the player, who is on loan. Set to None if there is no such option.
        loan_option_years (list[str] | None): Year(s) denoted by 'LO' in the roster profile, presumably the year(s) through which the club holds an option to extend the player's loan. Set to None if not denoted.
        international_slot (bool): Indicates whether the player occupies an international slot on the roster.
        convertible_with_tam (bool | None): Indicates whether the player can be converted to a non-Designated Player with Targeted Allocation Money (TAM). Set to None if the player is not a Designated Player.
        unavailable (bool): Indicates whether the player is unavailable for selection due to injury, loan, or other reasons.
        canadian_international_slot_exemption (bool | None): Indicates whether the player does not count toward an international roster slot. Each Canadian club may designate up to three players. Set to None if the player is not contracted to a Canadian team.

    """

    model_config = ConfigDict(serialize_by_alias=True)

    id_: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        default=None,
        serialization_alias="id",
        description="Unique identifier for the player.",
    )
    name: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        default=...,
        description="Full name of the player.",
    )
    entered_via_homegrown_contract: bool | None = Field(
        default=None,
        description="Indicates whether the player entered MLS via a Homegrown contract, denoted by an 'HG' tag beneath the player's name. Set to None for releases which do not note this (i.e., prior to September 2026).",
    )
    roster_slot: RosterSlot = Field(
        default=...,
        description="Roster slot of the player, such as 'Senior Roster' or 'Supplemental Roster.'",
    )
    roster_designation: RosterDesignation | None = Field(
        default=None,
        description="Roster designation of the player, such as 'Designated Player' or 'Homegrown Player.'",
    )
    current_status: list[CurrentStatus] | None = Field(
        default=None,
        description="Current status(es) of the player, such as 'Unavailable - On Loan' or 'Unavailable - Injured List.'",
    )
    contract_through: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        default=None,
        description="Contract end date for the player. Most often a year (e.g., '2025'), but can also be a month (e.g., 'July 2025').",
    )
    option_years: list[Annotated[str, StringConstraints(strip_whitespace=True)]] | None = Field(
        default=None,
        description="Contract option years for the player. Most often a year (e.g., '2025') or season (e.g., '2027-28'), but can also be a month (e.g., 'June 2027').",
    )
    permanent_transfer_option_years: list[Annotated[str, StringConstraints(strip_whitespace=True)]] | None = Field(
        default=None,
        description="Year(s) through which the club may execute a permanent transfer option for the player, who is on loan. Set to None if there is no such option.",
    )
    loan_option_years: list[Annotated[str, StringConstraints(strip_whitespace=True)]] | None = Field(
        default=None,
        description="Year(s) denoted by 'LO' in the roster profile, presumably the year(s) through which the club holds an option to extend the player's loan. Set to None if not denoted.",
    )
    international_slot: bool = Field(
        default=False,
        description="Indicates whether the player occupies an international slot on the roster.",
    )
    convertible_with_tam: bool | None = Field(
        default=None,
        description="Indicates whether the player can be converted to a non-Designated Player with Targeted Allocation Money (TAM). Set to None if the player is not a Designated Player.",
    )
    unavailable: bool = Field(
        default=False,
        description="Indicates whether the player is unavailable for selection due to injury, loan, or other reasons.",
    )
    canadian_international_slot_exemption: bool | None = Field(
        default=None,
        description="Indicates whether the player does not count toward an international roster slot. Each Canadian club may designate up to three players. Set to None if the player is not contracted to a Canadian team.",
    )

    @field_validator("current_status", mode="before")
    @classmethod
    def validate_current_status(cls, value: str | list[str] | None) -> list[str] | None:
        if isinstance(value, str):
            value = [_value.strip() for _value in re.split(r"[;,]", value) if _value.strip()]
        return value or None


class Team(BaseModel):
    """
    Represents a Major League Soccer team and the makeup of its roster.

    Attributes:
        id_ (str | None): Unique identifier for the team.
        name (str): Full name of the team.
        roster_construction_model (RosterConstructionModel | None): Roster construction model of the team, such as Designated Player Model or U22 Initiative Player Model.
        players (list[Player]): List of players on the team.
        international_slots (int): Number of international slots presently available to the team.
        gam_available (int | None): Amount of this season's General Allocation Money (GAM) presently available to the team.

    """

    model_config = ConfigDict(serialize_by_alias=True)

    id_: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        default=None,
        serialization_alias="id",
        description="Unique identifier for the team.",
    )
    name: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        default=...,
        description="Full name of the team.",
    )
    roster_construction_model: RosterConstructionModel | None = Field(
        default=None,
        description="Roster construction model of the team, such as Designated Player Model or U22 Initiative Player Model.",
    )
    players: list[Player] = Field(
        default_factory=list,
        description="List of players on the team.",
    )
    international_slots: int = Field(
        default=...,
        description="Number of international slots presently available to the team.",
    )
    gam_available: int | None = Field(
        default=None,
        description="Amount of this season's General Allocation Money (GAM) presently available to the team.",
    )


class TableTitleMixin(BaseModel):
    """Mixin class for the title of a table."""

    title: str = Field(validation_alias="table_title")


class SmallTableRow(BaseModel):
    """Represents a row in a small table, specifiying which players occupy a team's
    international slots, Designated Player slots, etc."""

    player_name: str | None = None


class SmallTable(TableTitleMixin):
    """Represents a small table, specifiying which players occupy a team's international
    slots, Designated Player slots, etc."""

    rows: list[SmallTableRow] = Field(default_factory=list, validation_alias="small_table_row")


class LargeTableRow(BaseModel):
    """Represents a row in a large table, specifying each rostered player's designation,
    contract details, etc."""

    player_name: str
    homegrown: str | None = None
    roster_designation: str | None = None
    current_status: str | None = None
    contract_through: str | None = None
    option_years: str | None = None

    def split_option_years(self) -> dict[str, list[str] | None]:
        """
        Splits the raw option years into contract option years, permanent transfer
        option years, and loan option years.

        Segments are separated by semicolons and may be prefixed with 'PT:' (permanent transfer option) or
        'LO:' (loan option), with years separated by commas within each segment. Unprefixed segments are
        contract option years. For example, 'LO: 2026; PT: 2028; 2029, 2030' yields loan option years of
        ['2026'], permanent transfer option years of ['2028'], and contract option years of ['2029', '2030'].

        Returns:
            dict[str, list[str] | None]: The option years, keyed by the corresponding `Player` attribute.

        """
        option_years = {"option_years": [], "permanent_transfer_option_years": [], "loan_option_years": []}
        prefixes = {"PT": "permanent_transfer_option_years", "LO": "loan_option_years"}

        for segment in str(self.option_years or "").split(";"):
            key = "option_years"
            match = re.match(r"\s*(PT|LO)\s*:", segment)
            if match:
                key = prefixes[match.group(1)]
                segment = segment[match.end() :]
            option_years[key].extend(year.strip() for year in segment.split(",") if year.strip())

        return {key: years or None for key, years in option_years.items()}


class LargeTable(TableTitleMixin):
    """Represents a large table, specifying each rostered player's designation, contract
    details, etc."""

    rows: list[LargeTableRow] = Field(default_factory=list, validation_alias="large_table_row")


class RosterProfile(BaseModel):
    """Represents a roster profile for a single Major League Soccer team."""

    team_name: str
    release_date: datetime.date
    roster_construction_model: str | None = None
    gam_available: int | None = None
    small_tables: list[SmallTable] = Field(default_factory=list, validation_alias="small_table")
    large_tables: list[LargeTable] = Field(default_factory=list, validation_alias="large_table")

    def _get_international_slots(self) -> int | None:
        """
        From the relevant table title, extract the number of international slots the
        team possesses.

        Returns:
            int | None: The number of international slots, or None if not found.

        """
        for table in self.small_tables:
            if table.title.lower().startswith("international"):
                match = re.search(r"\d+", table.title)
                if match:
                    return int(match.group(0))

    def _enrich_from_international_slots(self, player: Player) -> Player:
        """
        Enriches the player object with details found in the "International Slots"
        table.

        Args:
            player (Player): The player object to enrich.

        Returns:
            Player: The enriched player object.

        """
        for table in self.small_tables:
            if table.title.lower().startswith("international"):
                if any("+" in str(row.player_name) for row in table.rows):
                    player.canadian_international_slot_exemption = False

                for row in table.rows:
                    if str(row.player_name).lower().startswith(player.name.lower()):
                        player.international_slot = True
                        if "+" in row.player_name:
                            player.canadian_international_slot_exemption = True
                        break
        return player

    def _enrich_from_designated_players(self, player: Player) -> Player:
        """
        Enriches the player object with details found in the "Designated Players" table.

        Args:
            player (Player): The player object to enrich.

        Returns:
            Player: The enriched player object.

        """
        if player.roster_designation == RosterDesignation.DP:
            player.convertible_with_tam = True
            for table in self.small_tables:
                if table.title.lower().startswith("designated"):
                    for row in table.rows:
                        if str(row.player_name).lower().startswith(player.name.lower()) and "^" in row.player_name:
                            player.convertible_with_tam = False
        return player

    def _enrich_from_unavailable_players(self, player: Player) -> Player:
        """
        Enriches the player object with details found in the "Unavailable Players"
        table.

        Args:
            player (Player): The player object to enrich.

        Returns:
            Player: The enriched player object.

        """
        for table in self.small_tables:
            if table.title.lower().startswith("unavailable"):
                for row in table.rows:
                    if str(row.player_name).lower().startswith(player.name.lower()):
                        player.unavailable = True
        return player

    def _enrich_player(self, player: Player) -> Player:
        """
        Enriches the player object with details from various small tables.

        Args:
            player (Player): The player object to enrich.

        Returns:
            Player: The enriched player object.

        """
        player = self._enrich_from_international_slots(player)
        player = self._enrich_from_designated_players(player)
        player = self._enrich_from_unavailable_players(player)
        return player

    def _get_players(self) -> list[Player]:
        """
        Extracts player information from the large tables and enriches each player
        object with details from various small tables.

        Returns:
            list[Player]: The list of extracted players.

        """
        players = []
        for table in self.large_tables:
            for row in table.rows:
                player = Player(
                    name=row.player_name,
                    entered_via_homegrown_contract=row.homegrown is not None,
                    roster_slot=table.title,
                    roster_designation=row.roster_designation,
                    current_status=row.current_status,
                    contract_through=row.contract_through,
                    **row.split_option_years(),
                )
                player = self._enrich_player(player)
                players.append(player)

        return players

    def to_team(self) -> Team:
        """
        Converts the roster profile to a `Team` object.

        Returns:
            Team: The constructed team object.

        """
        international_slots = self._get_international_slots()
        players = self._get_players()

        return Team(
            name=self.team_name,
            roster_construction_model=self.roster_construction_model,
            international_slots=international_slots,
            gam_available=self.gam_available,
            players=players,
        )
