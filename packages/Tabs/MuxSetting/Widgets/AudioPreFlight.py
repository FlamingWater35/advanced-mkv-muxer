"""Warn before a queue that would produce files without any audio (#144).

Deleting every audio track can be intentional, so this is a confirmation and
not a hard refusal. The check reads the cached ``mkvmerge -J`` output in
``MediaInfo/`` instead of probing the files again, so it costs nothing at the
moment the user presses start.
"""

import hashlib
import json
import os

from packages.Startup import GlobalFiles
from packages.Tabs.GlobalSetting import GlobalSetting, is_empty_matching_slot


def get_media_info_file_path(video_absolute_path):
    string_name_hash = hashlib.sha1((str(video_absolute_path)).encode("utf-8")).hexdigest()
    return os.path.join(GlobalFiles.MediaInfoFolderPath, string_name_hash + ".json")


def get_cached_track_count(video_absolute_path, track_type):
    """Number of tracks of a type in the cached MediaInfo, None when unknown."""
    media_info_file_path = get_media_info_file_path(video_absolute_path)
    if not os.path.isfile(media_info_file_path):
        return None
    try:
        with open(media_info_file_path, "r", encoding="UTF-8") as media_info_file:
            json_info = json.load(media_info_file)
    except (OSError, ValueError):
        return None
    tracks = json_info.get("tracks", [])
    return len([track for track in tracks if track.get("type") == track_type])


def count_attached_audios(video_index):
    """How many audio files the queue attaches to this video row."""
    count = 0
    for tab_index in GlobalSetting.AUDIO_FILES_LIST.keys():
        names_list = GlobalSetting.AUDIO_FILES_LIST[tab_index]
        if len(names_list) > video_index:
            if is_empty_matching_slot(names_list[video_index]):
                continue
            count += 1
    return count


def has_kept_source_audios():
    """True when the "Only Keep Those Audios" filter keeps at least one track."""
    return bool(GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_IDS or
                GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_NAMES or
                GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_LANGUAGES or
                GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_ORDERS or
                GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_FORMATS)


def keeps_an_old_audio_track():
    """True when at least one source audio track survives "delete old tracks"."""
    for track_id in GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING.keys():
        if GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_BULK_SETTING[track_id].is_enabled:
            return True
    return False


def job_would_have_no_audio(video_index):
    """True when this row is expected to produce a file without audio tracks."""
    if count_attached_audios(video_index) > 0:
        # Attached audio files are separate inputs, they survive every filter.
        return False
    if GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED:
        return not has_kept_source_audios()
    if GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED:
        return not keeps_an_old_audio_track()
    source_audios = get_cached_track_count(
        GlobalSetting.VIDEO_FILES_ABSOLUTE_PATH_LIST[video_index], "audio")
    if source_audios is None:
        # No cached MediaInfo: stay silent rather than warn wrongly.
        return False
    return source_audios == 0


def find_videos_without_audio():
    """Names of the queued videos that would end up with no audio track."""
    if GlobalSetting.USE_MKVPROPEDIT:
        # Metadata only: the tool does not re-mux, so tracks are untouched.
        return []
    result = []
    for video_index in range(len(GlobalSetting.VIDEO_FILES_LIST)):
        if job_would_have_no_audio(video_index):
            result.append(GlobalSetting.VIDEO_FILES_LIST[video_index])
    return result


def get_no_audio_warning_message(videos_list):
    if len(videos_list) == 1:
        header = "This job will produce a file without any audio track:"
    else:
        header = f"{len(videos_list)} jobs will produce files without any audio track:"
    maximum_names = 10
    lines = [header, ""]
    lines.extend("- " + name for name in videos_list[:maximum_names])
    if len(videos_list) > maximum_names:
        lines.append(f"- and {len(videos_list) - maximum_names} more")
    lines.extend(["", "Continue anyway?"])
    return "\n".join(lines)
