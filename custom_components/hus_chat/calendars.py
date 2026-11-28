"""The family's calendars, found by themselves - nothing to set up.

Each calendar gets a kind from its integration or its name, and - for a child's own (school, birthdays) - the one
person it belongs to:
- waste: the waste collection (Affaldshåndtering DK, Waste Collection Schedule …)
- school: a timetable (Aula, "Skoleskema Lilly …")
- birthday: birthdays ("Fødselsdage Holly")
- family: the family's shared calendar ("Familie", "Fælles kalender")
- holiday: holidays ("Helligdage i Danmark")
A calendar is only tied to a person when exactly one person's first name is a whole word in its name - in doubt it
belongs to nobody (it's then left out of the personal lines, never shown to the wrong child).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

WASTE_PLATFORMS = {"affalddk", "waste_collection_schedule", "affaldvarme", "renoweb", "afvalbeheer", "recycle_app", "garbage_collection"}
KINDS = (  # tried in order: the first that fits
    ("waste", re.compile(r"affald|skrald|renovation|waste|garbage|bin\b|afval|müll|avfall|sopor", re.I)),
    ("school", re.compile(r"skema|skole|school|aula|lektion|timetable|stundenplan|schema|skola", re.I)),
    ("birthday", re.compile(r"fødselsdag|fodselsdag|birthday|geburtstag|födelsedag|bursdag|verjaardag", re.I)),
    ("holiday", re.compile(r"helligdag|public.?holiday|holidays\s+in|feiertag|helgdag|feestdag|^holidays?\b", re.I)),
    ("family", re.compile(r"famil|fælles|faelles|shared|household|husstand|hjemme", re.I)),
)


def kind_of(name: str, platform: str | None) -> str | None:
    if platform in WASTE_PLATFORMS:
        return "waste"
    return next((k for k, pat in KINDS if pat.search(name or "")), None)


def owner(name: str, people: list[dict[str, Any]]) -> str | None:
    """The one person whose first name is a whole word in the calendar's name - None when none or several fit."""
    hits = {p["id"] for p in people
            if (first := (p.get("name") or "").split(" ")[0].strip()) and len(first) >= 2
            and re.search(rf"(?<![\w-]){re.escape(first)}(?![\w-])", name or "", re.I)}
    return hits.pop() if len(hits) == 1 else None


def find(hass: HomeAssistant, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{entity_id, name, kind, person}] for every calendar with a kind."""
    reg = er.async_get(hass)
    out = []
    for st in hass.states.async_all("calendar"):
        if st.state == "unavailable":
            continue
        ent = reg.async_get(st.entity_id)
        name = str(st.attributes.get("friendly_name") or st.entity_id)
        kind = kind_of(name, ent.platform if ent else None)
        if not kind:
            continue
        person = owner(name, people) if kind in ("school", "birthday", "holiday", "family") else None
        if kind in ("holiday", "family") and person:
            continue  # a person's own calendar ("Lillys ferie") is nobody else's - not the family's
        out.append({"entity_id": st.entity_id, "name": name, "kind": kind, "person": person})
    return out


async def events(hass: HomeAssistant, entity_id: str, start: datetime, end: datetime, strict: bool = False) -> list[dict[str, Any]] | None:
    """The calendar's events between start and end: [{summary, start, end, all_day}] (local datetimes). A calendar that
    can't be read gives [] - or None with strict (then "no school" isn't said for a calendar that failed)."""
    try:
        res = await hass.services.async_call("calendar", "get_events", {"entity_id": entity_id, "start_date_time": start.isoformat(),
                                             "end_date_time": end.isoformat()}, blocking=True, return_response=True)
    except Exception:  # noqa: BLE001 - a calendar that can't be read is left out
        _LOGGER.debug("Could not read %s", entity_id, exc_info=True)
        return None if strict else []
    out = []
    for e in ((res or {}).get(entity_id) or {}).get("events", []):
        s, en = str(e.get("start") or ""), str(e.get("end") or "")
        all_day = len(s) == 10
        try:
            sd = dt_util.as_local(dt_util.parse_datetime(s)) if not all_day else datetime.fromisoformat(s).replace(tzinfo=dt_util.get_default_time_zone())
            ed = dt_util.as_local(dt_util.parse_datetime(en)) if en and not all_day else sd + timedelta(days=1)
        except (TypeError, ValueError):
            continue
        out.append({"summary": str(e.get("summary") or "").strip(), "start": sd, "end": ed, "all_day": all_day})
    return sorted(out, key=lambda x: x["start"])


def day_span(evs: list[dict[str, Any]]) -> tuple[datetime, datetime] | None:
    """A school day: from the first lesson to the end of the last (all-day events don't count)."""
    timed = [e for e in evs if not e["all_day"]]
    if not timed:
        return None
    return timed[0]["start"], max(e["end"] for e in timed)
