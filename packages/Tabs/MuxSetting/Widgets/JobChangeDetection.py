"""Decide whether a queue item would change anything at all (#145).

Re-muxing an already-Matroska file onto itself with no options rewrites every
byte of it without changing a single track. With "overwrite source files" that
is pure work: the file is copied through a temporary file and moved back. The
worker asks this module before it starts a job, and marks the job as done
instead of running mkvmerge/mkvpropedit for nothing.

The check is deliberately conservative: it only reports "nothing to do" when
*every* muxing instruction is empty. Any doubt means the job runs.
"""

import os

from packages.Tabs.GlobalSetting import GlobalSetting
from packages.Tabs.MuxSetting.Widgets.SingleJobData import SingleJobData


def is_already_mkv(job: SingleJobData):
    return os.path.splitext(job.video_name_absolute)[1].lower() == ".mkv"


def has_attached_files(job: SingleJobData):
    return bool(job.subtitle_found or job.audio_found or job.chapter_found or
                job.subtitle_name or job.audio_name or job.chapter_name or
                job.attachments_absolute_path)


def has_track_instructions():
    return bool(
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_ENABLED or
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_ENABLED or
        GlobalSetting.MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_SEMI_ENABLED or
        GlobalSetting.MUX_SETTING_MAKE_THIS_SUBTITLE_DEFAULT_FULL_ENABLED or
        GlobalSetting.MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_SEMI_ENABLED or
        GlobalSetting.MUX_SETTING_MAKE_THIS_AUDIO_DEFAULT_FULL_ENABLED or
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_MODIFIED_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_REORDER_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_VIDEOS_DELETED_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_MODIFIED_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_REORDER_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_AUDIOS_DELETED_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_MODIFIED_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_REORDER_ACTIVATED or
        GlobalSetting.VIDEO_OLD_TRACKS_SUBTITLES_DELETED_ACTIVATED or
        any(GlobalSetting.SUBTITLE_SET_DEFAULT.values()) or
        any(GlobalSetting.SUBTITLE_SET_FORCED.values()) or
        any(GlobalSetting.AUDIO_SET_DEFAULT.values()) or
        any(GlobalSetting.AUDIO_SET_FORCED.values()) or
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_ORDERS or
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_SUBTITLES_TRACKS_FORMATS or
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_ORDERS or
        GlobalSetting.MUX_SETTING_ONLY_KEEP_THOSE_AUDIOS_TRACKS_FORMATS
    )


def has_container_instructions():
    return bool(
        GlobalSetting.CHAPTER_DISCARD_OLD or
        GlobalSetting.CHAPTER_GENERATE_BY_INTERVAL or
        GlobalSetting.ATTACHMENT_DISCARD_OLD or
        GlobalSetting.MUX_SETTING_SET_TITLE_TO_FILE_NAME or
        GlobalSetting.MUX_SETTING_DISCARD_ALL_TAGS or
        GlobalSetting.VIDEO_FIX_BITSTREAM_TIMING_INFO or
        GlobalSetting.VIDEO_DEFAULT_DURATION_FPS not in ["", "Default"] or
        int(GlobalSetting.CHAPTER_DELAY_MILLISECONDS) != 0 or
        GlobalSetting.MUX_SETTING_STOP_AFTER_VIDEO_ENDS or
        GlobalSetting.ATTACHMENT_AUTO_DETECT_FONTS or
        str(GlobalSetting.MUX_SETTING_EXTRA_ARGUMENTS).strip() != "" or
        # An output name pattern renames the file even when nothing else
        # changes, so it is a real instruction (#111).
        str(GlobalSetting.MUX_SETTING_OUTPUT_NAME_PATTERN).strip() != ""
    )


def job_has_nothing_to_do(job: SingleJobData):
    """True when running this job would leave the file exactly as it is."""
    if not GlobalSetting.OVERWRITE_SOURCE_FILES:
        # A separate output folder always asks for a new file.
        return False
    if not is_already_mkv(job):
        # A non-Matroska source is a real conversion, never a no-op.
        return False
    if job.is_crc_calculating_required or job.is_crc_removing_required:
        return False
    if has_attached_files(job):
        return False
    if has_track_instructions() or has_container_instructions():
        return False
    return True
