<p align="center">
  <img src="Resources/Icons/App.ico" alt="Advanced MKV Muxer Icon" width="128">
  <h1 align="center">🎬 Advanced MKV Muxer</h1>
  <p align="center">
    A robust application for muxing (merging) videos with subtitles, audios, chapters, attachments alongside many customization options.
    <br>
    <em>Freshly maintained fork of <a href="https://github.com/yaser01/mkv-muxing-batch-gui">MKV Muxing Batch GUI</a> (by <code>yaser01</code>).</em>
  </p>

  <p align="center">
    <a href="https://github.com/FlamingWater35/advanced-mkv-muxer/releases">
      <img src="https://img.shields.io/badge/Download-Latest%20Release-2ea44f?style=for-the-badge&logo=github" alt="Download Latest Release">
    </a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python Version">
    <img src="https://img.shields.io/badge/Platform-Windows%20|%20Linux-lightgrey" alt="Platform">
    <img src="https://img.shields.io/badge/GUI-PySide6-41CD52" alt="PySide6 GUI">
    <img src="https://img.shields.io/badge/Status-Active-success" alt="Status">
  </p>
</p>

---

## 📷 App Preview

_A preview of Advanced MKV Muxer in action:_

<https://github.com/yaser01/mkv-muxing-batch-gui/assets/52576632/33f8bf3e-600c-4e0d-8ee2-ca51abdf79dc>

---

## 📑 Table of Contents

- [✨ About & Key Features](#-about--key-features)
- [⚙️ Features Reference](#️-features-reference)
- [🚀 Downloads & Setup](#-downloads--setup)
  - [📦 Pre-built Releases](#-pre-built-releases)
  - [🐧 For Linux Users](#-for-linux-users)
  - [💻 Using Python Code Version](#-using-python-code-version)
  - [🔄 Updating the MKVmerge Version](#-updating-the-mkvmerge-version)
  - [⬆️ Checking For A Newer Application Release](#️-checking-for-a-newer-application-release)
- [🎯 Usage Notes](#-usage-notes)
- [📁 Supported Extensions](#-supported-extensions)
- [🧪 Running Tests](#-running-tests)
- [🙏 Credits & Attribution](#-credits--attribution)
- [🪪 License](#-license)

---

## ✨ About & Key Features

Advanced MKV Muxer is a robust application for muxing (merging) videos with subtitles, audios, chapters, attachments alongside many customization options. It is a freshly maintained version of [MKV Muxing Batch GUI](https://github.com/yaser01/mkv-muxing-batch-gui), continuing the original project with ongoing maintenance and updates. Best wishes and many thanks to the original author, [yaser01](https://github.com/yaser01).

- **Video Options**: View media info of each file to monitor the video tracks; change default video duration/FPS (use this feature cautiously).
- **Subtitle Options**: Add new subtitles to each video file with individual settings, reorder to match the right video, set default/forced, configure delay, track name, and language, and mux at any desired position.
- **Audio Options**: Add new audios to each video file with individual settings, reorder to match the right video, set default/forced, configure delay, track name, and language, and mux at any desired position.
- **Chapter Options**: Add new chapters to each video file, reorder to match the right video, and remove files from the chapter tab.
- **Attachment Options**: Add new attachments to all video files, discard old attachments, attach files/folders per video (expert mode), and prevent adding duplicate existing attachments.
- **Source Files Options**: Discard old subtitles/audios, keep only specific languages/track IDs while discarding others, set old tracks to default/forced, and modify existing tracks individually.
- **Muxing Options**: Override global settings per file, save a log file, set default directories/languages/extensions, optimize muxing by modifying source files, and check for MKVToolNix and application updates with one click.

---

## ⚙️ Features Reference

A quick guide to the main feature categories. Click each to expand the full details.

<details>
<summary><strong>🎬 Video Options</strong></summary>

<br>

- View media info of each file to monitor the video tracks
- Change default video duration/FPS [use this feature cautiously]

</details>

<details>
<summary><strong>💬 Subtitle Options</strong></summary>

<br>

- Add new subtitles to each video file
- Subtitles names **don't have to match** videos names
- Reorder the subtitles to match the right video
- Remove files from the subtitle tab
- Set subtitles to be default/forced
- Set subtitle delay, track name, language
- Mux the new subtitle at any desired position in the output video
- Add multiple subtitles to each video file with individual settings for each subtitle

</details>

<details>
<summary><strong>🔊 Audio Options</strong></summary>

<br>

- Add new audios to each video file
- Audios names **don't have to match** videos names
- Reorder the audios to match the right video
- Remove files from the audio tab
- Set audios to be default/forced
- Set audio delay, track name, language
- Mux the new audio at any desired position in the output video
- Add multiple audios to each video file with individual settings for each audio

</details>

<details>
<summary><strong>📑 Chapter Options</strong></summary>

<br>

- Add new chapters to each video file
- Chapters names **don't have to match** videos names
- Reorder the chapters to match the right video
- Remove files from the chapter tab

</details>

<details>
<summary><strong>📎 Attachment Options</strong></summary>

<br>

- Add new attachments to all video files
- Discard old attachments files from all videos
- Ability to attach file/folder for each video separately [expert mode]
- Option to prevent adding duplicate existing attachments [any existing attachment in source video will be skipped]

</details>

<details>
<summary><strong>📂 Source Files Options</strong></summary>

<br>

- Discard old subtitles
- Keep subtitles with specific language(s) and/or track id(s) while discarding any other subtitle
- Discard old audios
- Keep audios with specific language(s) or track id(s) while discarding any other audio
- Set an old subtitle track to be default/forced
- Set an old audio track to be default/forced
- Modify existing tracks **(each track separately)** like: track name, delete, set default, set forced and language, even you can change their order with shortcuts `Ctrl + Up Arrow / Ctrl + Down Arrow`

</details>

<details>
<summary><strong>🔀 Muxing Options</strong></summary>

<br>

- Override global settings by changing subtitle/audio settings (delay, track name, language) for each subtitle/audio file
- Save a log file
- Set your default directories, languages, and file extensions to be remembered for future runs
- Optimize your muxing by modifying the source file when feasible. A prompt will appear when this option is available
- Check for new MKVToolNix releases from the options dialog: the installed `mkvmerge`/`mkvpropedit` versions are shown, and a newer release can be downloaded and installed for the current platform with one click
- Check for new Advanced MKV Muxer releases from the options dialog: the installed app version is shown, and when a newer release exists its version is displayed with a button that opens the release page

</details>

---

## 🚀 Downloads & Setup

### 📦 Pre-built Releases

Advanced MKV Muxer runs on 64-bit Windows 10 (1809 or later) and Windows 11, and on 64-bit x86_64 Linux. 32-bit builds are not produced: Qt 6 and the PySide6 wheels this app depends on are 64-bit only, and the bundled MKVToolNix binaries are x86_64 as well. You can download it from the project's [releases page](https://github.com/FlamingWater35/advanced-mkv-muxer/releases).

**For Windows Users**

Two builds are published:

- **Portable** (`...-windows-x64-portable.zip`) — unpack the folder anywhere and run `Advanced-MKV-Muxer.exe`. No installation and no administrator rights. Your settings, logs and any updated MKVToolNix tools are kept in a `Data` folder inside that folder, so you can move it to another machine or a USB stick and keep your configuration. Delete `portable.flag` next to the executable to store the data in your user profile instead.
- **Installer** (`...-windows-x64-setup.exe`) — installs per user below `%LOCALAPPDATA%\Programs\Advanced MKV Muxer`, with a Start Menu entry and an optional desktop shortcut. Settings live in `%APPDATA%\Advanced MKV Muxer`.

### 🐧 For Linux Users

Two Linux builds are published: an **AppImage** (`...-linux-x64.AppImage`, make it executable and run it) and a **tarball** (`...-linux-x64.tar.gz`, unpack it and run `Advanced-MKV-Muxer` from the unpacked folder).

Both are built on Ubuntu 22.04, so they require glibc 2.35 or newer: Ubuntu 22.04 and up, Mint 21.2 and up, Fedora 38 and up and other current distributions. Before starting the app, install the following libraries (not always needed as most of them are included in the app):

```bash
sudo apt-get install -y libpugixml-dev
sudo apt-get install -y libmatroska-dev
sudo apt install libxcb-cursor0
```

### 💻 Using Python Code Version

1. Clone the repository: `git clone https://github.com/FlamingWater35/advanced-mkv-muxer.git`.
2. The app uses `PySide6 6.12.0` on `Python 3.12` and only runs on 64-bit systems — there is no 32-bit or PySide2 variant on this repository.
3. Make sure you use Python 3.12: `requirements.txt` pins the exact dependency versions and the test suite asserts them.
4. Just run `pip install -r requirements.txt`.
5. Then run `python main.py` and you are all good.
6. You may use `python3/pip3` instead of `python/pip` depending on your system.
7. For Linux users if you want to use another python version from the one that is already on your system it's recommended to use `pyenv`, if you didn't hear about it, you may read [this](https://askubuntu.com/a/1195153).
8. Also, for Linux users: as this app depends on mkvtoolnix it's very recommended to install it on your system before run the app from [here](https://mkvtoolnix.download/downloads.html).

### 🔄 Updating The MKVmerge Version

The easiest way is the built-in updater: open **Options** and find the **MKVToolNix Tools** section, which shows the installed `mkvmerge`/`mkvpropedit` versions, then press **Check for Updates**. If a newer release exists, **Update** downloads it from [mkvtoolnix.download](https://mkvtoolnix.download/downloads.html), verifies the checksum (Windows), installs the tools for the current platform and switches to them immediately. Updated tools are stored per user in the application data folder (or in `Data` for a portable copy), so the update also works for the portable build.

If you prefer to do it manually, you can still replace the files yourself — but do this only if you're sure of what you're doing, as it may require a reinstallation:

```bash
# Navigate to the app's installation directory, e.g. on Windows for the installer build:
"%LOCALAPPDATA%\Programs\Advanced MKV Muxer"
# or the folder you unpacked for the portable build
# Go to Resources\Tools\ [your operating system], and replace mkvmerge.exe and mkvpropedit.exe with the newer version you have
```

> For Linux users it's recommended to just clear `Resources\Tools\ [your operating system]` folder and then install mkvtoolnix on your system from [here](https://mkvtoolnix.download/downloads.html) and the app will automatically detect it.

### ⬆️ Checking For A Newer Application Release

Open **Options** and find the **Application Updates** section. It shows the version you are running; press **Check for Updates** and, if a newer release has been published, the new version number is displayed and an **Open Latest Release** button opens that release page in your browser, where you can download the current build for your platform. When you are already up to date, the section says so and the button stays hidden.

The check reads the project's [releases](https://github.com/FlamingWater35/advanced-mkv-muxer/releases) from GitHub and does not download or install anything by itself.

---

## 🎯 Usage Notes

> [!NOTE]
>
> 1. Leaving destination folder empty will lead to overwrite source videos a popup will shown to confirm this action.
> 2. When the option [make this subtitle/audio default] is activated with language/track that does not exist in the source, then the option will be ignored.
> 3. When the option [keep this subtitle/audio only] is activated with language/track that does not exist in the source video, then the option will lead to output video with only chosen language/track (even if it means to discard all subtitle/audio from the source).
> 4. When using `Modify Old Tracks` in video tab, the following options: (make this subtitle/audio default, keep this subtitle/audio only, mux new subtitle/audio in desired position) will be **disabled/limited**.
> 5. When using `mux subtitle/audio` at same position for the same track type, they will be added respecting to the order of all other new subtitles/audio.
> 6. In every tab/dialog you can reorder tracks using shortcuts `Ctrl + Up Arrow / Ctrl + Down Arrow` except for: (Attachment/Muxing Tab).

---

## 📁 Supported Extensions

|     Type    |                                        Extensions                                       |
|:-----------:|:---------------------------------------------------------------------------------------:|
|   Video     | AVI, MKV, MP4, M4V, MOV, MPEG, TS, OGG, OGM, H264, H265, WEBM, WMV                      |
|  Subtitle   | ASS, SRT, SSA, SUP, PGS, MKS, VTT                                                       |
|   Audio     | AAC, AC3, FLAC, EAC3, MKA, M4A, MP3, DTS, DTSMA, THD, WAV, OGG, OPUS                    |
|   Chapter   | XML                                                                                     |

---

## 🧪 Running Tests

After installing the dependencies, run the test suite from the repository root:

```bash
python -m unittest discover -s tests -t . -v
```

The tests use a temporary profile under `tests/.tmp/`, so they do not touch your real application settings.

---

## 🙏 Credits & Attribution

- **Advanced MKV Muxer** is a freshly maintained fork of **[MKV Muxing Batch GUI](https://github.com/yaser01/mkv-muxing-batch-gui)**, originally created by **[yaser01](https://github.com/yaser01)**. Huge thanks to the original author for building the application this project is based on.
- The application relies heavily on [MKVToolNix](https://gitlab.com/mbunkus/mkvtoolnix), so a big thanks to them.
- Thanks to everyone who helped test the app and offered numerous ideas.

---

## 🪪 License

[![GitHub](https://img.shields.io/github/license/FlamingWater35/advanced-mkv-muxer?style=for-the-badge)](https://github.com/FlamingWater35/advanced-mkv-muxer/blob/main/LICENSE)
