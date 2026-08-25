Rhythm Detector for Linux
=========================

WHAT IS IN THIS FOLDER
----------------------
  RhythmDetector        the application
  music_files/          the two sample tracks (also embedded in the binary)

FIRST LAUNCH
------------
Unzipping does not always preserve the executable bit, so if double-clicking or
running it does nothing:

  chmod +x RhythmDetector
  ./RhythmDetector

The binary bundles its own Python, NumPy, SciPy, matplotlib and libsndfile. It
does need the system Tk libraries to draw the window, which most desktop
installs already have; if it exits complaining about libtk, install your
distribution's Tk package (for example "sudo apt install libtk8.6").

USING IT
--------
Press "Default Execution" to analyse the two sample tracks straight away, or
use the "Choose..." buttons to pick your own audio (.mp3, .wav, .flac, .ogg,
.m4a) and press "Run Detection".

The analysis plots are written to:

  ~/RhythmDetector/results

The first run takes a little while -- roughly 5 seconds of computation per
6 minutes of audio, plus decoding -- and the log panel updates as it goes.
