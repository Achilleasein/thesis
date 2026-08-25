Rhythm Detector for macOS
=========================

WHAT IS IN THIS FOLDER
----------------------
  Rhythm Detector.app   the application
  music_files/          the two sample tracks (also embedded in the app)

FIRST LAUNCH -- PLEASE READ
---------------------------
macOS will refuse to open this app on the first try, with a message like
"cannot be opened because the developer cannot be verified" or
"Rhythm Detector is damaged and should be moved to the Bin".

Nothing is wrong with the download. Apple charges an annual fee to issue the
Developer ID certificate needed to have an app notarized, and this is a thesis
project with no such certificate. The app is ad-hoc signed, which is enough for
macOS to run it, but not enough for Gatekeeper to vouch for it.

Either of these will let it through -- you only need to do it once.

  Option 1 -- right-click
    1. Right-click (or Control-click) "Rhythm Detector.app".
    2. Choose "Open" from the menu.
    3. Click "Open" in the dialog that appears.

    Note: double-clicking does NOT offer this. It must be the right-click menu.
    On macOS 15 (Sequoia) and later, Apple removed this shortcut: go to
    System Settings > Privacy & Security, scroll down, and click
    "Open Anyway" next to the message about Rhythm Detector.

  Option 2 -- Terminal
    Remove the quarantine flag macOS attaches to downloaded files:

      xattr -dr com.apple.quarantine "Rhythm Detector.app"

    Run it from this folder (or give the full path to the .app). The app then
    opens normally by double-clicking.

USING IT
--------
Press "Default Execution" to analyse the two sample tracks straight away, or
use the "Choose..." buttons to pick your own audio (.mp3, .wav, .flac, .ogg,
.m4a) and press "Run Detection".

The analysis plots are written to:

  ~/RhythmDetector/results

(that is, a "RhythmDetector" folder in your home directory). The app writes
there rather than next to itself so it keeps working from /Applications, and so
that saving results never breaks its signature.

The first run takes a little while -- roughly 5 seconds of computation per
6 minutes of audio, plus decoding -- and the log panel updates as it goes.
