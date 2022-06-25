from f1bot import command as cmd
from typing import Tuple
from fastf1.core import Session
from f1bot.lib import parsers
from f1bot.lib.fmt import format_lap_time
from f1bot.lib.sessions import SessionType, SessionLoader
from f1bot.mysql import ergast
import pandas
import argparse

class SessionResults(cmd.Command):
    """Returns the session results for a particular session."""

    @classmethod
    def manifest(cls) -> cmd.Manifest:
        return cmd.Manifest(
            name='results',
            description="Show the results for a session.",
        )

    @classmethod
    def init_parser(cls, parser: argparse.ArgumentParser):
        parser.add_argument('year', type=parsers.parse_year)
        parser.add_argument('weekend', type=str)
        parser.add_argument('session_type', type=SessionType.parse)

    def run(self, args: argparse.Namespace) -> cmd.CommandValue:
        year: int = args.year
        weekend: str = args.weekend
        session_type: SessionType = args.session_type
        race_id = ergast.resolve_fuzzy_race_query(year, weekend)
        if race_id is None:
            raise cmd.CommandError(f'Could not find race \'{weekend}\' in {year}.')
        return ""
        return self.get_results(year, weekend, session_type)

    def get_results(
        self, year: int, weekend: str, session_type: SessionType
    ) -> cmd.CommandValue:
        session = SessionLoader(
                session_types=[session_type]
            ).load_for_weekend(year, weekend)[0]
        if session_type == SessionType.RACE:
            return self.format_race(session)
        elif session_type == SessionType.QUALIFYING:
            return self.format_qualifying(session)
        return self.format_practice(session)


    def format_race(self, session: Session) -> cmd.CommandValue:
        results = session.results[
            ['FullName', 'Position', 'TeamName', 'Status']
        ]
        results['Position'] = results['Position'].astype(int)
        return [session.event.EventName, results]

    def format_qualifying(self, session: Session) -> cmd.CommandValue:
        results = session.results[
            ['FullName', 'Position', 'TeamName', 'Q1', 'Q2', 'Q3']
        ]

        # Converts lap times into a readable format from Timedelta
        for q in ['Q1', 'Q2', 'Q3']:
            results[q] = results[q].apply(format_lap_time)

        results['Position'] = results['Position'].astype(int)
        return [session.event.EventName, results]

    def format_practice(self, session: Session) -> pandas.DataFrame:
        return session.results

    def parse_args(self, args: list[str]) -> Tuple[int, str, SessionType]:
        if len(args) != 3:
            raise cmd.CommandError(
                f"Not enough arguments. Expected 3, found {len(args)}.")

        year = parsers.parse_year(args[0])
        if year < 1950:
            raise cmd.CommandError("Formula 1 started in 1950...")

        session_type = SessionType.parse(args[2])
        if session_type is None:
            raise cmd.CommandError(
                f"Could not parse session string: {args[2]}")

        return year, args[1], session_type
