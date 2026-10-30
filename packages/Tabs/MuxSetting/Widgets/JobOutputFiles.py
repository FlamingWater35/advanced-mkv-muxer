"""File-system side of finishing a muxing job.

Everything in this module is plain blocking I/O and is meant to run on the
muxing worker thread, never on the GUI thread: renaming a freshly written file
can fail for seconds while the muxer or a virus scanner still holds it open,
and size queries can block on network shares.
"""

import os
import shutil
import time
from pathlib import Path

from packages.Tabs.GlobalSetting import GlobalSetting, write_to_log_file

Valid_CRC_String = "0123456789ABCDEF"

# A bounded retry: the old GUI thread implementation retried for 25 seconds,
# which froze the window that long for every locked output file.
RENAME_ATTEMPTS = 40
RENAME_RETRY_DELAY = 0.05


def get_file_name_with_mkv_extension(file_name):
    file_extension_start_index = file_name.rfind(".")
    new_file_name_with_mkv_extension = file_name[:file_extension_start_index] + ".mkv"
    return new_file_name_with_mkv_extension


def change_file_extension_to_mkv_with_random_suffix(file_name):
    file_extension_start_index = file_name.rfind(".")
    new_file_name_with_mkv_extension = file_name[
                                       :file_extension_start_index] + "#" + GlobalSetting.RANDOM_OUTPUT_SUFFIX + ".mkv "
    return new_file_name_with_mkv_extension


def get_file_name_without_crc(file_name):
    file_name = str(file_name)
    file_name_without_crc = file_name
    bracket_left_index = file_name.rfind("[")
    bracket_right_index = file_name.rfind("]")
    if (bracket_right_index - bracket_left_index - 1) == 8:
        valid_counter = 0
        for i in range(bracket_left_index + 1, bracket_right_index):
            if file_name[i] in Valid_CRC_String:
                valid_counter += 1
        if valid_counter == 8:
            file_name_without_crc = file_name[:bracket_left_index] + file_name[
                                                                     bracket_right_index + 1:]
    extension_index = file_name_without_crc.rfind(".")
    file_name_without_extension = file_name_without_crc[:extension_index]
    last_valid_char = 0
    for i in range(len(file_name_without_extension) - 1, -1, -1):
        if file_name_without_extension[i] != " ":
            last_valid_char = i
            break
    file_name_without_crc = file_name_without_crc[
                            :last_valid_char + 1] + file_name_without_crc[extension_index:]
    return file_name_without_crc


def get_file_name_with_crc(file_name, crc_string):
    file_name = str(file_name)
    file_name_without_crc = file_name
    bracket_left_index = file_name.rfind("[")
    bracket_right_index = file_name.rfind("]")
    if (bracket_right_index - bracket_left_index - 1) == 8:
        valid_counter = 0
        for i in range(bracket_left_index + 1, bracket_right_index):
            if file_name[i] in Valid_CRC_String:
                valid_counter += 1
        if valid_counter == 8:
            file_name_without_crc = file_name[:bracket_left_index] + file_name[
                                                                     bracket_right_index + 1:]
    extension_index = file_name_without_crc.rfind(".")
    file_name_without_extension = file_name_without_crc[:extension_index]
    last_valid_char = 0
    for i in range(len(file_name_without_extension) - 1, -1, -1):
        if file_name_without_extension[i] != " ":
            last_valid_char = i
            break
    if file_name_without_crc[last_valid_char] in ['[', ']', ')', '(', '}', '{']:
        file_name_with_crc = file_name_without_crc[
                             :last_valid_char + 1] + "[" + crc_string + "]" + file_name_without_crc[
                                                                              extension_index:]
    else:
        file_name_with_crc = file_name_without_crc[
                             :last_valid_char + 1] + " [" + crc_string + "]" + file_name_without_crc[
                                                                               extension_index:]
    return file_name_with_crc


def get_file_size(file_path):
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def delete_file(file_path):
    try:
        os.remove(file_path)
        return True
    except OSError:
        return False


def get_overwrite_temp_folder(job):
    """Relay folder for the intermediate file of an overwrite job (#143)."""
    configured_folder = str(GlobalSetting.OVERWRITE_TEMP_FOLDER_PATH or "").strip()
    if configured_folder:
        return configured_folder
    return os.path.dirname(job.video_name_absolute)


def get_overwrite_temp_path(job):
    return os.path.join(get_overwrite_temp_folder(job),
                        change_file_extension_to_mkv_with_random_suffix(job.video_name))


def are_on_different_devices(first_path, second_path):
    try:
        return os.stat(os.path.dirname(first_path)).st_dev != os.stat(os.path.dirname(second_path)).st_dev
    except OSError:
        return False


def move_file_across_devices(old_path, new_path):
    """os.rename() cannot cross file systems; copy + delete instead."""
    try:
        shutil.move(old_path, new_path)
        return True
    except OSError:
        write_to_log_file(f"Could not move '{old_path}' to '{new_path}'")
        return False


def rename_file(file_name_old_absolute_path, file_name_new_absolute_path,
                attempts=RENAME_ATTEMPTS, delay=RENAME_RETRY_DELAY):
    """Rename with a short bounded retry, returning True on success.

    Windows keeps a file locked for a moment after the muxing tool closes it,
    which is why the retry exists at all. It is deliberately short because the
    caller runs on a background thread but still gates the job queue. A relay
    folder on another drive is handled with a real move.
    """
    if os.path.abspath(str(file_name_old_absolute_path)) == os.path.abspath(str(file_name_new_absolute_path)):
        return True
    if are_on_different_devices(file_name_old_absolute_path, file_name_new_absolute_path):
        return move_file_across_devices(file_name_old_absolute_path, file_name_new_absolute_path)
    for _ in range(attempts):
        try:
            os.rename(file_name_old_absolute_path, file_name_new_absolute_path)
            return True
        except OSError:
            time.sleep(delay)
    if os.path.exists(file_name_old_absolute_path):
        # Last resort for a cross-device rename that was not detected above.
        return move_file_across_devices(file_name_old_absolute_path, file_name_new_absolute_path)
    write_to_log_file(
        f"Could not rename '{file_name_old_absolute_path}' to '{file_name_new_absolute_path}'")
    return False


def create_parent_folder(absolute_path):
    """Create the folders a mirrored subfolder output needs (#136, #157).

    Files loaded from subfolders keep their sub path, so the output folder
    structure has to exist before mkvmerge writes into it.
    """
    parent_folder = os.path.dirname(os.path.abspath(str(absolute_path)))
    if parent_folder and not os.path.isdir(parent_folder):
        os.makedirs(parent_folder, exist_ok=True)


RELATIVE_FOLDER_PREFIXES = (".\\", "./", "..\\", "../")


def is_relative_destination_folder(folder_path):
    """True for a destination like "converted" or ".\\converted" (#118).

    Such a destination is resolved against the folder of every source file, so
    a queue that mixes folders still writes each output next to its own input.
    """
    text = str(folder_path or "").strip()
    if not text:
        return False
    if text.startswith(RELATIVE_FOLDER_PREFIXES):
        return True
    if os.path.isabs(text):
        return False
    # "C:converted" is drive relative, not a folder name: leave it alone.
    return os.path.splitdrive(text)[0] == ""


def get_relative_destination_folder(job):
    return os.path.normpath(os.path.join(os.path.dirname(job.video_name_absolute),
                                         str(GlobalSetting.DESTINATION_FOLDER_PATH).strip()))


def uses_relative_destination(job):
    if job.used_mkvpropedit or GlobalSetting.OVERWRITE_SOURCE_FILES:
        return False
    return is_relative_destination_folder(GlobalSetting.DESTINATION_FOLDER_PATH)


def get_output_folder_path(job):
    if job.used_mkvpropedit or GlobalSetting.OVERWRITE_SOURCE_FILES:
        return os.path.dirname(job.video_name_absolute)
    if is_relative_destination_folder(GlobalSetting.DESTINATION_FOLDER_PATH):
        return get_relative_destination_folder(job)
    return str(GlobalSetting.DESTINATION_FOLDER_PATH)


def get_output_file_name(job):
    if str(getattr(job, "custom_output_name", "")).strip() != "":
        # An output name pattern decided the name of this job (#111).
        return job.custom_output_name
    file_name = get_file_name_with_mkv_extension(job.video_name)
    if uses_relative_destination(job):
        # The relative destination already follows the source file, so a sub
        # path from a recursive scan would nest the tree twice.
        file_name = os.path.basename(file_name)
    return file_name


def get_output_file_path(job):
    return os.path.join(get_output_folder_path(job), get_output_file_name(job))


def get_written_output_path(job):
    """Path of the file the muxer itself wrote, before any finalizing rename.

    This has to mirror setup_output_video_command() exactly, because it is used
    to measure and report a job that failed: an output name pattern or a relay
    folder changes where the tool was told to write, and a path that does not
    exist would be reported as a 0 byte output.
    """
    folder_path = get_output_folder_path(job)
    if GlobalSetting.OVERWRITE_SOURCE_FILES and not job.used_mkvpropedit:
        # Same path setup_output_video_command() passes as --output.
        return get_overwrite_temp_path(job)
    return os.path.join(folder_path, get_output_file_name(job))


def record_failed_job_output(job):
    """Record where a failed job left its partial output.

    Nothing is renamed or deleted here: in overwrite mode the source video must
    survive a failed mux, so the "#suffix" output is only measured, not moved
    over the source.
    """
    job.output_video_absolute_path = get_written_output_path(job)
    job.output_video_name = os.path.basename(job.output_video_absolute_path)
    return job.output_video_absolute_path


def replace_source_with_output(source_path, new_path, final_path):
    """Put the freshly muxed file over its source without ever losing the source.

    os.rename() cannot overwrite an existing file on Windows, so the source has
    to move out of the way first. It is moved to a sibling backup instead of
    being deleted, and restored when the rename of the new file fails: a relay
    folder on another drive makes that rename a real copy that can fail halfway
    (#143).
    """
    if not os.path.exists(new_path):
        write_to_log_file(f"Could not replace '{source_path}': '{new_path}' does not exist")
        return False
    backup_path = source_path + ".amkv-old"
    if os.path.exists(backup_path):
        # Left over from an interrupted run; it is not the source any more.
        delete_file(backup_path)
    if not rename_file(source_path, backup_path):
        return False
    if rename_file(new_path, final_path):
        delete_file(backup_path)
        return True
    # The new file could not be moved: put the original back.
    rename_file(backup_path, source_path)
    return False


def finalize_muxing_output(job):
    """Move the tool's output to its final name and record it on the job.

    Must be called before the CRC step, which renames the very same file: doing
    the rename on the GUI thread used to race with the CRC worker reading it.
    """
    folder_path = get_output_folder_path(job)
    final_name = get_output_file_name(job)
    final_path = os.path.join(folder_path, final_name)
    if GlobalSetting.OVERWRITE_SOURCE_FILES and not job.used_mkvpropedit:
        # The muxer wrote "name#suffix.mkv" (in the relay folder when one is
        # configured); replace the original source file.
        if not replace_source_with_output(job.video_name_absolute, get_overwrite_temp_path(job), final_path):
            job.error_occurred = True
            job.muxing_message = "Could not replace the source file with the muxed output"
            # Report the partial output, not the source that was just restored.
            job.output_video_name = os.path.basename(get_overwrite_temp_path(job))
            job.output_video_absolute_path = get_overwrite_temp_path(job)
            return job.output_video_absolute_path
    job.output_video_name = final_name
    job.output_video_absolute_path = final_path
    return final_path


def apply_crc_to_output_name(job):
    """Rename the finished output according to the CRC options of the job."""
    folder_path = get_output_folder_path(job)
    output_video_name = get_output_file_name(job)
    old_path = os.path.join(folder_path, output_video_name)
    if job.is_crc_calculating_required and "%crc%" in output_video_name:
        # The pattern already reserved a place for the CRC (#111).
        new_name = output_video_name.replace("%crc%", str(job.new_crc))
        rename_file(old_path, os.path.join(folder_path, new_name))
    elif job.is_crc_calculating_required:
        new_name = get_file_name_with_crc(output_video_name, job.new_crc)
        rename_file(old_path, os.path.join(folder_path, new_name))
    elif job.is_crc_removing_required:
        new_name = get_file_name_without_crc(output_video_name)
        rename_file(old_path, os.path.join(folder_path, new_name))
    else:
        new_name = output_video_name
    job.output_video_name = new_name
    job.output_video_absolute_path = os.path.join(folder_path, new_name)
    return job.output_video_absolute_path


def get_output_size(job):
    """Return the size of the job output, dropping an empty placeholder file."""
    output_size = get_file_size(job.output_video_absolute_path)
    if output_size == 0:
        delete_file(job.output_video_absolute_path)
    return output_size
