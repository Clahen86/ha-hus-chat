"""Small things the chat understands in a message: "buy milk" (the shopping list) and "remind me ..." (a reminder).

Pure functions - no Home Assistant - so they are easy to test. Danish, Norwegian, Swedish and English.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import re

# ---------- the shopping list ----------
SHOP = re.compile(r"^\s*(?:husk(?:\s+at)?\s+)?(?:køb|kjøp|köp|buy|get)\s+(?:lige\s+|også\s+|some\s+)?(.+?)\s*[.!]*$", re.I)
SPLIT = re.compile(r"\s*(?:,|\bog\b|\band\b|\boch\b|\+)\s*", re.I)


# "vi mangler mælk", "vi er løbet tør for kaffe", "tom for bleer" - short and plain, or it's just a sentence ("vi mangler
# dig til fodbold" isn't shopping: a person or a vague word ends it).
NEED = re.compile(r"^\s*(?:vi\s+)?(?:mangler|er\s+(?:løbet\s+)?tør\s+for|er\s+tom(?:me)?\s+for|har\s+ikke\s+mere|tom\s+for|løbet\s+tør\s+for"
                  r"|we(?:'re|\s+are)?\s+(?:out\s+of|need)|out\s+of|vi\s+(?:trenger|behöver)|tomt\s+for|slut\s+på)\s+(?:mere\s+|noget\s+|some\s+|more\s+)?(.+?)\s*[.!]*$", re.I)
NOT_THINGS = {"dig", "jer", "dem", "ham", "hende", "mig", "os", "en", "et", "nogen", "noget", "tid", "hjælp", "penge", "you", "time", "help",
              "someone", "deg", "dere", "meg", "dig själv", "lige", "bare"}


def shop_items(text: str) -> list[str]:
    """"køb mælk, brød og æg" / "vi mangler mælk og brød" -> ["Mælk", "Brød", "Æg"]. Nothing for an ordinary message."""
    m = SHOP.match(text or "") or NEED.match(text or "")
    if not m or len(m.group(1)) > 120 or "?" in text or len((text or "").split()) > 14:
        return []
    first = m.group(1).split()[0].lower().strip(" .!,") if m.group(1).split() else ""
    if first in NOT_THINGS:
        return []
    out = []
    for x in SPLIT.split(m.group(1)):
        x = x.strip(" .!")
        if x and len(x) <= 60:
            out.append(x[0].upper() + x[1:])
    return out[:10]


# ---------- reminders ----------
REMIND = re.compile(r"^\s*(?:mind|minn|påminn)\s+(mig|meg|os|oss|oss alla|alle)\s+(?:om|på|at|att)\s+(.+)$|^\s*remind\s+(me|us)\s+(?:to|about|of)?\s*(.+)$", re.I)
DAYS = {"mandag": 0, "tirsdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lørdag": 5, "søndag": 6,
        "måndag": 0, "tisdag": 1, "lördag": 5, "söndag": 6, "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6}
CLOCK = r"(?:kl\.?|klokken|klockan|at)?\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?"
PATTERNS = [  # (pattern, kind) - tried in order; the first that fits is the time, the rest is what to remember
    (re.compile(r"\b(?:om|i|in)\s+(\d+|en|et|ett|an|a|one|half(?:\s+an)?|en\s+halv)\s*(min(?:ut(?:ter|e|es|er)?)?|time[rn]?|timme|timmar|hours?|t)\b", re.I), "in"),
    (re.compile(r"\b(i\s+morgen|i\s+morgon|imorgen|tomorrow)(?:\s+(tidlig|tidig|morning|aften|kväll|evening))?(?:\s+" + CLOCK + r")?", re.I), "tomorrow"),
    (re.compile(r"\b(?:på|on|nu\s+på|næste|nästa|next)?\s*(" + "|".join(DAYS) + r")(?:\s+" + CLOCK + r")?", re.I), "day"),
    (re.compile(r"\b(i\s+aften|i\s+kväll|i\s+kveld|tonight|this\s+evening)(?:\s+" + CLOCK + r")?", re.I), "tonight"),
    (re.compile(r"\b(?:i\s+dag\s+)?(?:kl\.?|klokken|klockan|at)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", re.I), "at"),
]


def _hm(h: str | None, m: str | None, ampm: str | None, default: tuple[int, int]) -> tuple[int, int] | None:
    if h is None:
        return default
    hh, mm = int(h), int(m or 0)
    if ampm and ampm.lower() == "pm" and hh < 12:
        hh += 12
    if ampm and ampm.lower() == "am" and hh == 12:
        hh = 0
    return (hh, mm) if hh < 24 and mm < 60 else None


def _num(word: str) -> float:
    w = word.lower()
    if w.startswith("half") or w == "en halv":
        return 0.5
    return 1 if w in ("en", "et", "ett", "an", "a", "one") else float(w)


HOME = re.compile(r"\s*,?\s*(?:når|naar|when|nar)\s+(?:jeg|vi|I|we)\s+(?:kommer|er|kjem|get|am|are)\s+(?:hjem(?:me)?|home)\b", re.I)
EVERY = re.compile(r"\b(?:hver|hvert|every|varje|hver eneste)\s+(dag|day|dygn|" + "|".join(DAYS) + r")(?:\s+" + CLOCK + r")?", re.I)


def reminder(text: str, now: datetime) -> dict | None:
    """"mind mig om tandlæge i morgen kl. 8" -> {"when": tomorrow 08:00, "what": "tandlæge", "all": False}.
    None when it isn't a reminder, or no time was given (then nothing is guessed)."""
    m = REMIND.match(text or "")
    if not m:
        return None
    who, rest = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    everyone = who.lower() in ("os", "oss", "oss alla", "alle", "us")
    if h := HOME.search(rest):  # "... når jeg kommer hjem": when the phone says home, not at a time
        what = (rest[:h.start()] + " " + rest[h.end():]).strip(" ,.!")
        what = re.sub(r"^(?:at|att|to)\s+", "", what, flags=re.I)
        return {"when": None, "home": True, "what": what[0].upper() + what[1:], "all": everyone} if what else None
    if e := EVERY.search(rest):  # "hver tirsdag kl. 18": again every week (or every day)
        word = e.group(1).lower()
        hm = _hm(e.group(2), e.group(3), e.group(4), (8, 0))
        if not hm:
            return None
        day = None if word in ("dag", "day", "dygn") else DAYS[word]
        when = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        if day is None:
            when = when if when > now else when + timedelta(days=1)
        else:
            ahead = (day - now.weekday()) % 7
            when = when + timedelta(days=ahead)
            if when <= now:
                when += timedelta(days=7)
        what = (rest[:e.start()] + " " + rest[e.end():]).strip(" ,.!")
        what = re.sub(r"^(?:at|att|to)\s+", "", what, flags=re.I)
        return {"when": when, "every": 1 if day is None else 7, "what": what[0].upper() + what[1:], "all": everyone} if what else None
    for pat, kind in PATTERNS:
        f = pat.search(rest)
        if not f:
            continue
        g = f.groups()
        if kind == "in":
            n = _num(g[0])
            unit = g[1].lower()
            when = now + (timedelta(minutes=n) if unit.startswith("min") else timedelta(hours=n))
        elif kind == "tomorrow":
            part = (g[1] or "").lower()
            default = (7, 0) if part in ("tidlig", "tidig", "morning") else (19, 0) if part in ("aften", "kväll", "evening") else (8, 0)
            hm = _hm(g[2], g[3], g[4], default)
            if not hm:
                return None
            when = (now + timedelta(days=1)).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        elif kind == "day":
            hm = _hm(g[1], g[2], g[3], (8, 0))
            if not hm:
                return None
            ahead = (DAYS[g[0].lower()] - now.weekday()) % 7 or 7
            when = (now + timedelta(days=ahead)).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        elif kind == "tonight":
            hm = _hm(g[1], g[2], g[3], (19, 0))
            if not hm:
                return None
            if hm[0] < 12:
                hm = (hm[0] + 12, hm[1])  # "i aften kl 8" is 20:00
            when = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        else:  # "kl. 17" - today, or tomorrow if it has passed
            hm = _hm(g[0], g[1], g[2], (8, 0))
            if not hm:
                return None
            when = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
            if when <= now:
                when += timedelta(days=1)
        what = (rest[:f.start()] + " " + rest[f.end():]).strip(" ,.!")
        what = re.sub(r"^(?:at|att|to)\s+", "", what, flags=re.I)
        if not what or when <= now:
            return None
        return {"when": when, "what": what[0].upper() + what[1:], "all": everyone}
    return None


# ---------- on my way home ----------
def eta_minutes(lat: float | None, lon: float | None, home_lat: float, home_lon: float) -> int | None:
    """About how long home by car: the distance as the crow flies, a bit longer on the road, at town and country speed."""
    if lat is None or lon is None:
        return None
    r = 6371.0
    p1, p2 = math.radians(lat), math.radians(home_lat)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(home_lon - lon) / 2) ** 2
    km = 2 * r * math.asin(math.sqrt(a)) * 1.3
    if km < 0.3:
        return 0
    return max(5, int(round((km / (35 if km < 15 else 60) * 60 + 3) / 5) * 5))


# ---------- questions the house answers itself (before Assist) ----------
# By the words in it, in any order - not one fixed sentence: "Hvornår har Lilly fri på onsdag?", "Lilly fri onsdag?",
# "hvornår slutter Lilly i morgen", "skal Holly hentes i dag?" and "har Silas skole fredag" are the same question.
WORD = re.compile(r"[\wæøåäöüé'-]+", re.I)
SCHOOL_WORDS = {"fri", "fri?", "skole", "skolen", "slutter", "færdig", "færdige", "hentes", "hente", "henter", "hjem", "out", "school",
                "done", "finish", "finishes", "pickup", "pick", "slutt", "ferdig", "slutar", "skola", "lektioner", "timer",
                "møder", "møde", "starter", "start", "begynder", "afsted", "afsted?", "ind", "skema", "skemaet", "starts", "begins", "dag"}
START_WORDS = {"møder", "møde", "starter", "start", "begynder", "afsted", "ind", "starts", "begins", "møter", "börjar"}
BOTH_WORDS = {"skema", "skemaet", "dag", "day", "timetable", "ud", "ser"}
DINNER_WORDS = {"spise", "spiser", "mad", "aftensmad", "aftensmaden", "middag", "middagen", "dinner", "eat", "food", "maden", "aftenmad", "kvällsmat"}
WASTE_WORDS = {"skrald", "skraldet", "skraldespand", "skraldespanden", "affald", "affaldet", "spand", "spanden", "spandene", "renovation",
               "bin", "bins", "garbage", "rubbish", "søppel", "sopor", "skraldemand", "skraldemanden", "tømmes", "tømt"}
POWER_WORDS = {"strøm", "strømmen", "el", "elen", "elpris", "elprisen", "power", "electricity", "strøm?", "ström", "strømpris", "strømprisen"}
CHEAP_WORDS = {"koster", "costs", "billig", "billigst", "billigste", "billigt", "cheap", "cheapest", "pris", "prisen", "lavest", "laveste", "billigare", "billigere"}
MINE_PHRASES = re.compile(r"hvad\s+skal\s+jeg\b|hvad\s+har\s+jeg\b|mine\s+pligter|min\s+dag|what\s+do\s+i\s+have|my\s+day|my\s+chores|hva\s+skal\s+jeg", re.I)
ALL_KIDS = {"de", "børnene", "børnenes", "bornene", "ungerne", "pigerne", "drengene", "they", "kids", "children", "barna", "barnen", "alle"}
WHICH_DAY = re.compile(r"\b(i\s+dag|idag|today|i\s+morgen|imorgen|tomorrow|i\s+overmorgen|" + "|".join(DAYS) + r")\b", re.I)


def which_day(text: str, today: datetime) -> datetime | None:
    """The day a question asks about: "på onsdag" -> next Wednesday (today if it's Wednesday), "i morgen", "i dag".
    None: no day given."""
    m = WHICH_DAY.search(text or "")
    if not m:
        return None
    w = re.sub(r"\s+", " ", m.group(1).lower())
    base = today.replace(hour=0, minute=0, second=0, microsecond=0)
    if w in ("i dag", "idag", "today"):
        return base
    if w in ("i morgen", "imorgen", "tomorrow"):
        return base + timedelta(days=1)
    if w == "i overmorgen":
        return base + timedelta(days=2)
    ahead = (DAYS[w] - today.weekday()) % 7
    if ahead == 0 and re.search(r"\b(?:næste|nästa|neste|next)\s+" + re.escape(w), text or "", re.I):
        ahead = 7  # "næste onsdag" on a Wednesday is next week's
    return base + timedelta(days=ahead)


def _name_in(words: list[str], names: list[str]) -> str | None:
    """A family member's first name among the words - also with a small slip ("Lily", "Lillys", "hollys")."""
    from difflib import SequenceMatcher

    scores: dict[str, float] = {}
    for w in words:
        w2 = re.sub(r"(s|'s)$", "", w) if len(w) > 3 else w
        for n in names:
            r = max(SequenceMatcher(None, w.lower(), n.lower()).ratio(), SequenceMatcher(None, w2.lower(), n.lower()).ratio())
            if r >= 0.85 or (r >= 0.75 and len(n) >= 5):
                scores[n] = max(scores.get(n, 0.0), r)
    if not scores:
        return None
    top = max(scores.values())
    best = [n for n, r in scores.items() if r == top]
    return best[0] if len(best) == 1 else None  # two names fit as well (Lilli, Lilly): nobody's guessed


def school_mode(text: str) -> str:
    """ "start" (hvornår møder Lilly), "both" (hvordan ser Lillys dag ud, Lillys skema) or "end" (hvornår har Lilly fri)."""
    ws = {w.lower().strip("?!.,") for w in WORD.findall(text or "")}
    if re.search(r"\bskal\s+\w+\s+(?:i\s+skole|af\s*sted)\b", text or "", re.I):
        return "start"
    if ws & START_WORDS and not ws & {"fri", "slutter", "færdig", "hentes", "hente"}:
        return "start"
    if ws & BOTH_WORDS and not ws & {"fri", "slutter", "færdig", "hentes", "hente"}:
        return "both"
    return "end"


# What to bring, from the timetable: a lesson's subject (the part before the comma in Aula: "IDR, Helene ...") or a day's
# all-day event. Said in the child's own good morning.
BRING = (
    (re.compile(r"^(idr|idræt|gym|pe|sport|idrott)\b", re.I), "pe"),
    (re.compile(r"^(svø|svøm|svømning|swim|svømme|simning)", re.I), "swim"),
    (re.compile(r"^(hdk|madkundskab|mad|home ec|hjemkundskab)\b", re.I), "food"),
    (re.compile(r"\b(tur|udflugt|ekskursion|trip|lejrskole|excursion)\b", re.I), "trip"),
)


def bring(summaries: list[str]) -> list[str]:
    """["pe", "swim"] from today's lessons - each once, in order."""
    out: list[str] = []
    for s in summaries:
        head = (s or "").split(",")[0].strip()
        for pat, what in BRING:
            if (pat.search(head) or (what == "trip" and pat.search(s or ""))) and what not in out:
                out.append(what)
    return out


def question(text: str, names: list[str] | None = None) -> tuple[str, str | None] | None:
    """What a question to the house is about, from its words: ("school", "Lilly" | "all"), ("dinner", None), ("waste",
    None), ("cheap", None), ("mine", None). None when it isn't one of them - then Assist or the AI answers."""
    words = [w.lower().strip("?!.,") for w in WORD.findall(text or "")]
    ws = set(words)
    if not words:
        return None
    if re.search(r"\bskal\s+\w+\s+(?:af\s*sted|i\s+skole)\b", text or "", re.I):
        ws = ws | {"afsted"}  # "hvornår skal Lilly af sted"
    looks = {"ser", "ud"} <= ws and bool(WHICH_DAY.search(text or "")) and not ws & {"vejret", "vejr", "weather"}  # "hvordan ser Lillys mandag ud"
    # "hvornår starter Lilly til fodbold" is no school question: a start word counts only with school, or alone with a day
    other = ws - START_WORDS - {"hvornår", "when", "på", "i", "on", "next", "næste", "skal", "skole", "skolen", "school", "?", "af", "sted"} - set(DAYS) \
        - {"dag", "morgen", "overmorgen", "today", "tomorrow", "idag", "imorgen"} - {n.lower() for n in names or []} - {w + "s" for w in (n.lower() for n in names or [])}
    if ws & START_WORDS and not ws & {"skole", "skolen", "school", "fri"} and len(other) > 0:
        ws = ws - START_WORDS
    if looks or ws & SCHOOL_WORDS and ("fri" in ws or "skole" in ws or "skolen" in ws or "school" in ws or "skema" in ws or "skemaet" in ws
                                       or ws & START_WORDS or ws & {"slutter", "hentes", "hente", "færdig", "finish", "finishes", "done", "out"}):
        who = _name_in([w for w in WORD.findall(text or "")], names or []) or ("all" if ws & ALL_KIDS else None)  # a name wins over "de"
        if who:
            return "school", who
    if ws & WASTE_WORDS:
        return "waste", None
    if ws & POWER_WORDS and ws & CHEAP_WORDS:
        return "cheap", None
    if ws & DINNER_WORDS:
        return "dinner", None
    if MINE_PHRASES.search(text or ""):
        return "mine", None
    return None
