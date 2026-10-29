"""Detect a language from a subtitle/audio file name (#55).

MKVToolNix guesses the language of a file from its name ("Show.S01E01.en.srt").
The upstream author narrowed this request to a per-tab rule: every subtitle tab
points at the same folder and keeps only the files whose name carries the
language of that tab, so a folder of "english.srt / arabic.srt / japanese.srt"
fills three tabs in one go.

The tables are derived from ``Resources/Languages/iso639_language_list.json``
(display name -> ISO 639-2/B code), so the detected names always match the
names offered by the language combination boxes.
"""

import os
import re

from packages.Startup.PreDefined import ISO_639_2_LANGUAGES

# ISO 639-1 -> ISO 639-2 codes. Both the /B and the /T code of a language are
# accepted, because file names are written by hand and use either one
# ("ger" and "deu" both mean German).
TWO_LETTER_LANGUAGE_CODES = {
    "aa": ("aar",), "ab": ("abk",), "af": ("afr",), "ak": ("aka",), "am": ("amh",),
    "an": ("arg",), "ar": ("ara",), "as": ("asm",), "av": ("ava",), "ay": ("aym",),
    "az": ("aze",), "ba": ("bak",), "be": ("bel",), "bg": ("bul",), "bi": ("bis",),
    "bm": ("bam",), "bn": ("ben",), "bo": ("tib", "bod"), "br": ("bre",), "bs": ("bos",),
    "ca": ("cat",), "ce": ("che",), "co": ("cos",), "cs": ("cze", "ces"), "cu": ("chu",),
    "cv": ("chv",), "cy": ("wel", "cym"), "da": ("dan",), "de": ("ger", "deu"),
    "dv": ("div",), "dz": ("dzo",), "ee": ("ewe",), "el": ("gre", "ell"), "en": ("eng",),
    "eo": ("epo",), "es": ("spa",), "et": ("est",), "eu": ("baq", "eus"), "fa": ("per", "fas"),
    "ff": ("ful",), "fi": ("fin",), "fj": ("fij",), "fo": ("fao",), "fr": ("fre", "fra"),
    "fy": ("fry",), "ga": ("gle",), "gd": ("gla",), "gl": ("glg",), "gn": ("grn",),
    "gu": ("guj",), "ha": ("hau",), "he": ("heb",), "hi": ("hin",), "hr": ("hrv",),
    "ht": ("hat",), "hu": ("hun",), "hy": ("arm", "hye"), "hz": ("her",), "ia": ("ina",),
    "id": ("ind",), "ig": ("ibo",), "ii": ("iii",), "ik": ("ipk",), "is": ("ice", "isl"),
    "it": ("ita",), "iu": ("iku",), "ja": ("jpn",), "jv": ("jav",), "ka": ("geo", "kat"),
    "kk": ("kaz",), "kl": ("kal",), "km": ("khm",), "kn": ("kan",), "ko": ("kor",),
    "ks": ("kas",), "ku": ("kur",), "kv": ("kom",), "kw": ("cor",), "ky": ("kir",),
    "la": ("lat",), "lb": ("ltz",), "lg": ("lug",), "li": ("lim",), "ln": ("lin",),
    "lo": ("lao",), "lt": ("lit",), "lu": ("lub",), "lv": ("lav",), "mg": ("mlg",),
    "mi": ("mao", "mri"), "mk": ("mac", "mkd"), "ml": ("mal",), "mn": ("mon",),
    "mr": ("mar",), "ms": ("may", "msa"), "mt": ("mlt",), "my": ("bur", "mya"),
    "nb": ("nob",), "nd": ("nde",), "ne": ("nep",), "nl": ("dut", "nld"), "nn": ("nno",),
    "no": ("nor",), "ny": ("nya",), "oc": ("oci",), "om": ("orm",), "or": ("ori",),
    "pa": ("pan",), "pl": ("pol",), "ps": ("pus",), "pt": ("por",), "qu": ("que",),
    "rm": ("roh",), "ro": ("rum", "ron"), "ru": ("rus",), "rw": ("kin",), "sa": ("san",),
    "sd": ("snd",), "se": ("sme",), "sg": ("sag",), "si": ("sin",), "sk": ("slo", "slk"),
    "sl": ("slv",), "so": ("som",), "sq": ("alb", "sqi"), "sr": ("srp",), "ss": ("ssw",),
    "st": ("sot",), "su": ("sun",), "sv": ("swe",), "sw": ("swa",), "ta": ("tam",),
    "te": ("tel",), "tg": ("tgk",), "th": ("tha",), "ti": ("tir",), "tk": ("tuk",),
    "tl": ("tgl",), "tn": ("tsn",), "tr": ("tur",), "ts": ("tso",), "tt": ("tat",),
    "ug": ("uig",), "uk": ("ukr",), "ur": ("urd",), "uz": ("uzb",), "vi": ("vie",),
    "wo": ("wol",), "xh": ("xho",), "yi": ("yid",), "yo": ("yor",), "zh": ("chi", "zho"),
    "zu": ("zul",),
}

# Two letter codes that are also ordinary English words. They are only trusted
# when nothing else in the name can be recognised ("it.srt" is not Italian).
AMBIGUOUS_TWO_LETTER_CODES = ("it", "no", "is", "as", "be", "in", "to", "so", "my", "am", "an", "si", "la", "id")


def tokenize_file_name(text):
    """Split a name into lower-case word tokens ("Show.E01.EN.srt" -> [show, e01, en])."""
    return re.sub(r"[^0-9A-Za-z]+", " ", str(text)).lower().split()


def use_display_name_as_tokens(display_name):
    """Tokens a file name would use for a language display name.

    The bundled list is written in the ISO registry style, with alternatives
    separated by ';', regions in brackets and old forms after a comma
    ("Greek, Ancient (to 1453)"), so it needs cleaning before it can be matched
    against a file name ("Ancient Greek.srt").
    """
    text = str(display_name).split(";")[0]
    text = re.sub(r"\([^)]*\)", " ", text)
    tokens = tokenize_file_name(text)
    return [token for token in tokens if not re.search(r"\d", token)]


def normalize_language_name(language_name):
    """Canonical form used to compare a detected language with a chosen one."""
    tokens = use_display_name_as_tokens(language_name)
    if len(tokens) == 0:
        tokens = tokenize_file_name(language_name)
    return " ".join(tokens)


_language_tables = None


def get_language_tables():
    """Build (single token map, multi token list, two letter map) from the resource."""
    global _language_tables
    if _language_tables is not None:
        return _language_tables
    single_token_languages = {}
    multiple_token_languages = []
    three_letter_codes = {}
    for display_name, code in ISO_639_2_LANGUAGES.items():
        three_letter_codes.setdefault(str(code).lower(), display_name)
        tokens = use_display_name_as_tokens(display_name)
        if len(tokens) == 1:
            single_token_languages.setdefault(tokens[0], display_name)
        elif len(tokens) > 1:
            multiple_token_languages.append((tuple(tokens), display_name))
            if "," in str(display_name):
                # "Greek, Modern" is written "Modern Greek" in a file name.
                multiple_token_languages.append((tuple(reversed(tokens)), display_name))
    for code, display_name in three_letter_codes.items():
        single_token_languages[code] = display_name
    two_letter_codes = {}
    for code, alternatives in TWO_LETTER_LANGUAGE_CODES.items():
        display_name = None
        for alternative in alternatives:
            display_name = display_name or three_letter_codes.get(alternative)
        if display_name is None:
            continue
        two_letter_codes[code] = display_name
        # The /T alternative of a /B code is not in the bundled list, but file
        # names use it too ("deu.srt").
        for alternative in alternatives:
            single_token_languages.setdefault(alternative, display_name)
    multiple_token_languages.sort(key=lambda item: len(item[0]), reverse=True)
    _language_tables = (single_token_languages, multiple_token_languages, two_letter_codes)
    return _language_tables


def detect_language_from_file_name(file_name):
    """Return the display name of the language found in a file name, or None."""
    single_token_languages, multiple_token_languages, two_letter_codes = get_language_tables()
    tokens = tokenize_file_name(os.path.splitext(os.path.basename(str(file_name)))[0])
    if len(tokens) == 0:
        return None
    for wanted_tokens, display_name in multiple_token_languages:
        length = len(wanted_tokens)
        for start in range(len(tokens) - length + 1):
            if tuple(tokens[start:start + length]) == wanted_tokens:
                return display_name
    for token in tokens:
        if len(token) > 2 and token in single_token_languages:
            return single_token_languages[token]
    for token in tokens:
        if token in AMBIGUOUS_TWO_LETTER_CODES:
            continue
        if token in two_letter_codes:
            return two_letter_codes[token]
    return None


def is_language_detectable(language_name):
    """True when the name can be recognised in a file name at all."""
    normalized = normalize_language_name(language_name)
    if normalized == "":
        return False
    single_token_languages, multiple_token_languages, _ = get_language_tables()
    if normalized in single_token_languages:
        return True
    normalized_tokens = tuple(normalized.split())
    for wanted_tokens, _ in multiple_token_languages:
        if wanted_tokens == normalized_tokens:
            return True
    return False


def file_name_matches_language(file_name, language_name):
    """True when the file name carries the given language (the #55 rule)."""
    if not is_language_detectable(language_name):
        # Unrecognised language name: never hide files because of it.
        return True
    detected_language = detect_language_from_file_name(file_name)
    if detected_language is None:
        return False
    return normalize_language_name(detected_language) == normalize_language_name(language_name)
