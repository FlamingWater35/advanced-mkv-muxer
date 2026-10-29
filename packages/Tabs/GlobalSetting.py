# Here we have everything that must be shared between all tabs
import copy
import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from packages.Startup import GlobalFiles
from packages.Startup.PreDefined import ISO_639_2_SYMBOLS
from packages.Widgets.PathData import PathData
from packages.Widgets.SingleOldTrackData import SingleOldTrackData


def convert_string_integer_to_two_digit_string(value):
    s = str(value)
    if len(s) >= 2:
        return s
    else:
        return "0" + s


def get_attribute(data, attribute, default_value):
    return data.get(attribute) or default_value


def sort_names_like_windows(names_list):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(names_list, key=alphanum_key)


def generate_track_ids(ids_list):
    res = []
    for i in ids_list:
        res.append("Track " + str(i))
    return res


# Section headers of the "Only Keep Those ..." / "Make This ... Default"
# menus. Every one of them is a non selectable separator row.
TRACK_SECTION_ORDER = "---Track Order---"
TRACK_SECTION_TRACK_ID = "---Track Id---"
TRACK_SECTION_LANGUAGE = "---Language---"
TRACK_SECTION_FORMAT = "---Format---"
TRACK_SECTION_TRACK_NAME = "---Track Name---"


def is_track_menu_section(text):
    """True for a section header row of a track menu."""
    text = str(text)
    return text.startswith("---") and text.endswith("---")


def generate_track_id_with_language(track_id, language_name):
    """A "Track Id" entry that also shows the language of the track (#139)."""
    return "Track " + str(track_id) + " - " + str(language_name)


def get_track_id_from_menu_entry(entry_text):
    """"Track 02 - French" -> "02"; None for anything else."""
    parts = str(entry_text).split(" ")
    if len(parts) < 2 or parts[0] != "Track":
        return None
    return parts[1]


def get_track_order_from_menu_entry(entry_text):
    """"Order 2" -> 2 (one based); None for anything else."""
    parts = str(entry_text).split(" ")
    if len(parts) != 2 or parts[0] != "Order":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def filter_track_menu_entries(texts, allowed_sections):
    """Keep the sections (and their entries) the caller can handle.

    The "Make This Track Default" menu cannot use the order/format sections, so
    it is fed a filtered copy of the shared track list.
    """
    result = []
    current_section = ""
    for text in texts:
        if is_track_menu_section(text):
            current_section = text
            if current_section in allowed_sections:
                result.append(text)
            continue
        if current_section in allowed_sections:
            result.append(text)
    return result


def get_readable_filesize(size_bytes, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(size_bytes) < 1024.0:
            return "%3.2f %s%s" % (size_bytes, unit, suffix)
        size_bytes /= 1024.0
    return "%.2f %s%s" % (size_bytes, 'Y', suffix)


def get_files_names_absolute_list(files_names, folder_path):
    result = []
    for i in range(len(files_names)):
        result.append(get_file_name_absolute_path(file_name=files_names[i], folder_path=folder_path))
    return result


def get_file_name_absolute_path(file_name, folder_path):
    return os.path.join(Path(folder_path), file_name)


def convert_string_to_boolean(string):
    if string in ["True", "true", "T", "t"]:
        return True
    else:
        return False


def reset_track_flags(flags):
    """Clear every per-track default/forced flag.

    Several tracks may be flagged at once, so a caller that takes over the
    flags (the "Make this ... default" mux options) has to clear all of them,
    not only the last one it finds.
    """
    for key in flags:
        flags[key] = False


EMPTY_MATCHING_SLOT = "<empty>"
EMPTY_MATCHING_SLOT_DISPLAY_NAME = "(empty)"


def is_empty_matching_slot(file_name):
    """True when this matching-list entry is a deliberately empty slot.

    A slot keeps the file lists aligned with the video list, so a subtitle or
    an audio file can be attached to a specific episode without shifting every
    later file up one row (#158, #120).
    """
    return file_name == EMPTY_MATCHING_SLOT


def insert_empty_matching_slot(files_list, absolute_path_list, index):
    """Insert an empty slot at index, keeping both lists the same length."""
    index = max(0, min(index, len(files_list)))
    files_list.insert(index, EMPTY_MATCHING_SLOT)
    absolute_path_list.insert(index, "")


def is_usable_matching_file(absolute_path, file_name, extensions):
    """True when this entry is a non-empty file this tab can use."""
    if not os.path.isfile(absolute_path):
        return False
    try:
        if os.path.getsize(absolute_path) == 0:
            return False
    except OSError:
        return False
    if extensions is None:
        return True
    extension_start_index = file_name.rfind(".")
    if extension_start_index == -1:
        return False
    file_extension = file_name[extension_start_index + 1:]
    for extension in extensions:
        if file_extension.lower() == extension.lower():
            return True
    return False


def get_matching_files_in_folder(folder_path, extensions=None, include_subfolders=False):
    """List the usable files of a source folder (#136, #157).

    With ``include_subfolders`` the whole tree is scanned and each name keeps
    its sub path ("Season 1/episode 1.srt"), so names stay unique and the
    absolute path can still be rebuilt with os.path.join. The order is
    depth-first with every folder and file sorted like Windows Explorer.
    """
    result = []
    if include_subfolders:
        for current_folder, folders_names, files_names in os.walk(folder_path):
            folders_names[:] = sort_names_like_windows(folders_names)
            for file_name in sort_names_like_windows(files_names):
                absolute_path = os.path.join(current_folder, file_name)
                if is_usable_matching_file(absolute_path, file_name, extensions):
                    result.append(os.path.relpath(absolute_path, folder_path))
    else:
        for file_name in sort_names_like_windows(os.listdir(folder_path)):
            absolute_path = os.path.join(folder_path, file_name)
            if is_usable_matching_file(absolute_path, file_name, extensions):
                result.append(file_name)
    return result


def convert_boolean_to_checked_value(value):
    if value is None:
        return 1  # Qt.CheckState.PartiallyChecked
    if value:
        return 2  # Qt.CheckState.Checked
    return 0  # Qt.CheckState.Unchecked


def convert_check_state_int_to_check_state(value):
    if value == 1:
        return Qt.CheckState.PartiallyChecked
    if value == 2:
        return Qt.CheckState.Checked
    return Qt.CheckState.Unchecked


def write_to_log_file(exception):
    logging.error(exception)


def refresh_tracks(track_type):
    videos = GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST.copy()
    new_list = []
    # Track ids keep the language they were found with, so the "Track Id"
    # entries can show it (#139).
    tracks_id_languages = {}
    tracks_languages = []
    tracks_names = []
    tracks_formats = []
    max_tracks_count = 0
    for video_name in videos:
        string_name_hash = hashlib.sha1((str(video_name)).encode('utf-8')).hexdigest()
        media_info_file_path = os.path.join(GlobalFiles.MediaInfoFolderPath, string_name_hash + ".json")
        with open(media_info_file_path, 'r', encoding="UTF-8") as media_info_file:
            json_info = json.load(media_info_file)
        tracks_json_info = json_info["tracks"]
        tracks_of_type = [track for track in tracks_json_info if track["type"] == track_type]
        max_tracks_count = max(max_tracks_count, len(tracks_of_type))
        for track in tracks_of_type:
            language = str(
                get_attribute(data=track["properties"], attribute="language", default_value="UND"))
            language_name = ISO_639_2_SYMBOLS.get(language.lower(), "Undetermined")
            track_id = convert_string_integer_to_two_digit_string(str(track["id"]))
            if track_id not in tracks_id_languages:
                tracks_id_languages[track_id] = language_name
            tracks_languages.append(language_name)
            name = str(get_attribute(data=track["properties"], attribute="track_name",
                                     default_value="UnNamedTrackBeBo"))
            if name != "UnNamedTrackBeBo":
                tracks_names.append(name)
            codec = str(track.get("codec") or get_attribute(data=track["properties"], attribute="codec",
                                                            default_value=""))
            if codec != "":
                tracks_formats.append(codec)

    # The order of the tracks inside one file is what the user sees in a media
    # player, which is why it gets its own section (#141).
    tracks_order = ["Order " + str(index + 1) for index in range(max_tracks_count)]
    tracks_languages = list(dict.fromkeys(tracks_languages))
    tracks_names = list(dict.fromkeys(tracks_names))
    tracks_formats = list(dict.fromkeys(tracks_formats))
    tracks_languages.sort()
    tracks_names.sort()
    tracks_formats.sort()
    if len(tracks_order) > 0:
        new_list = [TRACK_SECTION_ORDER]
        new_list.extend(tracks_order)
    if len(tracks_id_languages) > 0:
        new_list.append(TRACK_SECTION_TRACK_ID)
        for track_id in sorted(tracks_id_languages.keys()):
            new_list.append(generate_track_id_with_language(track_id, tracks_id_languages[track_id]))
    if len(tracks_languages) > 0:
        new_list.append(TRACK_SECTION_LANGUAGE)
        new_list.extend(tracks_languages)
    if len(tracks_formats) > 0:
        new_list.append(TRACK_SECTION_FORMAT)
        new_list.extend(tracks_formats)
    if len(tracks_names) > 0:
        new_list.append(TRACK_SECTION_TRACK_NAME)
        new_list.extend(tracks_names)
    return new_list


def refresh_old_tracks_info_as_bulk(tracks_info: List[List[SingleOldTrackData]]):
    tracks_bulk_data = defaultdict(SingleOldTrackData)
    track_dict = {}
    for video_id, tracks_list in enumerate(tracks_info, start=1):
        for track in tracks_list:
            track_id = track.id
            if track_id not in track_dict.keys():
                track_dict[track_id] = defaultdict(SingleOldTrackData)
            single_old_track_data: SingleOldTrackData = SingleOldTrackData()
            single_old_track_data.id = track_id
            single_old_track_data.track_name = track.track_name
            single_old_track_data.language = track.language
            single_old_track_data.is_default = track.is_default
            single_old_track_data.is_forced = track.is_forced
            single_old_track_data.is_enabled = track.is_enabled
            track_dict[track_id][video_id] = single_old_track_data

    for order_id, track_id in enumerate(track_dict.keys()):
        temp_old_track_data = SingleOldTrackData()
        all_same = True
        for video_id in track_dict[track_id]:
            if temp_old_track_data.id == "":
                temp_old_track_data = track_dict[track_id][video_id]
            else:
                if temp_old_track_data.track_name != track_dict[track_id][video_id].track_name:
                    temp_old_track_data.track_name = "[Old]"
                if temp_old_track_data.language != track_dict[track_id][video_id].language:
                    temp_old_track_data.language = "[Old]"
                if temp_old_track_data.is_enabled != track_dict[track_id][video_id].is_enabled:
                    temp_old_track_data.is_enabled = None
                if temp_old_track_data.is_default != track_dict[track_id][video_id].is_default:
                    temp_old_track_data.is_default = None
                if temp_old_track_data.is_forced != track_dict[track_id][video_id].is_forced:
                    temp_old_track_data.is_forced = None
        if all_same:
            tracks_bulk_data[track_id] = temp_old_track_data
        else:
            temp_old_track_data.track_name = "[Old]"
            temp_old_track_data.language = "[Old]"
            tracks_bulk_data[track_id] = temp_old_track_data
        tracks_bulk_data[track_id].is_enabled = convert_boolean_to_checked_value(tracks_bulk_data[track_id].is_enabled)
        tracks_bulk_data[track_id].is_default = convert_boolean_to_checked_value(tracks_bulk_data[track_id].is_default)
        tracks_bulk_data[track_id].is_forced = convert_boolean_to_checked_value(tracks_bulk_data[track_id].is_forced)
        tracks_bulk_data[track_id].order = order_id
    return tracks_bulk_data


def refresh_old_tracks_info(track_type):
    videos = GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST.copy()
    new_list: List[List[SingleOldTrackData]] = []
    for video_name in videos:
        video_tracks: List[SingleOldTrackData] = []
        string_name_hash = hashlib.sha1((str(video_name)).encode('utf-8')).hexdigest()
        media_info_file_path = os.path.join(GlobalFiles.MediaInfoFolderPath, string_name_hash + ".json")
        with open(media_info_file_path, 'r', encoding="UTF-8") as media_info_file:
            json_info = json.load(media_info_file)
        tracks_json_info = json_info["tracks"]
        for track in tracks_json_info:
            new_track: SingleOldTrackData = SingleOldTrackData()
            if track["type"] == track_type:
                new_track.id = str(track["id"])
                language = str(
                    get_attribute(data=track["properties"], attribute="language", default_value="UND"))
                language_symbol = language.lower()
                new_track.language = ISO_639_2_SYMBOLS.get(language_symbol, "Undetermined")
                name = str(get_attribute(data=track["properties"], attribute="track_name",
                                         default_value="UnNamedTrackBeBo"))
                if name != "UnNamedTrackBeBo":
                    new_track.track_name = name
                new_track.is_default = get_attribute(data=track["properties"], attribute="default_track",
                                                     default_value=False)
                new_track.is_forced = get_attribute(data=track["properties"], attribute="forced_track",
                                                    default_value=False)
                new_track.is_enabled = True
                new_track.uid = str(
                    get_attribute(data=track["properties"], attribute="uid", default_value="-1"))
                video_tracks.append(new_track)
        new_list.append(video_tracks)
    if track_type == "audio":
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_INFO = new_list
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING_ORIGINAL = refresh_old_tracks_info_as_bulk(
            tracks_info=GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_INFO)
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING = copy.deepcopy(
            GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING_ORIGINAL)
    elif track_type == "subtitles":
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_INFO = new_list
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_BULK_SETTING_ORIGINAL = refresh_old_tracks_info_as_bulk(
            tracks_info=GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_INFO)
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_BULK_SETTING = copy.deepcopy(
            GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_BULK_SETTING_ORIGINAL)
    elif track_type == "video":
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_INFO = new_list
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_BULK_SETTING_ORIGINAL = refresh_old_tracks_info_as_bulk(
            tracks_info=GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_INFO)
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_BULK_SETTING = copy.deepcopy(
            GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_BULK_SETTING_ORIGINAL)


class GlobalSetting(QWidget):
    LAST_DIRECTORY_PATH = ""
    INCLUDE_SUBFOLDERS = False
    VIDEO_SOURCE_PATHS = []
    VIDEO_FILES_LIST = []
    VIDEO_FILES_SIZE_LIST = []
    VIDEO_FILES_ABSOLUTE_PATH_LIST = []
    VIDEO_SOURCE_MKV_ONLY = False
    VIDEO_DEFAULT_DURATION_FPS = ""
    VIDEO_FIX_BITSTREAM_TIMING_INFO = False
    VIDEO_OLD_TRACKS_VIDEOS_INFO: List[List[SingleOldTrackData]] = []
    VIDEO_OLD_TRACKS_AUDIOS_INFO: List[List[SingleOldTrackData]] = []
    VIDEO_OLD_TRACKS_SUBTITLES_INFO: List[List[SingleOldTrackData]] = []
    VIDEO_OLD_TRACKS_VIDEOS_BULK_SETTING_ORIGINAL = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING_ORIGINAL = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_SUBTITLES_BULK_SETTING_ORIGINAL = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_VIDEOS_BULK_SETTING = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_SUBTITLES_BULK_SETTING = defaultdict(SingleOldTrackData)
    VIDEO_OLD_TRACKS_VIDEOS_MODIFIED_ACTIVATED = False
    VIDEO_OLD_TRACKS_VIDEOS_REORDER_ACTIVATED = False
    VIDEO_OLD_TRACKS_VIDEOS_DELETED_ACTIVATED = False
    VIDEO_OLD_TRACKS_SUBTITLES_MODIFIED_ACTIVATED = False
    VIDEO_OLD_TRACKS_SUBTITLES_REORDER_ACTIVATED = False
    VIDEO_OLD_TRACKS_SUBTITLES_DELETED_ACTIVATED = False
    VIDEO_OLD_TRACKS_AUDIOS_MODIFIED_ACTIVATED = False
    VIDEO_OLD_TRACKS_AUDIOS_REORDER_ACTIVATED = False
    VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED = False

    SUBTITLE_ENABLED = False
    SUBTITLE_TAB_ENABLED = defaultdict(bool)
    SUBTITLE_FILES_LIST = defaultdict(list)
    SUBTITLE_FILES_ABSOLUTE_PATH_LIST = defaultdict(list)
    SUBTITLE_TRACK_NAME = defaultdict(str)
    SUBTITLE_DELAY = defaultdict(float)
    SUBTITLE_SET_DEFAULT = defaultdict(bool)
    SUBTITLE_SET_FORCED = defaultdict(bool)
    SUBTITLE_SET_ORDER = defaultdict(int)
    SUBTITLE_SET_DEFAULT_DISABLED = False
    SUBTITLE_SET_FORCED_DISABLED = False
    SUBTITLE_LANGUAGE = defaultdict(str)
    SUBTITLE_MATCH_LANGUAGE_BY_FILE_NAME = defaultdict(bool)

    AUDIO_ENABLED = False
    AUDIO_TAB_ENABLED = defaultdict(bool)
    AUDIO_FILES_LIST = defaultdict(list)
    AUDIO_FILES_ABSOLUTE_PATH_LIST = defaultdict(list)
    AUDIO_TRACK_NAME = defaultdict(str)
    AUDIO_DELAY = defaultdict(float)
    AUDIO_SET_DEFAULT = defaultdict(bool)
    AUDIO_SET_FORCED = defaultdict(bool)
    AUDIO_SET_ORDER = defaultdict(int)
    AUDIO_SET_DEFAULT_DISABLED = False
    AUDIO_SET_FORCED_DISABLED = False
    AUDIO_LANGUAGE = defaultdict(str)

    ATTACHMENT_ENABLED = False
    ATTACHMENT_FILES_LIST = []
    ATTACHMENT_FILES_CHECKING_LIST = []
    ATTACHMENT_FILES_ABSOLUTE_PATH_LIST = []
    ATTACHMENT_DISCARD_OLD = False
    ATTACHMENT_ALLOW_DUPLICATE = False

    ATTACHMENT_EXPERT_MODE = False
    ATTACHMENT_PATH_DATA_LIST: List[PathData] = []
    ATTACHMENT_AUTO_DETECT_FONTS = False
    ATTACHMENT_SEARCH_FOLDERS = []

    CHAPTER_ENABLED = False
    CHAPTER_FILES_LIST = []
    CHAPTER_FILES_ABSOLUTE_PATH_LIST = []
    CHAPTER_DISCARD_OLD = False
    CHAPTER_GENERATE_BY_INTERVAL = False
    CHAPTER_GENERATE_INTERVAL_SECONDS = 120
    CHAPTER_DELAY_MILLISECONDS = 0

    MUX_SETTING_AUDIO_TRACKS_LIST = []
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED = False
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_IDS = []
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_LANGUAGES = []
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_NAMES = []
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_ORDERS = []
    MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_FORMATS = []

    MUX_SETTING_SUBTITLE_TRACKS_LIST = []
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED = False
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_IDS = []
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_LANGUAGES = []
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_NAMES = []
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_ORDERS = []
    MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_FORMATS = []

    MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_SEMI_ENABLED = False
    MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_FULL_ENABLED = False
    MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_TRACK = ""

    MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_SEMI_ENABLED = False
    MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_FULL_ENABLED = False
    MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_TRACK = ""

    MUX_SETTING_ABORT_ON_ERRORS = False
    MUX_SETTING_KEEP_LOG_FILE = False
    MUX_SETTING_ADD_CRC = False
    MUX_SETTING_REMOVE_OLD_CRC = False
    MUX_SETTING_SET_TITLE_TO_FILE_NAME = False
    MUX_SETTING_DISCARD_ALL_TAGS = False
    MUX_SETTING_STOP_AFTER_VIDEO_ENDS = False
    MUX_SETTING_EXTRA_ARGUMENTS = ""
    MUX_SETTING_OUTPUT_NAME_PATTERN = ""
    MUX_SETTING_USED_OUTPUT_NAMES = set()

    DESTINATION_FOLDER_PATH = ""
    OVERWRITE_SOURCE_FILES = False
    OVERWRITE_TEMP_FOLDER_PATH = ""
    RANDOM_OUTPUT_SUFFIX = ""
    USE_MKVPROPEDIT = False

    JOB_QUEUE_EMPTY = True
    JOB_QUEUE_FINISHED = False
    MUXING_ON = False
    LogFilePath = ""
    DISABLE_TOOLTIP = "<b>[Disabled]</b> because job queue has unfinished job(s)"
    def __init__(self):
        super().__init__()
