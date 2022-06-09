from f1bot import command as cmd

from f1bot.mysql import engine

import sqlalchemy as sql # type: ignore
import sqlalchemy.engine as sqlengine
import pandas
import attr

RaceId = int

def transform_to_dataframe(
    result: sqlengine.CursorResult, columns: list[str]
) -> pandas.DataFrame:
    return pandas.DataFrame(
        columns=columns, data=result.columns(*columns))

@engine.with_ergast
def get_last_race_of_year(conn: sqlengine.Connection, year: int) -> RaceId:
    """Returns the raceId for the last year in a particular race calendar."""
    result = conn.execute(sql.text(
        # Uses a window query to rank all races against other races in the
        # same year against the "races.round" column and then selects the
        # largest 1st rank.
        f"""
        SELECT
            raceId, name
        FROM (
          SELECT
            raceId, name, year, ROW_NUMBER() OVER (PARTITION BY year ORDER BY round DESC) as rnk
          FROM races) r
        WHERE r.rnk = 1 AND r.year = {year}"""))
    if result.rowcount != 1:
        raise cmd.CommandError(
                f'Failed to find the last race of the year for {year}.'
                f'Expected 1 result, found {result.rowcount}')
    row = result.first()

    # We've already made sure this isn't possible.
    assert row is not None

    return row['raceId']

@attr.define
class Event:
    pass


s = """
Name, Date, Time (PT), Time (MT), Time (CT), Time (ET)

FP1, ...
FP2, ...
FP3, ...
Qualifying, ...
Azerbaijan GP, June 11th, PT, MT, CT, ET
"""

@engine.with_ergast
def get_schedule(conn: sqlengine.Connection, year: int) -> pandas.DataFrame:
    result = conn.execute(sql.text(
        f"""
        SELECT
            r.name as "race_name",
            r.round as "round",
            r.date as "race_date",
            r.time as "race_time",
            c.name as "circuit_name",
            c.location as "location",
            fp1_date, fp1_time,
            fp2_date, fp2_time,
            fp3_date, fp3_time,
            quali_date, quali_time
        FROM races r
            INNER JOIN circuits c
            ON r.circuitId = c.circuitId
        WHERE year = {year}
        ORDER BY round"""))

    return transform_to_dataframe(
            result, 
            ["race_name", "round", "circuit_name", "location",
             "race_time", "race_date",
             "fp1_time", "fp1_date",
             "fp2_time", "fp2_date",
             "fp3_time", "fp3_date",
             "quali_time", "quali_date"])

@engine.with_ergast
def get_constructor_standings(conn: sqlengine.Connection, year: int) -> pandas.DataFrame:
    last_race_id = get_last_race_of_year(year)
    result = conn.execute(sql.text(
        f"""
        SELECT *
        FROM constructorStandings cs
        INNER JOIN constructors c
        ON cs.constructorId = c.constructorId
        WHERE raceId = {last_race_id}
        ORDER BY position
        """
    ))
    return transform_to_dataframe(result, ["name", "position", "points"])


@engine.with_ergast
def get_driver_standings(conn: sqlengine.Connection, year: int) -> pandas.DataFrame:
    last_race_id = get_last_race_of_year(year)
    result = conn.execute(sql.text(
        f"""
        SELECT *
        FROM driverStandings ds
        INNER JOIN drivers d
        ON ds.driverId = d.driverId
        WHERE raceId = {last_race_id}
        ORDER BY position
        """
    ))
    return transform_to_dataframe(
            result, ["forename", "surname", "points", "position"])
