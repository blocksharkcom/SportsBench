"""Markets — the abstraction that lets SportsBench predict and grade ANY bet type
on ANY sport: 1X2, over/under (goals, corners, cards, aces, games, points),
both-teams-to-score, correct score, handicaps, match winner…

A Market is a named set of mutually-exclusive **selections** plus a rule that
**settles** which one won from a match Result. Everything else (brief, grading,
value) is market-agnostic and just asks the Market for its selections + settlement.

Specs look like ``1x2``, ``btts``, ``ou_goals@2.5``, ``spread@-1.5``. Add a market
in a few lines: register a builder below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .types import Result


@dataclass(frozen=True)
class Selection:
    key: str
    label: str


@dataclass
class Market:
    key: str                       # "1x2", "ou_goals", "correct_score"
    name: str                      # human name
    sports: tuple                  # ("football",) or ("*",)
    stat: str                      # result stat that settles it: goals/corners/cards/aces/…
    selections: list              # list[Selection]
    _settle: Callable             # (Result) -> Optional[str]  winning selection key, None = void/unknown
    line: Optional[float] = None

    @property
    def spec(self) -> str:
        return f"{self.key}@{_fmt(self.line)}" if self.line is not None else self.key

    def selection_keys(self) -> list:
        return [s.key for s in self.selections]

    def label_for(self, key: str) -> str:
        for s in self.selections:
            if s.key == key:
                return s.label
        return key

    def settle(self, result: Result) -> Optional[str]:
        return self._settle(result)


def _fmt(x: float) -> str:
    return ("%g" % x)


# ----------------------------------------------------------------------------- #
# Builders. A "fixed" market takes no line; a "line" market takes @<number>.
# ----------------------------------------------------------------------------- #

def _m_1x2() -> Market:
    return Market("1x2", "Full-time result", ("football",), "goals",
                  [Selection("home", "Home"), Selection("draw", "Draw"), Selection("away", "Away")],
                  lambda r: r.outcome)


def _m_btts() -> Market:
    def settle(r: Result):
        return "yes" if r.home_score > 0 and r.away_score > 0 else "no"
    return Market("btts", "Both teams to score", ("football",), "goals",
                  [Selection("yes", "Yes"), Selection("no", "No")], settle)


def _m_dnb() -> Market:
    def settle(r: Result):
        o = r.outcome
        return None if o == "draw" else o  # draw voids the bet
    return Market("dnb", "Draw no bet", ("football",), "goals",
                  [Selection("home", "Home"), Selection("away", "Away")], settle)


def _m_match_winner(sport: str) -> Market:
    return Market("match_winner", "Match winner", (sport,), "goals",
                  [Selection("home", "Home"), Selection("away", "Away")],
                  lambda r: "home" if r.home_score >= r.away_score else "away")


# stat markets available as over/under
_OU_STATS = {
    "ou_goals": ("Total goals", "goals", ("football",)),
    "ou_corners": ("Total corners", "corners", ("football",)),
    "ou_cards": ("Total cards", "cards", ("football",)),
    "ou_games": ("Total games", "games", ("tennis",)),
    "ou_aces": ("Total aces", "aces", ("tennis",)),
    "ou_points": ("Total points", "points", ("basketball",)),
}


def _m_ou(key: str, line: float) -> Market:
    name, stat, sports = _OU_STATS[key]
    def settle(r: Result):
        return "over" if r.total(stat) > line else "under"
    return Market(key, f"{name} O/U", sports, stat,
                  [Selection("over", f"Over {_fmt(line)}"), Selection("under", f"Under {_fmt(line)}")],
                  settle, line=line)


def _m_spread(line: float) -> Market:
    # home handicap: home covers if (home_score + line) > away_score
    def settle(r: Result):
        return "home" if (r.home_score + line) > r.away_score else "away"
    return Market("spread", "Handicap (home)", ("basketball", "football"), "goals",
                  [Selection("home", f"Home {_fmt(line)}"), Selection("away", f"Away {_fmt(-line)}")],
                  settle, line=line)


def _m_correct_score(maxg: int = 3) -> Market:
    sels = [Selection(f"{h}-{a}", f"{h}-{a}") for h in range(maxg + 1) for a in range(maxg + 1)]
    sels.append(Selection("other", "Other"))
    keys = {s.key for s in sels}
    def settle(r: Result):
        k = f"{r.home_score}-{r.away_score}"
        return k if k in keys else "other"
    return Market("correct_score", "Correct score", ("football",), "goals", sels, settle)


# key -> builder (fixed markets take no arg; line markets take the line)
_FIXED = {
    "1x2": _m_1x2,
    "btts": _m_btts,
    "dnb": _m_dnb,
    "correct_score": _m_correct_score,
    "match_winner": lambda: _m_match_winner("tennis"),
    "moneyline": lambda: Market("moneyline", "Moneyline", ("basketball",), "goals",
                                [Selection("home", "Home"), Selection("away", "Away")],
                                lambda r: "home" if r.home_score >= r.away_score else "away"),
}
_LINE = {**{k: (lambda ln, kk=k: _m_ou(kk, ln)) for k in _OU_STATS}, "spread": _m_spread}

# sensible defaults offered by `sportsbench init`
DEFAULT_MARKETS = {
    "football": ["1x2", "ou_goals@2.5", "btts", "correct_score", "ou_corners@9.5"],
    "tennis": ["match_winner", "ou_games@22.5", "ou_aces@20.5"],
    "basketball": ["moneyline", "ou_points@210.5", "spread@-5.5"],
}


def parse_spec(spec: str) -> tuple:
    if "@" in spec:
        key, line = spec.split("@", 1)
        return key, float(line)
    return spec, None


def get_market(spec: str) -> Market:
    key, line = parse_spec(spec)
    if line is None and key in _FIXED:
        return _FIXED[key]()
    if line is not None and key in _LINE:
        return _LINE[key](line)
    raise ValueError(f"unknown market spec: {spec!r}. Try: {', '.join(available())}")


def available() -> list:
    return sorted(list(_FIXED) + [f"{k}@<line>" for k in _LINE])


def markets_for_sport(sport: str) -> list:
    out = []
    for k, b in _FIXED.items():
        m = b()
        if sport in m.sports or "*" in m.sports:
            out.append(k)
    for k in _LINE:
        if k == "spread" or sport in _OU_STATS.get(k, (None, None, ()))[2]:
            out.append(f"{k}@<line>")
    return out
