from __future__ import annotations

import datetime
import importlib.resources
from pathlib import Path

from itscalledsoccer.client import AmericanSoccerAnalysis
from parsimonious import Grammar
from parsimonious.nodes import Node
from pydantic import BaseModel, Field
from pypdf import PdfReader
from rapidfuzz import fuzz, process, utils

from mls_roster_profiles.models import RosterProfile, Team
from mls_roster_profiles.parsimonious import NodeVisitor
from mls_roster_profiles.pypdf.reader import Page


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
    def _resolve_team_ids(teams: list[Team]) -> list[Team]:
        asa_client = AmericanSoccerAnalysis()
        mls_teams = asa_client.get_teams(leagues="mls")
        mls_teams_lookup = {row["team_name"]: row["team_id"] for _, row in mls_teams.iterrows()}

        for team in teams:
            matches = process.extract(
                team.name,
                mls_teams_lookup.keys(),
                scorer=fuzz.WRatio,
                limit=2,
                score_cutoff=86,
                processor=utils.default_process,
            )

            if len(matches) == 1:
                team.id_ = mls_teams_lookup[matches[0][0]]
                team.name = matches[0][0]

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
