import os
import re

from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.Widgets.JobOutputFiles import get_output_folder_path

CRC_PLACEHOLDER = "%crc%"
VIDEO_EXTENSION = ".mkv"

# %name% -> short description, used by the tooltip of the pattern field.
OUTPUT_NAME_VARIABLES = (
    ("%source%", "source file name without extension"),
    ("%episode%", "queue position, zero padded to two digits"),
    ("%resolution%", "video dimensions, for example 1920x1080"),
    ("%videocodec%", "codec of the source video track"),
    ("%audiocodec%", "codec of the first audio track"),
    ("%audiolang%", "language of the first attached audio"),
    ("%sublang%", "language of the first attached subtitle"),
    (CRC_PLACEHOLDER, "CRC32 of the finished file"),
)

PATTERN_VARIABLE_PATTERN = re.compile(r"%[a-z]+%")
INVALID_FILE_NAME_CHARACTERS = '<>:"/\\|?*'


def get_output_name_variables_tooltip():
    lines = ["Variables:"]
    for variable, description in OUTPUT_NAME_VARIABLES:
        lines.append("  " + variable + " - " + description)
    lines.append("")
    lines.append("Write the name without the .mkv extension.")
    return "\n".join(lines)


def get_source_base_name(job):
    return os.path.splitext(os.path.basename(job.video_name))[0]


def get_first_attached_language(languages):
    for language in languages:
        if str(language).strip() != "":
            return str(language).strip()
    return ""


def get_output_name_variables(job, resolution="", video_codec="", audio_codec=""):
    """Build the %variable% table for one job.

    Values are only taken from data the queue already holds: the track list of
    the source file and the tracks the user attached to this job (#111).
    """
    return {
        "%source%": get_source_base_name(job),
        "%episode%": ("%02d" % int(job.queue_index or 0)) if int(job.queue_index or 0) > 0 else "01",
        "%resolution%": str(resolution or ""),
        "%videocodec%": str(video_codec or ""),
        "%audiocodec%": str(audio_codec or ""),
        "%audiolang%": get_first_attached_language(getattr(job, "audio_language", [])),
        "%sublang%": get_first_attached_language(getattr(job, "subtitle_language", [])),
        CRC_PLACEHOLDER: "",
    }


def remove_empty_brackets(text):
    """Drop "[ ]" style leftovers of a variable that resolved to nothing."""
    bracket_patterns = (r"\[\s*\]", r"\(\s*\)", r"\{\s*\}", r"<\s*>")
    previous_text = None
    while previous_text != text:
        previous_text = text
        for bracket_pattern in bracket_patterns:
            text = re.sub(bracket_pattern, "", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def sanitize_output_file_name(text):
    """Make a file name that Windows, Linux and mkvmerge all accept."""
    file_name = str(text)
    for character in INVALID_FILE_NAME_CHARACTERS:
        file_name = file_name.replace(character, "_")
    file_name = file_name.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    file_name = re.sub(r"[ ]{2,}", " ", file_name)
    file_name = file_name.strip().strip(".")
    return file_name


def is_output_name_pattern_valid(pattern):
    return str(pattern or "").strip() != ""


def apply_output_name_pattern(job, pattern, resolution="", video_codec="", audio_codec="",
                              keep_crc_placeholder=False):
    """Resolve the pattern of one job into a file name with the .mkv extension.

    An empty pattern returns an empty string, which means "keep the source
    name" and is the default behaviour of the app.
    """
    pattern = str(pattern or "")
    if not is_output_name_pattern_valid(pattern):
        return ""
    variables = get_output_name_variables(job, resolution=resolution, video_codec=video_codec,
                                          audio_codec=audio_codec)
    if keep_crc_placeholder:
        # The CRC is only known after muxing, so the literal token is written
        # into the intermediate name and replaced by apply_crc_to_output_name().
        variables[CRC_PLACEHOLDER] = CRC_PLACEHOLDER
    file_name = pattern
    for variable, value in variables.items():
        file_name = file_name.replace(variable, value)
    file_name = remove_empty_brackets(file_name)
    file_name = sanitize_output_file_name(file_name)
    if file_name == "":
        return ""
    if not file_name.lower().endswith(VIDEO_EXTENSION):
        file_name += VIDEO_EXTENSION
    return file_name


def get_unknown_pattern_variables(pattern):
    return sorted(set(PATTERN_VARIABLE_PATTERN.findall(str(pattern or ""))) -
                  {variable for variable, _ in OUTPUT_NAME_VARIABLES})


def make_output_name_unique(job):
    """Keep two jobs of the same queue from writing the same file.

    A constant pattern such as "converted" would make every job overwrite the
    previous one, so a counter is appended instead. Names are registered in
    GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES, which the queue resets when a
    new run starts.

    The key is the *output* folder, not the folder of the source file: with an
    absolute destination every job of the queue writes into the same folder, so
    two same-named episodes from different seasons collide there.
    """
    name = str(getattr(job, "custom_output_name", "")).strip()
    if name == "":
        return ""
    used_names = GlobalSetting.MUX_SETTING_USED_OUTPUT_NAMES
    output_folder_path = os.path.normcase(os.path.abspath(get_output_folder_path(job)))
    key = (output_folder_path, name.lower())
    if key not in used_names:
        used_names.add(key)
        return name
    base_name, extension = os.path.splitext(name)
    counter = 2
    while True:
        candidate = base_name + " (" + str(counter) + ")" + extension
        candidate_key = (key[0], candidate.lower())
        if candidate_key not in used_names:
            used_names.add(candidate_key)
            job.custom_output_name = candidate
            return candidate
        counter += 1
