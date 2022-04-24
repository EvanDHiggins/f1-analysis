import fastf1
from fastf1.core import SessionResults
from collections import defaultdict
from attrs import define
from typing import Optional
import mock

DriverAbbrev = str
DriverNum = str
MINIMUM_SESSION_THRESHOLD = 18

@define
class DerivedDriverSessionData:
    """Collection of driver data.

    Some of this is pulled straight from fastf1.core.SessionResults, other
    pieces are derived.
    """

    # SessionResults keys drivers by the string repr of their number
    number: str

    # Driver abbreviation, e.g. VER, HAM, GAS
    abbreviation: str

    full_name: str

    # The integer position they finished in.
    finish_pos: int

    # The number of positions that they are ahead of their teammate.
    # If driver A finishes 1st and driver B finishes 4th, their deltas are 3
    # and -3, respectively.
    teammate_delta: Optional[int] = None


def get_teammates(
    session_results: SessionResults
) -> list[tuple[DriverNum, DriverNum]]:
    """Returns pairings of driver abbrevs who were teammates in this session.

    If a team ran only one driver (or >2) they'll be ommitted from the results.
    
    NOTE: Driver numbers are not stable across seasons, so this should only be
    used when considering data from a single session.
    """
    teams = defaultdict(lambda: [])
    for (driver_num, team_name) in session_results.TeamName.items():
        teams[team_name].append(driver_num)

    # Remove teams with fewer than 2 drivers (no teammates to consider)
    driver_count = {team: len(drivers) for team, drivers in teams.items()}
    for team_name, num_drivers in driver_count.items():
        if num_drivers != 2:
            teams.pop(team_name)

    return [tuple(drivers) for drivers in teams.values()]

def compute_teammate_deltas(
    session_results: SessionResults
) -> list[DerivedDriverSessionData]:
    """Converts session results to a numeric teammate delta map.

    Args:
        session_results: A session result for a single race.
    Returns:
        A mapping of driver number to the finishing delta to their teammate.
        A positive delta indicates they were ahead, a negative delta indicates
        they were behind.
    """
    def to_derived(driver_num: str) -> DerivedDriverSessionData:
        return DerivedDriverSessionData(
            number=driver_num,
            full_name=session_results.FullName[driver_num],
            abbreviation=session_results.Abbreviation[driver_num],
            finish_pos=int(session_results.Position[driver_num]))

    teammates = [
        (to_derived(d1), to_derived(d2))
        for d1, d2 in get_teammates(session_results)
    ]
    for d1, d2 in teammates:
        d1.teammate_delta = d2.finish_pos - d1.finish_pos
        d2.teammate_delta = -d1.teammate_delta


    return [driver for drivers in teammates for driver in drivers]

def get_unloaded_sessions_for_year(year: int) -> list[SessionResults]:
    schedule = fastf1.get_event_schedule(year)
    sessions = []
    for round_num in schedule.RoundNumber.values:
        if round_num == 0:
            # Testing sessions have a number, but they cause the API to blow up.
            continue
        sessions.append(fastf1.get_session(year, round_num, 'R'))
    return sessions

class Average:
    def __init__(self):
        self.total = 0
        self.count = 0

    def add(self, num: int):
        self.total += num
        self.count += 1

    def compute(self) -> float:
        return self.total / self.count

@define
class AggregateDriverData:
    name: str
    abbreviation: str
    avg_teammate_delta: float
    num_sessions: int

def compute_average_deltas_from_sessions(
    sessions: list[SessionResults]
) -> dict[DriverAbbrev, AggregateDriverData]:
    race_data = [
        compute_teammate_deltas(session.results)
        for session in sessions
    ]
    name_lookup = {}
    for race in race_data:
        for driver in race:
            if driver.full_name in name_lookup:
                raise ValueError(f'Found duplicate driver code: {driver.full_name}')
            name_lookup[driver.abbreviation] = driver.full_name

    # maps driver abbreviation to average
    delta_averages: dict[str, Average] = defaultdict(lambda: Average())

    for race in race_data:
        for driver in race:
            delta_averages[driver.abbreviation].add(driver.teammate_delta)

    average_deltas = {
        abbrev: AggregateDriverData(
            abbreviation=abbrev,
            name=name_lookup[abbrev],
            avg_teammate_delta=avg.compute(),
            num_sessions=avg.count
        )
        for abbrev, avg in delta_averages.items()
        if avg.count > MINIMUM_SESSION_THRESHOLD
    }
    return average_deltas

def main():

    fastf1.Cache.enable_cache('../.f1-cache')
    years_to_fetch = [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021]
    unloaded_sessions = []
    for year in years_to_fetch:
        unloaded_sessions.extend(get_unloaded_sessions_for_year(year))

    loaded_sessions = []
    err_count = 0
    for session in unloaded_sessions:
        try:
            # There's an error in a single session's ergast data that causes
            # fastf1 to barf. So we'll just catch the error and throw out that
            # race.
            session.load(laps=True, telemetry=False, weather=False, livedata=False)
        except ValueError:
            err_count += 1
            continue
        loaded_sessions.append(session)

    driver_averages: dict[DriverAbbrev, AggregateDriverData] = (
        compute_average_deltas_from_sessions(loaded_sessions))

    sorted_averages = sorted(
        driver_averages.values(),
        key=lambda dd: dd.avg_teammate_delta)

    for data in sorted_averages:
        print(f'{data.name} \n\tAvg: {data.avg_teammate_delta:7.4f}, #Sess: {data.num_sessions}')

    print(f'Encountered {err_count} errors.')


if __name__ == "__main__":
    main()
