import hashlib
import os
import re

from packages.Startup import GlobalFiles

MATROSKA_TIME_PATTERN = re.compile(r"(<ChapterTime(?:Start|End)>)([^<]*)(</ChapterTime(?:Start|End)>)")
MATROSKA_FIRST_START_PATTERN = re.compile(r"<ChapterTimeStart>([^<]*)</ChapterTimeStart>")
OGM_TIME_PATTERN = re.compile(r"^(CHAPTER\d+)=([0-9:.]*)$", re.MULTILINE)

MATROSKA_TIME_FORMAT = "%(hours)02d:%(minutes)02d:%(seconds)02d.%(nanoseconds)09d"


def get_chapter_delay_folder_path():
    folder_path = os.path.join(os.path.abspath(GlobalFiles.AppDataFolderPath), "Chapters")
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def parse_chapter_time(text):
    """Return the time of a chapter timestamp in nanoseconds, or None."""
    text = str(text or "").strip()
    if text == "":
        return None
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_text = parts[2]
        if "." in seconds_text:
            seconds_part, fraction_part = seconds_text.split(".", 1)
        else:
            seconds_part, fraction_part = seconds_text, ""
        seconds = int(seconds_part)
        fraction_part = (fraction_part + "000000000")[:9]
        nanoseconds = int(fraction_part)
    except ValueError:
        return None
    if minutes < 0 or seconds < 0 or hours < 0:
        return None
    return ((hours * 60 + minutes) * 60 + seconds) * 1000000000 + nanoseconds


def format_chapter_time(nanoseconds, fraction_digits=9):
    nanoseconds = max(0, int(nanoseconds))
    seconds, nanoseconds = divmod(nanoseconds, 1000000000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    fraction_digits = max(0, min(9, int(fraction_digits)))
    fraction_text = ("%09d" % nanoseconds)[:fraction_digits]
    return "%02d:%02d:%02d" % (hours, minutes, seconds) + (("." + fraction_text) if fraction_digits else "")


def get_fraction_digits(text):
    """Number of digits after the dot of a chapter timestamp, 9 by default."""
    text = str(text or "").strip()
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def shift_nanoseconds(nanoseconds, delay_nanoseconds):
    return max(0, int(nanoseconds) + int(delay_nanoseconds))


def shift_chapter_xml(text, delay_milliseconds, pin_first_chapter=True):
    """Shift every chapter timestamp by delay_milliseconds.

    The very first chapter start is left untouched when it is 0, because a
    finished file should still start with chapter 1 at 00:00:00 even after a
    positive delay (#111). Negative results are clamped to 0.
    """
    delay_nanoseconds = int(delay_milliseconds) * 1000000
    first_start = MATROSKA_FIRST_START_PATTERN.search(text)
    pinned_start = None
    if pin_first_chapter and first_start is not None:
        first_value = parse_chapter_time(first_start.group(1))
        if first_value == 0:
            pinned_start = first_start.group(1)

    def matched_text_is_first_start(match):
        return match.group(1) == "<ChapterTimeStart>" and match.group(2) == pinned_start

    def replace(match):
        original = parse_chapter_time(match.group(2))
        if original is None:
            return match.group(0)
        if pinned_start is not None and matched_text_is_first_start(match):
            return match.group(0)
        return match.group(1) + format_chapter_time(shift_nanoseconds(original, delay_nanoseconds)) + match.group(3)

    return MATROSKA_TIME_PATTERN.sub(replace, text)


def shift_chapter_ogm_text(text, delay_milliseconds, pin_first_chapter=True):
    """Same as shift_chapter_xml() for the chapter formats mkvmerge also reads."""
    delay_nanoseconds = int(delay_milliseconds) * 1000000
    matches = list(OGM_TIME_PATTERN.finditer(text))
    pinned_line = None
    if pin_first_chapter and len(matches) > 0:
        first_value = parse_chapter_time(matches[0].group(2))
        if first_value == 0:
            pinned_line = matches[0].group(0)

    def replace(match):
        if pinned_line is not None and match.group(0) == pinned_line:
            return match.group(0)
        original = parse_chapter_time(match.group(2))
        if original is None:
            return match.group(0)
        return match.group(1) + "=" + format_chapter_time(shift_nanoseconds(original, delay_nanoseconds),
                                                          get_fraction_digits(match.group(2)))

    return OGM_TIME_PATTERN.sub(replace, text)


def is_matroska_chapter_xml(text):
    return "<ChapterTimeStart>" in text


def shift_chapter_text(text, delay_milliseconds, pin_first_chapter=True):
    if is_matroska_chapter_xml(text):
        return shift_chapter_xml(text, delay_milliseconds, pin_first_chapter)
    return shift_chapter_ogm_text(text, delay_milliseconds, pin_first_chapter)


def get_shifted_chapters_file_path(job, delay_milliseconds):
    """Write a delayed copy of the chapter file of this job and return its path.

    The original chapter file of the user is never modified, so the queue can
    be re-run with another delay. An empty string means "use the original
    file", which is also the fallback when the file cannot be read.
    """
    original_path = job.chapter_name_absolute
    if not os.path.isfile(original_path):
        return ""
    try:
        with open(original_path, "r", encoding="utf-8-sig", errors="replace") as chapter_file:
            text = chapter_file.read()
    except OSError:
        return ""
    shifted_text = shift_chapter_text(text, delay_milliseconds)
    extension = os.path.splitext(original_path)[1]
    if extension == "":
        extension = ".xml"
    file_name = hashlib.sha1((str(original_path) + "|" + str(delay_milliseconds))
                             .encode("utf-8")).hexdigest() + extension
    shifted_path = os.path.join(get_chapter_delay_folder_path(), file_name)
    try:
        with open(shifted_path, "w", encoding="utf-8", newline="") as chapter_file:
            chapter_file.write(shifted_text)
    except OSError:
        return ""
    return shifted_path
