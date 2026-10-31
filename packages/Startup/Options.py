import json
import logging
import os
from pathlib import Path
from PySide6.QtWidgets import QWidget
from packages.Startup.GlobalFiles import SettingJsonInfoFilePath
from packages.Startup.SystemTheme import detect_system_dark_mode
from packages.Widgets.SingleDefaultPresetsData import SingleDefaultPresetsData


def get_data_from_json(json_data, attribute, default_value):
    try:
        return json_data[attribute]
    except Exception as e:
        return default_value


def get_names_list_of_presets():
    names_list = []
    for preset in Options.DefaultPresets:
        names_list.append(preset.Preset_Name)
    return names_list


class Options(QWidget):
    DefaultPresets = [SingleDefaultPresetsData()]
    CurrentPreset = SingleDefaultPresetsData()
    FavoritePresetId = 0
    Dark_Mode = False
    Attachment_Expert_Mode_Info_Message_Show = True
    Choose_Preset_On_Startup = False
    # Remembered "Set Default"/"Set Forced" ticks of the subtitle and audio
    # tabs so the user does not have to re-tick them on every launch (#41).
    Default_Subtitle_Set_Default = False
    Default_Subtitle_Set_Forced = False
    Default_Audio_Set_Default = False
    Default_Audio_Set_Forced = False


def save_options():
    default_presets_data = []
    for preset_id in range(len(Options.DefaultPresets)):
        temp_default_preset = {
            "Preset_Name": Options.DefaultPresets[preset_id].Preset_Name,
            "Default_Video_Directory": Options.DefaultPresets[preset_id].Default_Video_Directory,
            "Default_Video_Extensions": Options.DefaultPresets[preset_id].Default_Video_Extensions,
            "Default_Subtitle_Directory": Options.DefaultPresets[preset_id].Default_Subtitle_Directory,
            "Default_Subtitle_Extensions": Options.DefaultPresets[
                preset_id].Default_Subtitle_Extensions,
            "Default_Subtitle_Language": Options.DefaultPresets[preset_id].Default_Subtitle_Language,
            "Default_Audio_Directory": Options.DefaultPresets[preset_id].Default_Audio_Directory,
            "Default_Audio_Extensions": Options.DefaultPresets[preset_id].Default_Audio_Extensions,
            "Default_Audio_Language": Options.DefaultPresets[preset_id].Default_Audio_Language,
            "Default_Chapter_Directory": Options.DefaultPresets[preset_id].Default_Chapter_Directory,
            "Default_Chapter_Extensions": Options.DefaultPresets[preset_id].Default_Chapter_Extensions,
            "Default_Attachment_Directory": Options.DefaultPresets[
                preset_id].Default_Attachment_Directory,
            "Default_Destination_Directory": Options.DefaultPresets[
                preset_id].Default_Destination_Directory,
            "Default_Favorite_Subtitle_Languages": Options.DefaultPresets[
                preset_id].Default_Favorite_Subtitle_Languages,
            "Default_Favorite_Audio_Languages": Options.DefaultPresets[
                preset_id].Default_Favorite_Audio_Languages,
        }
        default_presets_data.append(temp_default_preset)
    options_data = {
        "Presets": default_presets_data,
        "FavoritePresetId": Options.FavoritePresetId,
        "Dark_Mode": Options.Dark_Mode,
        "Attachment_Expert_Mode_Info_Message_Show": Options.Attachment_Expert_Mode_Info_Message_Show,
        "Choose_Preset_On_Startup": Options.Choose_Preset_On_Startup,
        "Default_Subtitle_Set_Default": Options.Default_Subtitle_Set_Default,
        "Default_Subtitle_Set_Forced": Options.Default_Subtitle_Set_Forced,
        "Default_Audio_Set_Default": Options.Default_Audio_Set_Default,
        "Default_Audio_Set_Forced": Options.Default_Audio_Set_Forced
    }
    options_file_path = Path(SettingJsonInfoFilePath)
    # Write to a sibling file and swap it in. Opening the real file with "w"
    # truncates it first, so a crash (or a power loss) between the truncate and
    # the flush left a zero-byte setting.json behind, and the next start-up died
    # in json.load() with "Expecting value: line 1 column 1 (char 0)".
    temporary_path = options_file_path.with_name(options_file_path.name + ".tmp")
    try:
        with open(temporary_path, "w", encoding="UTF-8") as option_file:
            json.dump(options_data, option_file, indent=4)
            option_file.flush()
            try:
                os.fsync(option_file.fileno())
            except OSError as exception:
                # Durability is best-effort: the replace below is what keeps the
                # settings file complete, so a filesystem that cannot fsync must
                # not turn a working save into a crash.
                logging.warning("Could not flush the settings file to disk: %s", exception)
    except Exception:
        # Leave the existing settings file untouched and do not litter the
        # profile folder with a half-written temporary file.
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise
    os.replace(temporary_path, options_file_path)


def _quarantine_corrupt_options(option_file_path):
    """Move an unreadable settings file aside so the defaults can be rewritten."""
    broken_path = option_file_path.with_name(option_file_path.name + ".corrupt")
    try:
        os.replace(option_file_path, broken_path)
        logging.warning("The settings file %s could not be read and was moved to %s; "
                        "default settings are used.", option_file_path, broken_path)
    except OSError as exception:
        logging.warning("The settings file %s could not be read (%s) and could not be "
                        "moved aside; default settings are used.", option_file_path, exception)


def _load_options_data(option_file_path):
    """Return the parsed settings file, or an empty mapping if it is unusable.

    A missing, truncated, empty or otherwise unreadable file must not abort
    start-up: ``read_option_file`` runs at import time, before any window
    exists, so an escaping error killed the process with a bare traceback
    instead of opening the application.
    """
    try:
        with open(option_file_path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, ValueError) as exception:
        logging.warning("Could not read the settings file %s: %s", option_file_path, exception)
        _quarantine_corrupt_options(option_file_path)
        return {}
    if not isinstance(data, dict):
        logging.warning("The settings file %s does not contain a JSON object; "
                        "default settings are used.", option_file_path)
        _quarantine_corrupt_options(option_file_path)
        return {}
    return data


def _normalize_presets(presets):
    """Return the stored presets as a list of mappings.

    The value comes from a user-writable file, so it can be any JSON type. Only
    a list of objects is usable; anything else falls back to a single default
    preset instead of raising while start-up is still in progress.
    """
    if presets == "Old":
        return [{}]
    if not isinstance(presets, list):
        logging.warning("The stored presets are not a list (%s); a single default preset is used.",
                        type(presets).__name__)
        return [{}]
    normalized = []
    for index, preset in enumerate(presets):
        if not isinstance(preset, dict):
            logging.warning("Preset #%d is not an object; it is replaced by its defaults.", index + 1)
            preset = {}
        normalized.append(preset)
    if not normalized:
        # The application always keeps at least one preset: the settings dialog
        # refuses to delete the last one, and start-up indexes preset 0.
        logging.warning("No presets were stored; a single default preset is used.")
        return [{}]
    return normalized


def read_option_file(option_file):
    option_file_path = Path(option_file)
    theme_configured = False
    if option_file_path.is_file():
        data = _load_options_data(option_file_path)
        # An empty mapping means the file was unreadable or held no JSON object.
        # Skipping the block below keeps the class-level defaults, and the theme
        # is then detected from the system exactly as on a first start-up.
        if data:
            theme_configured = "Dark_Mode" in data
            presets = _normalize_presets(
                get_data_from_json(json_data=data, attribute="Presets", default_value="Old"))
            preset_number = len(presets)
            Options.DefaultPresets.clear()
            for preset_id in range(preset_number):
                temp_default_preset = SingleDefaultPresetsData()
                temp_default_preset.Preset_Name = get_data_from_json(json_data=presets[preset_id],
                                                                     attribute="Preset_Name",
                                                                     default_value=f"Preset #{preset_id + 1}")
                temp_default_preset.Default_Video_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                 attribute="Default_Video_Directory",
                                                                                 default_value="")
                temp_default_preset.Default_Video_Extensions = get_data_from_json(json_data=presets[preset_id],
                                                                                  attribute="Default_Video_Extensions",
                                                                                  default_value=["MKV"])
                temp_default_preset.Default_Subtitle_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                    attribute="Default_Subtitle_Directory",
                                                                                    default_value="")
                temp_default_preset.Default_Subtitle_Extensions = get_data_from_json(json_data=presets[preset_id],
                                                                                     attribute="Default_Subtitle_Extensions",
                                                                                     default_value=["ASS"])
                temp_default_preset.Default_Subtitle_Language = get_data_from_json(json_data=presets[preset_id],
                                                                                   attribute="Default_Subtitle_Language",
                                                                                   default_value="English")
                temp_default_preset.Default_Audio_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                 attribute="Default_Audio_Directory",
                                                                                 default_value="")
                temp_default_preset.Default_Audio_Extensions = get_data_from_json(json_data=presets[preset_id],
                                                                                  attribute="Default_Audio_Extensions",
                                                                                  default_value=["AAC"])
                temp_default_preset.Default_Audio_Language = get_data_from_json(json_data=presets[preset_id],
                                                                                attribute="Default_Audio_Language",
                                                                                default_value="English")
                temp_default_preset.Default_Chapter_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                   attribute="Default_Chapter_Directory",
                                                                                   default_value="")
                temp_default_preset.Default_Chapter_Extensions = get_data_from_json(json_data=presets[preset_id],
                                                                                    attribute="Default_Chapter_Extensions",
                                                                                    default_value=["XML"])
                temp_default_preset.Default_Attachment_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                      attribute="Default_Attachment_Directory",
                                                                                      default_value="")
                temp_default_preset.Default_Destination_Directory = get_data_from_json(json_data=presets[preset_id],
                                                                                       attribute="Default_Destination_Directory",
                                                                                       default_value="")
                temp_default_preset.Default_Favorite_Subtitle_Languages = get_data_from_json(
                    json_data=presets[preset_id],
                    attribute="Default_Favorite_Subtitle_Languages",
                    default_value=['English',
                                   'Arabic'])
                temp_default_preset.Default_Favorite_Audio_Languages = get_data_from_json(json_data=presets[preset_id],
                                                                                          attribute="Default_Favorite_Audio_Languages",
                                                                                          default_value=['English',
                                                                                                         'Arabic'])
                Options.DefaultPresets.append(temp_default_preset)
            Options.FavoritePresetId = get_data_from_json(json_data=data, attribute="FavoritePresetId", default_value=0)
            # The favourite preset is used as a list index right after start-up,
            # so a stale or out-of-range value would crash with IndexError.
            if not isinstance(Options.FavoritePresetId, int) or isinstance(Options.FavoritePresetId, bool) \
                    or not 0 <= Options.FavoritePresetId < len(Options.DefaultPresets):
                Options.FavoritePresetId = 0
            Options.Dark_Mode = get_data_from_json(json_data=data, attribute="Dark_Mode", default_value=False)
            Options.Attachment_Expert_Mode_Info_Message_Show = get_data_from_json(json_data=data,
                                                                                  attribute="Attachment_Expert_Mode_Info_Message_Show",
                                                                                  default_value=True)
            Options.Choose_Preset_On_Startup = get_data_from_json(json_data=data,
                                                                  attribute="Choose_Preset_On_Startup",
                                                                  default_value=False)
            Options.Default_Subtitle_Set_Default = get_data_from_json(json_data=data,
                                                                      attribute="Default_Subtitle_Set_Default",
                                                                      default_value=False)
            Options.Default_Subtitle_Set_Forced = get_data_from_json(json_data=data,
                                                                     attribute="Default_Subtitle_Set_Forced",
                                                                     default_value=False)
            Options.Default_Audio_Set_Default = get_data_from_json(json_data=data,
                                                                   attribute="Default_Audio_Set_Default",
                                                                   default_value=False)
            Options.Default_Audio_Set_Forced = get_data_from_json(json_data=data,
                                                                  attribute="Default_Audio_Set_Forced",
                                                                  default_value=False)
    if not theme_configured:
        Options.Dark_Mode = detect_system_dark_mode()
    save_options()
