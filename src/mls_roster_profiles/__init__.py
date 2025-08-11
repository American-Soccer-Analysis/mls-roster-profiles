from __future__ import annotations

import datetime
import importlib.resources
import sys
from pathlib import Path

import pandas as pd
from itscalledsoccer.client import AmericanSoccerAnalysis
from loguru import logger
from parsimonious import Grammar
from parsimonious.nodes import Node
from pydantic import BaseModel, Field
from pypdf import PdfReader
from rapidfuzz import fuzz, process, utils

from mls_roster_profiles.models import Player, RosterProfile, Team
from mls_roster_profiles.parsimonious import NodeVisitor
from mls_roster_profiles.pypdf.reader import Page

__all__ = ["RosterProfileRelease"]


class RosterProfileVisitor(NodeVisitor):
    model_class: RosterProfile = RosterProfile

    def serialize(self, tree: Node) -> tuple[Team, datetime.date]:
        result = self.visit(tree)
        roster_profile = self.model_class.model_validate(result)
        return roster_profile.to_team(), roster_profile.release_date


class RosterProfileRelease(BaseModel):
    release_date: datetime.date = Field(
        default=...,
        description="Release date of the roster profiles.",
    )
    teams: list[Team] = Field(
        default_factory=list,
        description="List of teams with their roster profiles.",
    )

    @staticmethod
    def _itscalledsoccer_teams(client: AmericanSoccerAnalysis) -> list[dict[str, str]]:
        teams = client.get_teams(leagues="mls")

        teams = teams[["team_id", "team_name"]]
        teams.columns = ["ID", "Name"]

        return teams.to_dict(orient="records")

    @staticmethod
    def _itscalledsoccer_players(client: AmericanSoccerAnalysis) -> list[dict[str, str]]:
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

        logger.warning(f"Could not resolve {entity_type} '{entity.name}'")
        return entity

    @staticmethod
    def _map_ids(teams: list[Team]) -> list[Team]:
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
        pdf = PdfReader(stream)

        grammar_path = importlib.resources.files(__package__).joinpath("grammar.peg")
        with open(grammar_path) as f:
            grammar = Grammar(f.read())

        teams = []
        release_date = None

        logger.info(f"Parsing PDF with {len(pdf.pages)} pages")

        for idx, _page in enumerate(pdf.pages):
            page = Page(pdf, _page)
            text = page.extract_text()

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
