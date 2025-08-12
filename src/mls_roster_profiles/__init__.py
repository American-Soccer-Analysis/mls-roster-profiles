from __future__ import annotations

import datetime
import importlib.resources
import re
import sys
from pathlib import Path

import pandas as pd
from itscalledsoccer.client import AmericanSoccerAnalysis
from loguru import logger
from parsimonious.nodes import Node
from pydantic import BaseModel, Field
from pypdf import PdfReader
from rapidfuzz import fuzz, process, utils

from mls_roster_profiles.models import Player, RosterProfile, Team
from mls_roster_profiles.parsimonious.grammar import Grammar
from mls_roster_profiles.parsimonious.nodes import NodeVisitor
from mls_roster_profiles.pypdf.enum import DelimiterGlyph
from mls_roster_profiles.pypdf.reader import Page

__all__ = ["RosterProfileRelease"]


class RosterProfileVisitor(NodeVisitor):
    """Visitor class for serializing a parsed roster profile."""

    model_class: RosterProfile = RosterProfile

    def serialize(self, tree: Node) -> tuple[Team, datetime.date]:
        """
        Serializes the parsed roster profile into a tuple of `Team` and release date.

        Args:
            tree (Node): The parsed roster profile node.

        Returns:
            tuple[Team, datetime.date]: The serialized team and release date.

        """
        result = self.visit(tree)
        roster_profile = self.model_class.model_validate(result)
        return roster_profile.to_team(), roster_profile.release_date


class RosterProfileRelease(BaseModel):
    """
    Represents the release of a roster profile, including the release date and
    associated teams.

    Attributes:
        release_date (datetime.date): Release date of the roster profiles.
        teams (list[Team]): List of teams with their roster profiles.

    """

    release_date: datetime.date = Field(
        default=...,
        description="Release date of the roster profiles.",
    )
    teams: list[Team] = Field(
        default_factory=list,
        description="List of teams with their roster profiles.",
    )

    @staticmethod
    def _postprocess_text(text: str) -> str:
        """
        Post-processes the extracted text by applying necessary transformations.

        Args:
            text (str): The extracted text to post-process.

        Returns:
            str: The post-processed text.

        """
        return re.sub(rf"-{DelimiterGlyph.ATTRIBUTES_OPEN}.*{DelimiterGlyph.ATTRIBUTES_CLOSE}\n", "", text)

    @staticmethod
    def _itscalledsoccer_teams(client: AmericanSoccerAnalysis) -> list[dict[str, str]]:
        """
        Fetches Major League Soccer teams from `itscalledsoccer`.

        Args:
            client (AmericanSoccerAnalysis): The `itscalledsoccer` client instance.

        Returns:
            list[dict[str, str]]: A list of dictionaries representing the teams.

        """
        teams = client.get_teams(leagues="mls")

        teams = teams[["team_id", "team_name"]]
        teams.columns = ["ID", "Name"]

        return teams.to_dict(orient="records")

    @staticmethod
    def _itscalledsoccer_players(client: AmericanSoccerAnalysis) -> list[dict[str, str]]:
        """
        Fetches Major League Soccer players from `itscalledsoccer`.

        Args:
            client (AmericanSoccerAnalysis): The `itscalledsoccer` client instance.

        Returns:
            list[dict[str, str]]: A list of dictionaries representing the players.

        """
        teams = client.get_teams(leagues=["mls", "mlsnp"])
        teams = teams[["team_id", "team_name"]]

        players = client.get_players(leagues=["mls", "mlsnp"])
        players = players[["player_id", "player_name", "birth_date", "nationality", "season_name"]]
        players = players.explode("season_name", ignore_index=True).query("season_name >= '2023'")

        seasons = [str(year) for year in range(2023, datetime.date.today().year + 1)]
        xgoals = client.get_player_xgoals(leagues=["mls", "mlsnp"], season_name=seasons)
        salaries = client.get_player_salaries(leagues=["mls"], season_name=seasons)

        player_teams = pd.concat([xgoals[["player_id", "team_id"]], salaries[["player_id", "team_id"]]])
        player_teams = player_teams.explode("team_id", ignore_index=True).drop_duplicates()

        player_positions = xgoals[["player_id", "general_position"]]
        player_positions = player_positions.explode("general_position", ignore_index=True).drop_duplicates()

        players = players.merge(player_teams, on="player_id", how="left")
        players = players.merge(teams, on="team_id", how="left")
        players = players.merge(player_positions, on="player_id", how="left")
        players = players.fillna("")

        players["birth_date"] = players["birth_date"].apply(
            lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").strftime("%B %-d, %Y") if x else x
        )
        players = players.groupby(["player_id", "player_name", "birth_date", "nationality"], as_index=False).agg({
            "team_name": lambda x: ", ".join(sorted(set(x.dropna()))),
            "general_position": lambda x: ", ".join(sorted(set(x.dropna()))),
        })

        players = players[["player_id", "player_name", "team_name", "general_position", "birth_date", "nationality"]]
        players.columns = ["ID", "Name", "Team(s)", "Position(s)", "Birth Date", "Nationality"]

        return players.to_dict(orient="records")

    @staticmethod
    def _console_label(
        entity_type: str,
        from_roster_profile: dict[str, str],
        from_itscalledsoccer: dict[str, str],
    ) -> dict[str, str] | None:
        """
        Prompts the user to confirm whether the two entities provided are the same. Used
        when multiple possible matches are found for a team or player.

        Args:
            entity_type (str): The type of entity being compared (e.g., "team" or "player").
            from_roster_profile (dict[str, str]): The roster profile data for the entity.
            from_itscalledsoccer (dict[str, str]): The `itscalledsoccer` data for the entity.

        Returns:
            dict[str, str] | None: The confirmed entity data if the user agrees, otherwise None.

        """
        user_input = ""

        print(file=sys.stderr)
        print("-------------------------", file=sys.stderr)
        print(file=sys.stderr)

        print(f"More than one possible match found for the following {entity_type}:", file=sys.stderr)
        print(file=sys.stderr)

        print("[Roster Profile]", file=sys.stderr)
        for key, value in from_roster_profile.items():
            if value:
                print(f"{key}: {value}", file=sys.stderr)

        print(file=sys.stderr)

        print("[itscalledsoccer]", file=sys.stderr)
        for key, value in from_itscalledsoccer.items():
            if value and key != "ID":
                print(f"{key}: {value}", file=sys.stderr)

        print(file=sys.stderr)
        print("Are these the same? (y/n)", file=sys.stderr)

        user_input = input()
        if user_input.lower() in ["y", "yes"]:
            return from_itscalledsoccer

    @staticmethod
    def _map_id(
        entity: Team | Player,
        choices: list[dict[str, str]],
        score_cutoff: int,
        team_name: str | None = None,
    ) -> Team | Player:
        """
        Maps a team or player entity to its corresponding ID in the `itscalledsoccer`
        dataset.

        Args:
            entity (Team | Player): The team or player entity to map.
            choices (list[dict[str, str]]): The list of possible matches from `itscalledsoccer`.
            score_cutoff (int): The minimum score required to consider a match valid.
            team_name (str | None): The name of the team to which the player belongs, where applicable.

        Returns:
            Team | Player: The updated entity with the mapped ID, or the original entity if no match is found.

        """
        if isinstance(entity, Team):
            entity_type = "team"
            from_roster_profile = {"Name": entity.name}
        else:
            entity_type = "player"
            from_roster_profile = {"Name": entity.name, "Team": team_name}

        matches = process.extract(
            entity.name,
            [choice["Name"] for choice in choices],
            scorer=fuzz.WRatio,
            score_cutoff=score_cutoff,
            processor=utils.default_process,
        )

        if len(matches) == 1 or (
            len(matches) > 1
            and matches[0][1] == 100
            and entity_type == "player"
            and team_name in choices[matches[0][2]]["Team(s)"]
        ):
            idx = matches[0][2]
            entity.id_ = choices[idx]["ID"]
            entity.name = choices[idx]["Name"]
            return entity

        elif len(matches) > 1:
            for match in matches:
                labeled = RosterProfileRelease._console_label(
                    entity_type=entity_type,
                    from_roster_profile=from_roster_profile,
                    from_itscalledsoccer=choices[match[2]],
                )
                if labeled:
                    entity.id_ = labeled["ID"]
                    entity.name = labeled["Name"]
                    return entity

        logger.warning(f"No mapping identified for {entity_type} '{entity.name}'")
        return entity

    @staticmethod
    def _map_ids(teams: list[Team]) -> list[Team]:
        """
        Maps all team and player entities to their corresponding IDs in the
        `itscalledsoccer` dataset.

        Args:
            teams (list[Team]): The list of teams to map.

        Returns:
            list[Team]: The updated list of teams with mapped IDs.

        """
        logger.info("Mapping team and player names to their IDs, retrieving data from `itscalledsoccer`...")

        asa_client = AmericanSoccerAnalysis()
        itscalledsoccer_teams = RosterProfileRelease._itscalledsoccer_teams(asa_client)
        itscalledsoccer_players = RosterProfileRelease._itscalledsoccer_players(asa_client)

        logger.info("Successfully retrieved data from `itscalledsoccer`")

        for team in teams:
            logger.info(f"[{team.name}] Mapping team and player names to their IDs")

            team = RosterProfileRelease._map_id(
                entity=team,
                choices=itscalledsoccer_teams,
                score_cutoff=86,
            )

            for player in team.players:
                player = RosterProfileRelease._map_id(
                    entity=player,
                    choices=itscalledsoccer_players,
                    score_cutoff=75,
                    team_name=team.name,
                )

        logger.info("Finished mapping team and player names to their IDs")

        return teams

    @classmethod
    def from_pdf(cls, stream: str | bytes | Path) -> RosterProfileRelease:
        """
        Parses a PDF document, extracts the enclosed roster profiles, and returns a
        JSON-like structure.

        Attempts to map player and team names to their corresponding IDs in the `itscalledsoccer` dataset,
        doing so automatically when there is a single evident match, and prompting the user for confirmation
        when there are multiple potential matches.

        Produces warning messages when certain extracted values do not belong to a set of expected values,
        as well as when a player or team cannot be confidently mapped to an ID, highlighting sections of
        the output which may require manual review.

        Args:
            stream (str | bytes | Path): The PDF document to parse.

        Returns:
            RosterProfileRelease: The parsed roster profile release.

        """
        pdf = PdfReader(stream)

        rules = importlib.resources.files(__package__).joinpath("grammar.peg")
        grammar = Grammar(rules)

        teams = []
        release_date = None

        logger.info(f"Parsing PDF with {len(pdf.pages)} pages")

        for idx, _page in enumerate(pdf.pages):
            page = Page(pdf, _page)
            text = page.extract_text()
            text = cls._postprocess_text(text)

            if "SENIOR ROSTER" in text:
                tree = grammar.parse(text)
                visitor = RosterProfileVisitor()
                team, release_date = visitor.serialize(tree)
                teams.append(team)
                logger.info(f"[Page {idx + 1} of {len(pdf.pages)}] Parsed roster profile for '{team.name}'")
            else:
                logger.info(f"[Page {idx + 1} of {len(pdf.pages)}] Skipped non-roster profile page")

        teams = cls._map_ids(teams)
        return cls(release_date=release_date, teams=teams)
