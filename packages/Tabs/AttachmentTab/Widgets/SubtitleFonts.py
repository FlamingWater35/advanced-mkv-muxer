import os
import re

from packages.Tabs.GlobalSetting import GlobalSetting

FONT_FILE_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc")
SUBTITLE_FILE_EXTENSIONS = (".ass", ".ssa", ".srt", ".vtt")

# "Style: Default,Arial,20,&H00FFFFFF,..." -> the second field is the font name.
STYLE_LINE_PATTERN = re.compile(r"^\s*Style:\s*([^,\r\n]*),([^,\r\n]*)", re.IGNORECASE | re.MULTILINE)
# "{\fnArial\b1}" and "{\fnArial Bold}" inline overrides.
INLINE_FONT_PATTERN = re.compile(r"\\fn([^\\}]+)", re.IGNORECASE)
# "<font face="Arial">" as used by some SRT files.
HTML_FONT_PATTERN = re.compile(r"<font\s+face\s*=\s*[\"']?([^\"'>]+)", re.IGNORECASE)

_font_cache = {}


def normalize_font_key(text):
    """Reduce a font name or file name to a comparable key.

    "Open Sans-Bold" and "OpenSansBold.ttf" both become "opensansbold", which
    is how subtitles and font files are matched in practice.
    """
    return re.sub(r"[^0-9a-z]+", "", str(text or "").lower())


def get_font_names_from_subtitle_text(text):
    font_names = set()
    for match in STYLE_LINE_PATTERN.finditer(text):
        font_name = match.group(2).strip()
        if font_name != "":
            font_names.add(font_name)
    for match in INLINE_FONT_PATTERN.finditer(text):
        font_name = match.group(1).strip().rstrip("}")
        if font_name != "":
            font_names.add(font_name)
    for match in HTML_FONT_PATTERN.finditer(text):
        font_name = match.group(1).strip()
        if font_name != "":
            font_names.add(font_name)
    return font_names


def get_font_names_from_subtitle_file(file_absolute_path):
    """Read the fonts a subtitle file asks for, cached by path and mtime."""
    try:
        modification_time = os.path.getmtime(file_absolute_path)
    except OSError:
        return set()
    cache_key = (os.path.normcase(file_absolute_path), modification_time)
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    if os.path.splitext(file_absolute_path)[1].lower() not in SUBTITLE_FILE_EXTENSIONS:
        return set()
    try:
        with open(file_absolute_path, "r", encoding="utf-8-sig", errors="replace") as subtitle_file:
            text = subtitle_file.read()
    except OSError:
        return set()
    font_names = get_font_names_from_subtitle_text(text)
    _font_cache[cache_key] = font_names
    return font_names


def get_font_names_from_subtitle_files(subtitle_absolute_paths):
    font_names = set()
    for subtitle_absolute_path in subtitle_absolute_paths:
        font_names |= get_font_names_from_subtitle_file(subtitle_absolute_path)
    return font_names


def is_font_file(file_absolute_path):
    return os.path.splitext(file_absolute_path)[1].lower() in FONT_FILE_EXTENSIONS


def get_font_files_in_folders(folder_paths, include_subfolders=True):
    """Collect every font file below the given folders, once each."""
    font_files = []
    seen_folders = set()
    for folder_path in folder_paths:
        if not folder_path or not os.path.isdir(folder_path):
            continue
        key = os.path.normcase(os.path.abspath(folder_path))
        if key in seen_folders:
            continue
        seen_folders.add(key)
        if not include_subfolders:
            for file_name in sorted(os.listdir(folder_path)):
                file_absolute_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_absolute_path) and is_font_file(file_absolute_path):
                    font_files.append(file_absolute_path)
            continue
        for root_folder, _, file_names in os.walk(folder_path):
            for file_name in sorted(file_names):
                if is_font_file(file_name):
                    font_files.append(os.path.join(root_folder, file_name))
    return font_files


def font_file_matches_names(font_absolute_path, font_keys):
    """True when the file name of a font belongs to one of the wanted fonts."""
    file_key = normalize_font_key(os.path.splitext(os.path.basename(font_absolute_path))[0])
    if file_key == "":
        return False
    for font_key in font_keys:
        # "Arial" has to match "arial.ttf", "arialbd.ttf" and "Arial Bold.ttf".
        if font_key.startswith(file_key) or file_key.startswith(font_key) or font_key in file_key:
            return True
    return False


def find_font_files_for_names(font_names, folder_paths, include_subfolders=True):
    """Return the font files below the folders that provide the wanted fonts."""
    font_keys = [normalize_font_key(font_name) for font_name in font_names]
    font_keys = [font_key for font_key in font_keys if font_key != ""]
    if len(font_keys) == 0:
        return []
    matching_files = []
    for font_absolute_path in get_font_files_in_folders(folder_paths, include_subfolders):
        if font_file_matches_names(font_absolute_path, font_keys):
            matching_files.append(font_absolute_path)
    return matching_files


def get_subtitle_folders(subtitle_absolute_paths):
    folders = []
    for subtitle_absolute_path in subtitle_absolute_paths:
        folder_path = os.path.dirname(subtitle_absolute_path)
        if folder_path not in folders:
            folders.append(folder_path)
    return folders


def get_font_search_folders(job):
    """Folders scanned for subtitle fonts: the subtitles' folders, then the
    selected attachment folder (#160)."""
    folders = get_subtitle_folders(getattr(job, "subtitle_name_absolute", []))
    for folder_path in GlobalSetting.ATTACHMENT_SEARCH_FOLDERS:
        if folder_path not in folders:
            folders.append(folder_path)
    video_folder_path = os.path.dirname(getattr(job, "video_name_absolute", "") or "")
    if video_folder_path != "" and video_folder_path not in folders:
        folders.append(video_folder_path)
    return folders


def get_subtitle_font_attachments(job):
    """Font files used by the subtitles of this job, ready to be attached.

    Only subtitle fonts that exist on disk are returned; a font that cannot be
    found is silently skipped, so enabling the option is always safe.
    """
    subtitle_absolute_paths = [path for path in getattr(job, "subtitle_name_absolute", [])
                               if os.path.isfile(path)]
    if len(subtitle_absolute_paths) == 0:
        return []
    font_names = get_font_names_from_subtitle_files(subtitle_absolute_paths)
    if len(font_names) == 0:
        return []
    font_files = find_font_files_for_names(font_names, get_font_search_folders(job))
    already_attached = {os.path.normcase(os.path.abspath(path))
                        for path in getattr(job, "attachments_absolute_path", [])}
    result = []
    for font_file in font_files:
        if os.path.normcase(os.path.abspath(font_file)) in already_attached:
            continue
        already_attached.add(os.path.normcase(os.path.abspath(font_file)))
        result.append(font_file)
    return result
