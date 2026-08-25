Rhythm Detector for Windows
===========================

WHAT IS IN THIS FOLDER
----------------------
  RhythmDetector.exe    the application
  music_files\          the two sample tracks (also embedded in the .exe)

FIRST LAUNCH -- PLEASE READ
---------------------------
Windows SmartScreen will probably show "Windows protected your PC" the first
time you run this, because the .exe is not signed with a code-signing
certificate (those are sold per year, and this is a thesis project).

To run it anyway:

  1. Click "More info" in the SmartScreen dialog.
  2. Click "Run anyway".

You only need to do this once. Your antivirus may also want a moment to scan
the file -- unsigned PyInstaller executables are commonly flagged on sight.

USING IT
--------
Press "Default Execution" to analyse the two sample tracks straight away, or
use the "Choose..." buttons to pick your own audio (.mp3, .wav, .flac, .ogg,
.m4a) and press "Run Detection".

The analysis plots are written to:

  %USERPROFILE%\RhythmDetector\results

(that is, a "RhythmDetector" folder in your user folder). The app writes there
rather than next to itself so it keeps working from Program Files.

The first run takes a little while -- roughly 5 seconds of computation per
6 minutes of audio, plus decoding -- and the log panel updates as it goes.
