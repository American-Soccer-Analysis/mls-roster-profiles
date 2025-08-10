import datetime
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from mls_roster_profiles.enum import CurrentStatus, RosterConstructionModel, RosterDesignation, RosterSlot


class Player(BaseModel):
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
    roster_slot: RosterSlot = Field(
        default=...,
        description="Roster slot of the player, such as Senior Roster or Supplemental Roster.",
    )
    roster_designation: RosterDesignation | None = Field(
        default=None,
        description="Roster designation of the player, such as Designated Player or Homegrown Player.",
    )
    current_status: CurrentStatus | None = Field(
        default=None,
        description="Current status of the player, such as On Loan or Injured List.",
    )
    contract_through: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        default=None,
        description="Contract end date for the player. Most often a year (e.g., '2025'), but can also be a month (e.g., 'July 2025').",
    )
    option_years: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        default=None,
        description="List of option years for the player's contract. Most often a year (e.g., '2025'), but can also be a month (e.g., 'July 2025').",
    )
    permanent_transfer_option: bool = Field(
        default=False,
        description="Indicates whether the loan player's contract has a permanent transfer option.",
    )
    international_slot: bool = Field(
        default=False,
        description="Indicates whether the player occupies an international slot on the roster.",
    )
    convertible_with_tam: bool | None = Field(
        default=None,
        description="Indicates whether the player can be converted to a non-Designated Player with Targeted Allocation Money (TAM).",
    )
    unavailable: bool = Field(
        default=False,
        description="Indicates whether the player is unavailable for selection due to injury, loan, or other reasons.",
    )
    canadian_international_slot_exemption: bool | None = Field(
        default=None,
        description="Indicates whether the player does not count toward an international roster slot. Each Canadian club may designate up to three players.",
    )


class Team(BaseModel):
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
    roster_construction_model: RosterConstructionModel = Field(
        default=...,
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
    title: str = Field(validation_alias="table_title")


class SmallTableRow(BaseModel):
    player_name: str | None = None


class SmallTable(TableTitleMixin):
    rows: list[SmallTableRow] = Field(default_factory=list, validation_alias="small_table_row")


class LargeTableRow(BaseModel):
    player_name: str
    roster_designation: str | None = None
    current_status: str | None = None
    contract_through: str | None = None
    option_years: str | None = None


class LargeTable(TableTitleMixin):
    rows: list[LargeTableRow] = Field(default_factory=list, validation_alias="large_table_row")


class RosterProfile(BaseModel):
    team_name: str
    release_date: datetime.date
    roster_construction_model: str | None = None
    gam_available: int | None = None
    small_tables: list[SmallTable] = Field(default_factory=list, validation_alias="small_table")
    large_tables: list[LargeTable] = Field(default_factory=list, validation_alias="large_table")

    def _get_international_slots(self) -> int | None:
        for table in self.small_tables:
            if table.title.lower().startswith("international"):
                match = re.search(r"\d+", table.title)
                if match:
                    return int(match.group(0))

    def _enrich_international_slot(self, player: Player) -> Player:
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

    def _enrich_designated_player(self, player: Player) -> Player:
        if player.roster_designation == RosterDesignation.DP:
            player.convertible_with_tam = True
            for table in self.small_tables:
                if table.title.lower().startswith("designated"):
                    for row in table.rows:
                        if str(row.player_name).lower().startswith(player.name.lower()) and "^" in row.player_name:
                            player.convertible_with_tam = False
        return player

    def _enrich_unavailable(self, player: Player) -> Player:
        for table in self.small_tables:
            if table.title.lower().startswith("unavailable"):
                for row in table.rows:
                    if str(row.player_name).lower().startswith(player.name.lower()):
                        player.unavailable = True
        return player

    def _enrich_player(self, player: Player) -> Player:
        player = self._enrich_international_slot(player)
        player = self._enrich_designated_player(player)
        player = self._enrich_unavailable(player)
        return player

    def _get_players(self) -> list[Player]:
        players = []
        for table in self.large_tables:
            for row in table.rows:
                permanent_transfer_option = str(row.option_years).startswith("PT")
                player = Player(
                    name=row.player_name,
                    roster_slot=table.title,
                    roster_designation=row.roster_designation,
                    current_status=row.current_status,
                    contract_through=row.contract_through,
                    option_years=row.option_years,
                    permanent_transfer_option=permanent_transfer_option,
                )
                player = self._enrich_player(player)
                players.append(player)

        return players

    def to_team(self) -> Team:
        international_slots = self._get_international_slots()
        players = self._get_players()

        return Team(
            name=self.team_name,
            roster_construction_model=self.roster_construction_model,
            international_slots=international_slots,
            gam_available=self.gam_available,
            players=players,
        )
