from __future__ import annotations

import datetime
import importlib.resources
import sys
from pathlib import Path
from typing import Any

from itscalledsoccer.client import AmericanSoccerAnalysis
from parsimonious import Grammar
from parsimonious.nodes import Node
from pydantic import BaseModel, Field
from pypdf import PdfReader
from rapidfuzz import fuzz, process, utils

from mls_roster_profiles.models import RosterProfile, Team
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
    def _console_label(
        entity_type: str,
        from_roster_profile: dict[str, Any],
        from_itscalledsoccer: dict[str, Any],
    ) -> dict[str, Any] | None:
        user_input = ""

        print(file=sys.stderr)
        print("-------------------------", file=sys.stderr)
        print(file=sys.stderr)

        print(f"More than one possible match found for the following {entity_type}:", file=sys.stderr)
        print(file=sys.stderr)

        print("[Roster Profile]", file=sys.stderr)
        for key, value in from_roster_profile.items():
            print(f"{key}: {value}", file=sys.stderr)

        print(file=sys.stderr)

        print("[itscalledsoccer]", file=sys.stderr)
        for key, value in from_itscalledsoccer.items():
            print(f"{key}: {value}", file=sys.stderr)

        print(file=sys.stderr)
        print("Are these the same? (y/n)", file=sys.stderr)

        user_input = input()
        if user_input.lower() in ["y", "yes"]:
            return from_itscalledsoccer

    @staticmethod
    def _resolve_team_ids(teams: list[Team]) -> list[Team]:
        asa_client = AmericanSoccerAnalysis()
        teams_df = asa_client.get_teams(leagues="mls")

        lookup_dict = {row["team_name"]: row["team_id"] for _, row in teams_df.iterrows()}
        comparison_dict = {row["team_name"]: {"Name": row["team_name"]} for _, row in teams_df.iterrows()}

        for team in teams:
            matches = process.extract(
                team.name,
                lookup_dict.keys(),
                scorer=fuzz.WRatio,
                score_cutoff=86,
                processor=utils.default_process,
            )

            if len(matches) == 1:
                team.name = matches[0][0]
                team.id_ = lookup_dict.get(team.name)

            elif len(matches) > 1:
                for match in matches:
                    resolved = RosterProfileRelease._console_label(
                        entity_type="team",
                        from_roster_profile={"Name": team.name},
                        from_itscalledsoccer=comparison_dict.get(match[0]),
                    )
                    if resolved:
                        team.name = resolved.get("Name")
                        team.id_ = lookup_dict.get(team.name)
                        break

        return teams

    @classmethod
    def from_pdf(cls, stream: str | bytes | Path) -> RosterProfileRelease:
        pdf = PdfReader(stream)

        grammar_path = importlib.resources.files(__package__).joinpath("grammar.peg")
        with open(grammar_path) as f:
            grammar = Grammar(f.read())

        teams = []
        release_date = None

        for _page in pdf.pages:
            page = Page(pdf, _page)
            text = page.extract_text()

            if "SENIOR ROSTER" in text:
                tree = grammar.parse(text)
                visitor = RosterProfileVisitor()
                team, release_date = visitor.serialize(tree)
                teams.append(team)

        teams = cls._resolve_team_ids(teams)
        return cls(release_date=release_date, teams=teams)
