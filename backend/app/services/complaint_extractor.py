"""Structured complaint extraction for HERB-INFO AI (rule-based NLP, no external service).

Responsibilities:
- Detect every complaint mentioned by the user (multi-symptom) with its characteristic (jenis).
- Handle negation ("tidak pilek", "batuk tidak berdahak" -> batuk kering).
- Extract body temperature (value + unit), classify it, and cross-check it against the stated complaints.
- Detect danger signs while respecting negation.
- Normalise the "obat rutin" field so "tidak ada" / "belum minum obat" is never treated as a drug name.

The module has no dependency on search_service (avoids circular imports); the caller passes in
the emergency keyword list.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

# --------------------------------------------------------------------------------------
# Negation handling
# --------------------------------------------------------------------------------------
NEGATION_CUES: frozenset[str] = frozenset(
    {
        "tidak", "tak", "tdk", "gak", "ga", "nggak", "ngga", "enggak", "engga",
        "bukan", "tanpa", "belum", "nihil",
    }
)
NEGATION_WINDOW_TOKENS = 3

# Clause delimiters. "atau"/"maupun" are captured separately so negation scope can be extended.
_CLAUSE_DELIM = re.compile(
    r"(?P<hard>(?:(?<!\d),|,(?!\d)|;|\.(?!\d)|\n)"
    r"|\s+(?:dan|serta|tetapi|tapi|namun|sedangkan|disertai|ditambah|juga|lalu|kemudian|sambil|karena)\s+)"
    r"|(?P<soft>\s+(?:atau|maupun)\s+)"
)


def _clauses(text: str) -> list[dict[str, Any]]:
    """Split text into clauses; each clause remembers the delimiter type that precedes it."""
    result: list[dict[str, Any]] = []
    pos = 0
    sep_before = "start"
    for m in _CLAUSE_DELIM.finditer(text):
        result.append({"start": pos, "end": m.start(), "sep_before": sep_before})
        pos = m.end()
        sep_before = "soft" if m.group("soft") else "hard"
    result.append({"start": pos, "end": len(text), "sep_before": sep_before})
    return result


def _clause_index(clauses: list[dict[str, Any]], offset: int) -> int:
    for idx, c in enumerate(clauses):
        if c["start"] <= offset <= c["end"]:
            return idx
    return len(clauses) - 1


def _prefix_has_negation(text: str, clause_start: int, match_start: int) -> bool:
    prefix_tokens = re.findall(r"[a-z]+", text[clause_start:match_start])
    window = prefix_tokens[-NEGATION_WINDOW_TOKENS:]
    return any(tok in NEGATION_CUES for tok in window)


def is_negated(text: str, match_start: int, clauses: Optional[list[dict[str, Any]]] = None) -> bool:
    """Return True when the term starting at match_start is negated inside its clause."""
    cl = clauses if clauses is not None else _clauses(text)
    ci = _clause_index(cl, match_start)
    clause = cl[ci]
    if _prefix_has_negation(text, clause["start"], match_start):
        return True
    # Scope extension: "tidak demam atau pilek" -> pilek is also negated.
    if clause["sep_before"] == "soft" and ci > 0:
        own_tokens = re.findall(r"[a-z]+", text[clause["start"]:clause["end"]])
        if len(own_tokens) <= 3:
            prev = cl[ci - 1]
            prev_tokens = re.findall(r"[a-z]+", text[prev["start"]:prev["end"]])
            if any(tok in NEGATION_CUES for tok in prev_tokens):
                return True
    return False


# --------------------------------------------------------------------------------------
# Symptom lexicon
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SymptomDef:
    key: str
    label: str
    jenis: str
    patterns: tuple[str, ...]
    exact: str = r"(?!)"          # regex on recipe keluhan_terkait => exact match
    generic: str = r"(?!)"        # regex on recipe keluhan_terkait => general / partial match
    conflict: str = r"(?!)"       # regex on recipe keluhan_terkait => explicit conflicting characteristic
    qa_text: Optional[str] = None  # text fed to the Q&A knowledge base (None => use label, "" => skip)
    catatan_generik: str = ""


_NEG_DAHAK = r"(?:tanpa|tidak|tak|ga|gak|nggak|ngga|enggak|engga)"

SYMPTOM_LEXICON: tuple[SymptomDef, ...] = (
    SymptomDef(
        key="batuk_kering",
        label="batuk kering",
        jenis="batuk tanpa dahak (kering)",
        patterns=(
            r"batuk(?:\s+yang)?\s+(?:kering|non[\s-]?produktif)",
            rf"batuk(?:\s+yang)?\s+{_NEG_DAHAK}\s+(?:ada\s+|disertai\s+|mengeluarkan\s+|keluar\s+)?(?:berdahak|dahak|berlendir|lendir)",
        ),
        exact=r"batuk\s+kering|batuk\s+tidak\s+berdahak",
        generic=r"\bbatuk\b(?!\s+(?:berdahak|berlendir|produktif))",
        conflict=r"batuk\s+(?:berdahak|berlendir|produktif)",
        qa_text="",
        catatan_generik="Sumber hanya menyebut 'batuk' tanpa membedakan batuk kering atau berdahak.",
    ),
    SymptomDef(
        key="batuk_berdahak",
        label="batuk berdahak",
        jenis="batuk disertai dahak (produktif)",
        patterns=(
            r"batuk(?:\s+yang)?\s+(?:berdahak|berlendir|produktif|disertai\s+dahak|dengan\s+dahak|ada\s+dahak|ada\s+lendir|keluar\s+dahak)",
        ),
        exact=r"batuk\s+berdahak|batuk\s+berlendir",
        generic=r"\bbatuk\b(?!\s+(?:kering|tidak\s+berdahak|non))",
        conflict=r"batuk\s+(?:kering|tidak\s+berdahak)",
        qa_text="batuk berdahak dahak",
        catatan_generik="Sumber hanya menyebut 'batuk' tanpa membedakan batuk kering atau berdahak.",
    ),
    SymptomDef(
        key="batuk",
        label="batuk",
        jenis="batuk (jenis kering/berdahak belum disebutkan)",
        patterns=(r"batuk(?:[\s-]batuk)?",),
        exact=r"\bbatuk\b",
        qa_text="batuk",
    ),
    SymptomDef(
        key="demam",
        label="demam",
        jenis="peningkatan suhu tubuh yang dilaporkan",
        patterns=(
            r"demam(?!\s+berdarah)",
            r"meriang",
            r"panas\s+badan",
            r"badan\s+(?:saya\s+|terasa\s+)*(?:panas|hangat)",
            r"panas\s+tinggi",
            r"suhu\s+(?:badan\s+|tubuh\s+)?(?:tinggi|naik|meningkat)",
        ),
        exact=r"demam|meriang|panas\s+badan|penurun\s+panas",
        qa_text="demam",
    ),
    SymptomDef(
        key="sakit_tenggorokan",
        label="sakit tenggorokan",
        jenis="nyeri/gatal pada tenggorokan",
        patterns=(
            r"sakit\s+tenggorokan",
            r"radang\s+tenggorokan",
            r"tenggorokan\s+(?:saya\s+|ku\s+)?(?:terasa\s+|yang\s+)?(?:sakit|nyeri|perih|radang|gatal|kering)",
            r"(?:nyeri|sakit)\s+(?:saat\s+)?menelan",
            r"tenggorokan",
        ),
        exact=r"sakit\s+tenggorokan|radang\s+tenggorokan",
        generic=r"tenggorokan",
        qa_text="tenggorokan",
        catatan_generik="Sumber menyebut tenggorokan dalam konteks keluhan lain (misalnya gatal).",
    ),
    SymptomDef(
        key="pilek",
        label="pilek",
        jenis="hidung berair/tersumbat",
        patterns=(
            r"pilek",
            r"hidung\s+(?:saya\s+)?(?:meler|berair|tersumbat|mampet|buntu|beringus)",
            r"ingusan|beringus",
            r"flu",
        ),
        exact=r"pilek|hidung|flu",
        qa_text="pilek",
    ),
    SymptomDef(
        key="sakit_kepala_sebelah",
        label="sakit kepala sebelah",
        jenis="nyeri kepala sebelah (tipe migrain)",
        patterns=(
            r"sakit\s+kepala\s+sebelah",
            r"nyeri\s+kepala\s+sebelah",
            r"kepala\s+(?:saya\s+)?sebelah",
            r"migrain|migren",
        ),
        exact=r"sakit\s+kepala\s+sebelah",
        qa_text="sakit kepala",
    ),
    SymptomDef(
        key="sakit_kepala",
        label="sakit kepala",
        jenis="nyeri kepala (tipe belum disebutkan)",
        patterns=(
            r"sakit\s+kepala",
            r"nyeri\s+kepala",
            r"kepala\s+(?:saya\s+)?(?:terasa\s+)?(?:sakit|nyeri|pening|pusing)",
            r"pusing|pening",
        ),
        exact=r"sakit\s+kepala(?!\s+sebelah)",
        generic=r"sakit\s+kepala\s+sebelah",
        qa_text="sakit kepala",
        catatan_generik="Sumber mencatat sakit kepala sebelah; tipe sakit kepala Anda belum dipastikan.",
    ),
    SymptomDef(
        key="perut_kembung",
        label="perut kembung",
        jenis="perut kembung/begah",
        patterns=(
            r"perut\s+(?:saya\s+|ku\s+)?(?:terasa\s+|sering\s+|selalu\s+)*(?:kembung|begah|sebah|penuh(?:\s+gas)?|bergas)",
            r"kembung|begah|sebah",
            r"penuh\s+gas",
        ),
        exact=r"perut\s+kembung|kembung|begah",
        qa_text="perut kembung mual",
    ),
    SymptomDef(
        key="gangguan_lambung",
        label="gangguan lambung",
        jenis="keluhan lambung (maag/asam lambung)",
        patterns=(
            r"asam\s+lambung",
            r"perih\s+(?:di\s+)?lambung",
            r"(?:nyeri|sakit)\s+(?:di\s+)?lambung",
            r"gangguan\s+lambung",
            r"lambung\s+(?:saya\s+)?(?:perih|sakit|nyeri|bermasalah)",
            r"maag|dispepsia|ulu\s+hati",
            r"lambung",
        ),
        exact=r"lambung",
        qa_text="lambung",
    ),
    SymptomDef(
        key="mual",
        label="mual",
        jenis="rasa mual",
        patterns=(r"mual(?:-mual)?", r"eneg", r"rasa\s+ingin\s+muntah"),
        exact=r"mual",
        generic=r"masuk\s+angin|lambung",
        qa_text="mual",
        catatan_generik="Sumber menyebut mual dalam konteks keluhan pencernaan/masuk angin.",
    ),
    SymptomDef(
        key="masuk_angin",
        label="masuk angin",
        jenis="istilah tradisional (bukan diagnosis)",
        patterns=(r"masuk\s+angin",),
        exact=r"masuk\s+angin",
        qa_text="masuk angin",
    ),
    SymptomDef(
        key="nyeri_haid",
        label="nyeri haid",
        jenis="nyeri saat menstruasi",
        patterns=(
            r"nyeri\s+(?:saat\s+)?(?:haid|menstruasi|mens|datang\s+bulan)",
            r"sakit\s+(?:saat\s+)?(?:haid|menstruasi|datang\s+bulan)",
            r"dismenore|senggugut",
            r"kram\s+(?:saat\s+)?(?:perut\s+)?(?:haid|menstruasi|datang\s+bulan)",
            r"perut\s+(?:sakit|nyeri|kram)\s+(?:saat\s+|waktu\s+)?(?:haid|menstruasi|datang\s+bulan)",
            r"nyeri\s+perut\s+(?:saat\s+|waktu\s+)?(?:haid|menstruasi)",
        ),
        exact=r"nyeri\s+haid|dismenore",
        conflict=r"haid\s+tidak\s+teratur",
        qa_text="nyeri haid",
    ),
    SymptomDef(
        key="haid_tidak_teratur",
        label="haid tidak teratur",
        jenis="siklus haid tidak teratur",
        patterns=(
            r"haid\s+(?:saya\s+)?(?:tidak|tak)\s+teratur",
            r"haid\s+(?:saya\s+)?(?:telat|terlambat|berantakan|tidak\s+lancar)",
            r"telat\s+haid",
            r"siklus\s+haid\s+(?:saya\s+)?(?:tidak\s+teratur|berantakan)",
            r"(?:menstruasi|mens)\s+(?:tidak|tak)\s+teratur",
        ),
        exact=r"haid\s+tidak\s+teratur",
        conflict=r"nyeri\s+haid",
        qa_text="haid",
    ),
    SymptomDef(
        key="haid_ambigu",
        label="haid",
        jenis="konteks menstruasi (keluhan spesifik belum disebutkan: apakah nyeri haid atau siklus tidak teratur)",
        patterns=(
            r"\b(?:saya\s+)?(?:sedang\s+|lagi\s+)?(?:haid|menstruasi|mens|datang\s+bulan)\b",
        ),
        exact=r"(?!)",
        generic=r"(?!)",
        conflict=r".*",
        qa_text="",
        catatan_generik="Konteks menstruasi belum spesifik (apakah nyeri haid atau haid tidak teratur).",
    ),
    SymptomDef(
        key="terkilir",
        label="terkilir",
        jenis="cedera otot/sendi ringan (istilah awam)",
        patterns=(r"terkilir|keseleo|kesleo|salah\s+urat",),
        exact=r"terkilir",
        qa_text="terkilir",
    ),
    SymptomDef(
        key="leher_kaku",
        label="leher kaku",
        jenis="kaku/pegal pada leher",
        patterns=(
            r"leher\s+(?:saya\s+)?(?:terasa\s+)?(?:kaku|tegang|pegal|tengeng)",
            r"(?:kaku|pegal)\s+(?:di\s+)?leher",
            r"tengeng|salah\s+bantal",
        ),
        exact=r"leher\s+kaku",
        qa_text="leher kaku",
    ),
    SymptomDef(
        key="panas_dalam",
        label="panas dalam",
        jenis="istilah tradisional (bukan diagnosis)",
        patterns=(r"panas\s+dalam", r"sariawan", r"bibir\s+(?:pecah|pecah-pecah)"),
        exact=r"panas\s+dalam|sariawan",
        qa_text="sariawan",
    ),
    SymptomDef(
        key="nafsu_makan_berkurang",
        label="nafsu makan berkurang",
        jenis="penurunan nafsu makan",
        patterns=(
            r"(?:kurang|tidak\s+ada|tak\s+ada|hilang|tidak|tak|ga|gak)\s+nafsu\s+makan",
            r"nafsu\s+makan\s+(?:saya\s+)?(?:berkurang|menurun|turun|hilang|kurang|rendah)",
            r"(?:susah|sulit|malas)\s+makan",
        ),
        exact=r"nafsu\s+makan|penurunan\s+nafsu",
        qa_text="nafsu makan",
    ),
    SymptomDef(
        key="diare",
        label="diare",
        jenis="buang air besar cair",
        patterns=(r"diare|mencret", r"bab\s+cair|buang\s+air\s+besar\s+cair|berak\s+cair"),
        exact=r"diare|buang\s+air\s+besar\s+cair",
        qa_text="diare",
    ),
    SymptomDef(
        key="menggigil",
        label="menggigil",
        jenis="gejala penyerta (tanpa referensi ramuan)",
        patterns=(r"menggigil",),
        qa_text="",
    ),
    SymptomDef(
        key="lemas",
        label="lemas",
        jenis="gejala penyerta (tanpa referensi ramuan)",
        patterns=(r"lemas|lemah\s+badan|letih",),
        qa_text="",
    ),
)

SYMPTOM_BY_KEY: dict[str, SymptomDef] = {s.key: s for s in SYMPTOM_LEXICON}

# Pseudo-symptom: standalone dahak modifier ("batuk, tidak berdahak").
_DAHAK_MODIFIER = r"berdahak|dahak|berlendir"


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])")


_COMPILED: list[tuple[str, re.Pattern[str]]] = []
for _sd in SYMPTOM_LEXICON:
    for _p in _sd.patterns:
        _COMPILED.append((_sd.key, _compile(_p)))
_COMPILED.append(("_dahak", _compile(_DAHAK_MODIFIER)))

# --------------------------------------------------------------------------------------
# Temperature extraction
# --------------------------------------------------------------------------------------
TEMP_MIN_C = 30.0
TEMP_MAX_C = 45.0
TEMP_FEVER_C = 37.5
TEMP_LOW_URGENT_C = 35.0
TEMP_HIGH_URGENT_C = 40.0

_NUM = r"(\d{2,3}(?:[.,]\d{1,2})?)"
_TEMP_EXPLICIT = re.compile(
    rf"(?<![\d.,]){_NUM}"
    r"(?:\s*(?:°|º|˚)\s*(?P<u1>[cf])?(?![a-z])"
    r"|\s*derajat(?:\s*(?P<u2>celsius|celcius|fahrenheit|c|f)(?![a-z]))?"
    r"|\s*(?P<u3>celsius|celcius|fahrenheit|c|f)(?![a-z]))"
)
_TEMP_KEYWORD = re.compile(
    r"(?:suhu|temperatur|termometer|thermometer|demam|panas)"
    r"(?:\s+(?:badan|tubuh))?(?:\s+(?:saya|aku|ku))?"
    r"(?:\s+(?:ada|di|sekitar|sekira|kira-kira|kurang\s+lebih|sampai|hingga|mencapai|sebesar|adalah|jadi|naik\s+(?:ke|jadi|sampai)|sebanyak)|\s*[:=])*"
    rf"\s*{_NUM}(?![\d]|[.,]\d)"
    r"(?!\s*(?:hari|jam|menit|minggu|bulan|tahun|kali|x|mg|ml|gram|kg|%|persen))"
)


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


_NON_BODY_CONTEXT = re.compile(r"(?:udara|ruangan|ruang|cuaca|lingkungan|kamar|luar|air)\s*(?:sekitar|di|sebesar|=|:)?\s*$")


def format_celsius(value: float) -> str:
    """Format as Indonesian decimal comma, e.g. 38,3°C / 33°C."""
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}°C"
    return f"{value:.1f}".replace(".", ",") + "°C"


def classify_temperature(celsius: float) -> tuple[str, str]:
    if celsius < TEMP_LOW_URGENT_C:
        return "rendah_mendesak", "di bawah 35°C (suhu rendah, perlu penilaian medis segera)"
    if celsius < TEMP_FEVER_C:
        return "tanpa_demam", "dalam rentang tanpa demam (35,0-37,4°C)"
    if celsius < 38.0:
        return "subfebris", "suhu meningkat ringan (37,5-37,9°C)"
    if celsius < 39.0:
        return "demam", "demam (38,0-38,9°C)"
    if celsius < TEMP_HIGH_URGENT_C:
        return "demam_tinggi", "demam tinggi (39,0-39,9°C)"
    return "sangat_tinggi_mendesak", "40°C atau lebih (suhu sangat tinggi, perlu penilaian medis segera)"


def extract_temperatures(text: str) -> list[dict[str, Any]]:
    """Extract body-temperature mentions ("33 derajat", "33°C", "38,3°C", "suhu 38.3", "101 F")."""
    low = text.lower()
    found: list[dict[str, Any]] = []
    used_spans: list[tuple[int, int]] = []

    def overlaps(span: tuple[int, int]) -> bool:
        return any(not (span[1] <= s or span[0] >= e) for s, e in used_spans)

    def build(raw_num: str, unit_letter: Optional[str], explicit_word: bool, source_text: str,
              span: tuple[int, int], keyword_led: bool) -> Optional[dict[str, Any]]:
        value = _to_float(raw_num)
        unit = (unit_letter or "").lower()
        is_f = unit in {"f", "fahrenheit"}
        unit_explicit = unit in {"c", "celsius", "celcius", "f", "fahrenheit"}
        if is_f:
            if not (86.0 <= value <= 113.0):
                return None
            celsius = round((value - 32.0) * 5.0 / 9.0, 1)
        else:
            celsius = value
            if not (TEMP_MIN_C <= celsius <= TEMP_MAX_C):
                if not keyword_led:
                    return None
                return {
                    "nilai_asli": raw_num.replace(".", ",") if "," in raw_num else raw_num,
                    "nilai_celsius": None,
                    "satuan": "°C",
                    "satuan_eksplisit": unit_explicit,
                    "teks_asli": source_text.strip(),
                    "valid": False,
                    "kategori_kode": "tidak_valid",
                    "kategori": "angka tidak tampak seperti suhu tubuh manusia",
                    "tampilan": raw_num,
                }
        kode, label = classify_temperature(celsius)
        used_spans.append(span)
        return {
            "nilai_asli": raw_num,
            "nilai_celsius": celsius,
            "satuan": "°C",
            "satuan_asli": "°F" if is_f else "°C",
            "satuan_eksplisit": unit_explicit,
            "satuan_diasumsikan": not unit_explicit,
            "teks_asli": source_text.strip(),
            "valid": True,
            "kategori_kode": kode,
            "kategori": label,
            "tampilan": format_celsius(celsius),
        }

    for m in _TEMP_EXPLICIT.finditer(low):
        context_before = low[max(0, m.start() - 24):m.start()]
        if _NON_BODY_CONTEXT.search(context_before):
            continue  # e.g. "suhu udara 30 derajat" is ambient temperature, not body temperature
        unit_letter = m.group("u1") or m.group("u2") or m.group("u3")
        item = build(m.group(1), unit_letter, True, m.group(0), m.span(), keyword_led=False)
        if item:
            found.append(item)

    for m in _TEMP_KEYWORD.finditer(low):
        num_span = m.span(1)
        if overlaps(num_span):
            continue
        item = build(m.group(1), None, False, m.group(0), num_span, keyword_led=True)
        if item:
            found.append(item)
    return found


# --------------------------------------------------------------------------------------
# Duration extraction
# --------------------------------------------------------------------------------------
_NUMBER_WORDS = r"(?:satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh)"
_DURATION_PATTERNS = (
    r"(sejak\s+(?:kemarin(?:\s+(?:pagi|siang|sore|malam))?|tadi\s+(?:pagi|siang|sore|malam)|semalam|minggu\s+lalu|bulan\s+lalu|beberapa\s+hari|pagi\s+ini|hari\s+ini))",
    rf"((?:\d+|{_NUMBER_WORDS})\s*(?:hari|minggu|bulan|jam))",
    r"(seminggu|sebulan|sehari|setengah\s+hari)",
    r"(berhari-hari|berminggu-minggu|terus-menerus|sudah\s+lama)",
)


def extract_duration(raw_query: str, explicit_duration: str = "") -> Optional[str]:
    if explicit_duration and explicit_duration.strip():
        return re.sub(r"\s+", " ", explicit_duration.strip())
    low = re.sub(r"\s+", " ", (raw_query or "").lower())
    for pat in _DURATION_PATTERNS:
        m = re.search(pat, low)
        if m:
            return m.group(1).strip()
    return None


# --------------------------------------------------------------------------------------
# Danger sign detection (negation aware)
# --------------------------------------------------------------------------------------
def find_unnegated_keywords(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    clauses = _clauses(low)
    hits: list[str] = []
    for kw in keywords:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
            if not is_negated(low, m.start(), clauses):
                hits.append(kw)
                break
    return hits


# --------------------------------------------------------------------------------------
# Medication statement normalisation
# --------------------------------------------------------------------------------------
_MED_NONE_EXACT = {
    "tidak", "tak", "belum", "gak", "ga", "nggak", "ngga", "enggak", "tdk", "nihil", "kosong",
    "none", "no", "n/a", "na", "-", "tidak ada", "tak ada", "ga ada", "gak ada", "nggak ada",
    "tdk ada", "belum ada",
}
_MED_NONE_START = re.compile(r"^(?:tidak|tak|belum|gak|ga|nggak|ngga|enggak|tdk|nihil|kosong)\b")
_MED_NONE_EXCEPT = re.compile(r"\b(?:kecuali|selain|hanya|cuma|tapi|namun)\b")

_QUERY_MED_NONE_PATTERNS = (
    re.compile(
        r"(?:obat(?:\s+rutin)?|konsumsi\s+obat|minum\s+obat)\s*[:=\-]?\s*"
        r"(?:tidak(?:\s+ada)?|tak\s+ada|ga\s+ada|gak\s+ada|nggak\s+ada|tdk\s+ada|nihil|belum\s+ada|belum|tidak|-)"
        r"(?![a-z])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:tidak|belum|tak|gak|ga|nggak|ngga|enggak|tdk)\s+(?:sedang\s+|pernah\s+|ada\s+|rutin\s+)*"
        r"(?:minum|mengonsumsi|mengkonsumsi|konsumsi|pakai|memakai|menggunakan|makan)\s+"
        r"(?:obat(?:\s+rutin|\s+medis|\s+dokter)?(?:\s+apa\s*pun|\s+apapun)?)(?![a-z])",
        re.IGNORECASE,
    ),
    re.compile(r"obat(?:\s+rutin)?\s*[:=]\s*$", re.IGNORECASE),
)


def normalize_medication_input(value: str) -> str:
    """Return the medication text, or "" when the user reports no routine medication."""
    cleaned = re.sub(r"\s+", " ", (value or "").strip().lower()).strip(" .,:;!?-")
    if not cleaned:
        return ""
    if cleaned in _MED_NONE_EXACT:
        return ""
    if _MED_NONE_START.match(cleaned) and not _MED_NONE_EXCEPT.search(cleaned):
        return ""
    return re.sub(r"\s+", " ", value.strip())


def strip_medication_none_statements(query: str) -> tuple[str, bool]:
    """Remove "obat rutin: tidak ada"-style statements from free text.

    Returns (cleaned_query, found_statement).
    """
    cleaned = query or ""
    found = False
    for pat in _QUERY_MED_NONE_PATTERNS:
        new_text, n = pat.subn(" ", cleaned)
        if n:
            found = True
            cleaned = new_text
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;:-")
    cleaned = re.sub(r"(?:\s+(?:dan|serta|tetapi|tapi|namun|juga|dengan))+$", "", cleaned).strip(" .,;:-")
    cleaned = re.sub(r"^(?:(?:dan|serta|tetapi|tapi|namun|juga)\s+)+", "", cleaned).strip(" .,;:-")
    return cleaned, found


# --------------------------------------------------------------------------------------
# Main extraction
# --------------------------------------------------------------------------------------
def extract_structured_complaints(
    text: str,
    emergency_keywords: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Extract all complaints, characteristics, negations, temperature and danger signs."""
    low = re.sub(r"\s+", " ", (text or "").lower()).strip()
    clauses = _clauses(low)

    # 1. Collect lexicon matches, longest first, non-overlapping.
    candidates: list[tuple[int, int, str, str]] = []
    for key, pat in _COMPILED:
        for m in pat.finditer(low):
            candidates.append((m.start(), m.end(), key, m.group(0)))
    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    accepted: list[tuple[int, int, str, str]] = []
    for c in candidates:
        if any(not (c[1] <= a[0] or c[0] >= a[1]) for a in accepted):
            continue
        accepted.append(c)
    accepted.sort(key=lambda c: c[0])

    entries: list[dict[str, Any]] = []
    for start, end, key, matched in accepted:
        entries.append(
            {
                "key": key,
                "teks_asli": matched,
                "start": start,
                "negasi": is_negated(low, start, clauses),
            }
        )

    # 2. Resolve generic "batuk" + standalone dahak modifier.
    batuk_idx = next((i for i, e in enumerate(entries) if e["key"] == "batuk"), None)
    modifiers = [e for e in entries if e["key"] == "_dahak"]
    if batuk_idx is not None and modifiers:
        mod = modifiers[0]
        base = entries[batuk_idx]
        base["key"] = "batuk_kering" if mod["negasi"] else "batuk_berdahak"
        base["teks_asli"] = f"{base['teks_asli']} ... {mod['teks_asli']}"
        base["negasi"] = False
    elif batuk_idx is None and modifiers:
        for mod in modifiers:
            if not mod["negasi"]:
                mod["key"] = "batuk_berdahak"
    entries = [e for e in entries if e["key"] != "_dahak"]

    # 3. Build positive / negated symptom lists (dedupe by key).
    positives: list[dict[str, Any]] = []
    negated: list[dict[str, Any]] = []
    seen_pos: set[str] = set()
    seen_neg: set[str] = set()
    for e in entries:
        sd = SYMPTOM_BY_KEY.get(e["key"])
        if sd is None:
            continue
        if e["negasi"]:
            if e["key"] not in seen_neg:
                seen_neg.add(e["key"])
                negated.append({"key": sd.key, "nama": sd.label, "teks_asli": e["teks_asli"]})
        elif e["key"] not in seen_pos:
            seen_pos.add(e["key"])
            positives.append(
                {
                    "key": sd.key,
                    "nama": sd.label,
                    "jenis": sd.jenis,
                    "status": "dilaporkan",
                    "teks_asli": e["teks_asli"],
                }
            )

    # A specific cough type supersedes the unspecified "batuk" entry.
    if {"batuk_kering", "batuk_berdahak"} & seen_pos and "batuk" in seen_pos:
        positives = [p for p in positives if p["key"] != "batuk"]
        seen_pos.discard("batuk")

    # A specific menstruation complaint supersedes ambiguous "haid_ambigu".
    if {"nyeri_haid", "haid_tidak_teratur"} & seen_pos and "haid_ambigu" in seen_pos:
        positives = [p for p in positives if p["key"] != "haid_ambigu"]
        seen_pos.discard("haid_ambigu")

    stated_demam = "demam" in seen_pos
    demam_negated = "demam" in seen_neg

    # 4. Temperature.
    temps = extract_temperatures(low)
    primary_temp = next((t for t in temps if t["valid"]), None)
    konflik: list[str] = []
    informasi_belum_jelas: list[str] = []
    pertanyaan: list[str] = []
    peringatan_suhu: list[str] = []
    tanda_bahaya: list[str] = []
    peringatan_mendesak: list[str] = []

    for t in temps:
        if not t["valid"]:
            informasi_belum_jelas.append(
                f"Angka '{t['nilai_asli']}' yang disebut sebagai suhu tidak tampak seperti suhu tubuh manusia."
            )
            pertanyaan.append(
                f"Apakah angka {t['nilai_asli']} adalah suhu tubuh hasil pengukuran termometer? Mohon tulis ulang suhu yang terukur beserta satuannya (°C)."
            )

    if primary_temp is not None:
        c = primary_temp["nilai_celsius"]
        kode = primary_temp["kategori_kode"]
        tampil = primary_temp["tampilan"]
        if kode == "rendah_mendesak":
            msg = (
                f"PERINGATAN MEDIS MENDESAK: suhu tubuh yang Anda laporkan ({tampil}) berada di bawah 35°C. "
                "Suhu serendah ini tidak lazim dan perlu dinilai tenaga medis segera. Ukur ulang dengan termometer "
                "yang benar, dan segera cari pertolongan medis (IGD/fasilitas kesehatan terdekat), terutama jika "
                "disertai menggigil hebat, lemas, mengantuk berat, atau kebingungan."
            )
            peringatan_mendesak.append(msg)
            peringatan_suhu.append(msg)
            tanda_bahaya.append(f"suhu tubuh rendah ({tampil}, di bawah 35°C)")
        elif kode == "sangat_tinggi_mendesak":
            msg = (
                f"PERINGATAN MEDIS MENDESAK: suhu tubuh yang Anda laporkan ({tampil}) sangat tinggi (40°C atau lebih). "
                "Segera cari pertolongan medis (IGD/fasilitas kesehatan terdekat)."
            )
            peringatan_mendesak.append(msg)
            peringatan_suhu.append(msg)
            tanda_bahaya.append(f"suhu tubuh sangat tinggi ({tampil})")
        elif kode == "demam_tinggi":
            peringatan_suhu.append(
                f"Suhu {tampil} termasuk demam tinggi. Pertimbangkan segera berkonsultasi dengan dokter, "
                "terutama bila berlangsung lebih dari 3 hari atau disertai gejala berat."
            )

        # Cross-check against what the user said.
        if stated_demam and c < TEMP_FEVER_C:
            konflik.append(
                f"Anda menyebut demam, tetapi suhu yang dilaporkan ({tampil}) berada di bawah batas demam (37,5°C)."
            )
            pertanyaan.append(
                f"Anda menyebut demam namun suhu tercatat {tampil}. Apakah angka tersebut hasil pengukuran termometer, "
                "dan bagian tubuh mana yang diukur? Mohon ukur ulang."
            )
        if demam_negated and c >= TEMP_FEVER_C:
            konflik.append(
                f"Anda menyatakan tidak demam, tetapi suhu yang dilaporkan ({tampil}) menunjukkan peningkatan suhu."
            )
            pertanyaan.append(
                f"Anda menyatakan tidak demam namun suhu tercatat {tampil}. Mohon konfirmasi mana yang benar."
            )

        # Infer "demam" ONLY from a reported temperature at/above the fever threshold.
        if c >= TEMP_FEVER_C and not stated_demam and not demam_negated:
            positives.append(
                {
                    "key": "demam",
                    "nama": "demam",
                    "jenis": f"peningkatan suhu tubuh (disimpulkan dari angka suhu {tampil}; bukan diagnosis)",
                    "status": "disimpulkan_dari_suhu",
                    "teks_asli": primary_temp["teks_asli"],
                }
            )
            seen_pos.add("demam")
        if not primary_temp["satuan_eksplisit"]:
            informasi_belum_jelas.append(
                f"Satuan suhu tidak disebutkan eksplisit; angka {primary_temp['nilai_asli']} dibaca sebagai °C."
            )
    elif stated_demam and not temps:
        informasi_belum_jelas.append("Angka suhu tubuh terukur belum disebutkan.")

    # 5. Cough & Haid characteristics / ambiguity.
    if "batuk_kering" in seen_pos and "batuk_berdahak" in seen_pos:
        informasi_belum_jelas.append("Anda menyebut batuk kering sekaligus berdahak; jenis batuk yang dominan belum jelas.")
        pertanyaan.insert(0, "Anda menyebut batuk kering dan berdahak. Batuk mana yang paling dominan saat ini?")
    if "batuk" in seen_pos:
        informasi_belum_jelas.append("Jenis batuk (kering atau berdahak) belum disebutkan.")
        pertanyaan.append("Apakah batuk yang Anda alami kering (tanpa dahak) atau berdahak?")

    if "haid_ambigu" in seen_pos:
        informasi_belum_jelas.append(
            "Anda menyebutkan kondisi haid/menstruasi, tetapi belum merinci keluhan spesifik yang dirasakan."
        )
        pertanyaan.insert(
            0,
            "Apakah keluhan menstruasi yang Anda alami berupa nyeri haid (kram/dismenore) atau siklus haid yang tidak teratur / terlambat?"
        )

    # 6. Danger signs from keywords (negation aware).
    kw_hits = find_unnegated_keywords(low, emergency_keywords or [])
    for kw in kw_hits:
        if kw not in tanda_bahaya:
            tanda_bahaya.append(kw)

    # 7. Primary / additional roles.
    reported = [p for p in positives if p["status"] == "dilaporkan"]
    ordered = reported + [p for p in positives if p["status"] != "dilaporkan"]
    for idx, p in enumerate(ordered):
        p["peran"] = "utama" if idx == 0 else "tambahan"

    return {
        "keluhan": ordered,
        "keluhan_dinegasikan": negated,
        "symptom_keys": [p["key"] for p in ordered],
        "symptom_labels": [p["nama"] for p in ordered],
        "suhu_tubuh": primary_temp,
        "suhu_semua": temps,
        "konflik": konflik,
        "informasi_belum_jelas": informasi_belum_jelas,
        "pertanyaan_klarifikasi": pertanyaan,
        "tanda_bahaya": tanda_bahaya,
        "tanda_bahaya_kata_kunci": kw_hits,
        "peringatan_suhu": peringatan_suhu,
        "peringatan_mendesak": " ".join(peringatan_mendesak) if peringatan_mendesak else None,
        "instruksi_ramuan_dihentikan": bool(tanda_bahaya),
        "perlu_klarifikasi": bool(pertanyaan or "haid_ambigu" in seen_pos or "batuk" in seen_pos),
        "is_haid_ambigu": "haid_ambigu" in seen_pos,
    }


def recipe_symptom_compatibility(symptom_key: str, recipe_complaint: str) -> str:
    """Compare one recognised symptom with a recipe's documented complaint text.

    Returns one of: "tepat", "umum", "konflik", "tidak_terkait".
    Precedence: exact > conflict > generic.
    """
    sd = SYMPTOM_BY_KEY.get(symptom_key)
    if sd is None:
        return "tidak_terkait"
    low = (recipe_complaint or "").lower()
    if re.search(sd.exact, low):
        return "tepat"
    if re.search(sd.conflict, low):
        return "konflik"
    if re.search(sd.generic, low):
        return "umum"
    return "tidak_terkait"
