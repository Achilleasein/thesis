# thesis

Filterbank-based musical beat and tempo detection, following the Scheirer /
"Beat This" approach with the MATLAB reference implementations in
`code/matlab_reference_codes/` as the starting point.

## How it works

The pipeline runs once per input file:

| Stage | Module | What it does |
| --- | --- | --- |
| decode | `filterbank_module.read_audio` | soundfile, falling back to audioread; downmixed to mono |
| filterbank | `filterbank_module.bandpass_filter` | six Butterworth bands (1–200 … 3200–5000 Hz), one at a time |
| envelope | `envelope_module.get_envelope` | full-wave rectify, then smooth with a decaying half-Hann window |
| onsets | `diff_rect_module.diff_rect` | differentiate, then half-wave rectify |
| tempo | `comb_filter_module.analyze_tempo` | energy against a bank of 3-impulse comb filters, 60–179 BPM |
| combine | `comb_filter_module.combine_band_energies` | standardise each band, then sum, so all six get an equal vote |
| pick | `comb_filter_module.find_fundamental_tempo` | strongest *interior* peak of the combined curve |

`analyze_tempo` does not actually build comb filters. It evaluates the identical
energy analytically from the signal's autocorrelation, which needs two FFTs for
the whole tempo range instead of one per tempo. `create_comb_filter` is kept as
the readable reference definition of what the maths encodes.

The final step deliberately ignores the range boundaries. A comb at half the
true tempo still lands on every other beat, so an octave alias scores highly —
and when that alias sits on the first grid point (60 BPM aliasing a true 120) no
left-hand neighbour exists to disqualify it, so a plain `argmax` reports the
boundary rather than a peak.

On the two bundled tracks the detector reports **pathfinder 120 BPM** and
**celebration 80 BPM**. Both are pinned by `tests/test_smoke.py`; see the
caveat under "Tests" before trusting them as ground truth.

## Running the app

You need a system Python (3.10 or newer) that includes Tk; everything else is
installed automatically into a local virtual environment. Works on Windows,
macOS and Linux.

```sh
python run.py
```

This creates `.venv/`, installs `requirements.txt`, verifies Tk is importable
and launches the GUI. Useful flags:

- `python run.py --recreate` — rebuild the virtual environment from scratch.
- `python run.py --skip-install` — launch without reinstalling dependencies.

If the launcher reports that Tkinter is missing, it prints the exact install
command for your platform (e.g. `sudo apt install python3-tk`,
`sudo dnf install python3-tkinter`, `brew install python-tk`, or re-running the
python.org installer on Windows with the Tcl/Tk option enabled).

In the GUI: press **Default Execution** to analyse the two bundled sample tracks
straight away, or pick one or two of your own with the *Choose…* buttons and
press **Run Detection**. The samples are only ever selected by pressing that
button — nothing is chosen for you when the window opens. A **Detected Tempo**
panel at the top shows one large `<n> BPM`
readout per track as soon as each result arrives, the latest also appearing in
the status bar. Below it the worker's log streams live, and each plot appears as
soon as it is written. If a run produces no tempo at all the panel says so
explicitly rather than staying blank, and the log holds the reason.

## Running the analysis without the GUI

The detector is a plain CLI program and needs no Tk. It accepts any number of
audio files, and analyses nothing unless you name what to analyse:

```sh
cd code/python_implementation
python rhythm_detection.py track1.mp3 track2.mp3 # your own files, any count
python rhythm_detection.py --default-tracks      # the two bundled samples
python rhythm_detection.py --default-tracks mine.mp3   # both, for comparison
```

An empty command line exits 2 with a usage hint rather than quietly analysing
the samples, which used to make them look like part of every run's output.

Two PNGs per input are written to `code/python_implementation/results/`, a
per-band breakdown (`<name>_analysis.png`) and the combined curve
(`<name>_total.png`), each announced on stdout as `SAVED: <path>`. The result
itself is printed as:

```
TEMPO: 120.00 BPM /path/to/pathfinder.mp3
```

These two line formats are the interface the GUI reads to populate its tempo
panel and image gallery, so they are machine-readable on purpose: the BPM
precedes the path so that paths containing spaces still parse, and the path is
included because a file that fails earlier prints nothing at all, which would
silently shift any positional match. `rhythm_detection.format_tempo_line` is the
single definition of the tempo format, and a test asserts the GUI's regex parses
what it produces.

Expect roughly 5 s and ~1.3 GB of peak memory for 6.5 minutes of audio at
44.1 kHz. Note that everything runs at the full sample rate, unlike the MATLAB
reference which works at 4096 Hz.

## Standalone application

`rhythm_detector_gui.spec` builds a self-contained, windowed application with
PyInstaller — no Python installation needed on the target machine:

```sh
python -m pip install pyinstaller
pyinstaller rhythm_detector_gui.spec      # run from the repository root
```

Output is `dist/RhythmDetector` (`dist/RhythmDetector.exe` on Windows), plus
`dist/Rhythm Detector.app` on macOS. The two sample tracks are embedded, so
**Default Execution** works even from a bundle that has been moved somewhere
else entirely.

The same binary is also its own analysis worker. Frozen, there is no
`rhythm_detection.py` on disk to spawn, so the application re-executes itself
with `--run-detection`; that is also the quickest way to check a build:

```sh
"dist/Rhythm Detector.app/Contents/MacOS/RhythmDetector" --run-detection --default-tracks
```

Frozen builds write their plots to `~/RhythmDetector/results`
(`%USERPROFILE%\RhythmDetector\results` on Windows) rather than next to the
executable, which would be read-only under `/Applications` or `Program Files`
and, on macOS, would invalidate the code signature.

### Downloads and the unsigned-application warnings

PyInstaller cannot cross-compile, so the `Build executables` workflow builds
each platform on its own runner. It runs on pushes to `main` and on manual
dispatch, and pushing a `v*` tag additionally publishes the zips as a GitHub
Release. Each zip contains the application, a visible `music_files/` folder and
a `README-FIRST.txt` (the per-platform files under `packaging/`).

Neither the macOS nor the Windows build is signed with a real certificate —
both require a paid developer account, and this is a thesis project — so both
operating systems will object on first launch:

- **macOS**: the bundle is *ad-hoc* signed in CI, which is what lets it execute
  at all on Apple Silicon, but Gatekeeper still blocks it. Right-click → **Open**
  (macOS 15+: System Settings → Privacy & Security → **Open Anyway**), or run
  `xattr -dr com.apple.quarantine "Rhythm Detector.app"` once.
- **Windows**: SmartScreen shows "Windows protected your PC" — click **More
  info** → **Run anyway**.

The macOS zip is built with `ditto` rather than `zip`, because `zip` flattens
the `.app`'s symlinks and drops the signature, which would leave the download
broken in exactly the way the signing step exists to prevent.

## Tests

```sh
python -m pip install -r requirements.txt pytest
python -m pytest
```

The headless smoke tests run on Windows, macOS and Linux across Python
3.10–3.13 in the `CI` workflow. They cover:

- the full pipeline (decode → filterbank → envelope → onsets → tempo), with two
  tests pinning the detected tempo of the bundled tracks so that changes to the
  envelope window, the comb-filter maths, the band weighting or the peak picking
  cannot silently regress accuracy;
- the analysis helpers in isolation — band weighting, peak picking and plot
  decimation, each with the failure mode it exists to prevent;
- the GUI layer (`tests/test_gui_smoke.py`), which imports every GUI module,
  checks the **Default Execution** button selects both samples and hands over to
  the normal run path, and exercises the image-flattening helper. These tests
  skip automatically if the interpreter has no Tk or no display;
- the build-and-packaging contracts (`tests/test_packaging.py`): where the
  sample tracks are looked up, that an empty command line analyses nothing, and
  that the two halves of the `--run-detection` worker handshake agree. Those
  frozen code paths cannot be exercised from a checkout, so what is pinned is
  the agreement between the modules that implement them.

**Caveat on those expected values.** `celebration = 80` is well supported: five
of six bands and an independent spectral-flux estimate (79.5) agree.
`pathfinder = 120` is confirmed only up to the octave — all six bands put their
strongest interior peak at 120, but an independent flux estimate landed on 60,
the same octave family. If you know the notated tempi, correct `expected_bpm` in
`test_detects_known_tempo`.

## Linting

```sh
python -m pip install pylint
pylint $(git ls-files '*.py')
```

Run from the repository root so pylint picks up `[tool.pylint.*]` in
`pyproject.toml`. That config pins `py-version = "3.10"` so results do not
depend on which interpreter runs the linter, raises the design thresholds
rather than disabling them, and documents the one project-wide suppression
(`broad-exception-caught`, deliberate: the GUI and the batch loop isolate
failures per widget and per file). The `lint` job in the `CI` workflow enforces
a clean run.

## Continuous integration

Two workflows:

- **`CI`** — the test matrix plus the `lint` job. Runs on pushes to `main` and
  on pull requests. It intentionally does *not* run on pushes to every branch,
  which would build each PR commit twice; open the PR (a draft is enough) to get
  CI on a branch.
- **`Build executables`** — the three PyInstaller applications, on pushes to
  `main`, manual dispatch, and `v*` tags (which also publish a Release). Each
  runner verifies Tk is importable before building (PyInstaller only *warns*
  about a module it cannot find, so a broken Tk would otherwise ship a GUI
  application with no GUI), then runs the frozen binary in `--run-detection`
  mode and requires a `TEMPO:` and a `SAVED:` line — a missing hidden import
  produces a window that fails on every run, and that is the only step that
  would catch it before a user did.

Both cache pip downloads and cancel superseded runs for the same ref, except
tag builds, which are never cancelled because they publish release assets.

# Notes:
Detecting beat from a song with drums is easy, will do it with fitlerbank
Its different to detect the rhythm in a purely instrumental song.
Beat is different than rhythm

Band weighting matters more than expected: with a plain sum of band energies the
1–200 Hz band carried ~47% of the decision and the top three bands ~1–4% each,
so the filterbank was effectively a two-band analysis. Standardising each band
before summing gives all six an equal vote.

# Sources:

- [Audio Analysis using the Discrete Wavelet Transform](https://soundlab.cs.princeton.edu/publications/2001_amta_aadwt.pdf)
- [Beat This > Beat Detection Algorithm](https://www.clear.rice.edu/elec301/Projects01/beat_sync/beatalgo.html)
- https://dictionary.onmusic.org/appendix/topics/meters
- http://web.media.mit.edu/~tristan/Blog/WASPAA05_Tristan.pdf
- http://www-labs.iro.umontreal.ca/~pift6080/H09/documents/papers/scheirer_jasa.pdf
- https://ccrma.stanford.edu/~jos/r320/Analytic_Signals_Hilbert_Transform.html
- https://music.stackexchange.com/questions/77868/how-many-octaves-exist
- http://web.media.mit.edu/~tristan/phd/dissertation/chapter3.html
- https://www.algorithm-archive.org/contents/cooley_tukey/cooley_tukey.html
- https://github.com/TUIlmenauAMS/FilterBanks_FastPythonImplementation
- https://github.com/wil-j-wil/py_bank
- https://ismir2001.ismir.net/pdf/tzanetakis.pdf
- http://marsyas.info/
- https://github.com/marsyas/marsyas
- https://core.ac.uk/download/pdf/81077583.pdf
- https://www.iccs-meeting.org/archive/iccs2023/papers/140730692.pdf

# Music used:

- https://soundcloud.com/creatorchords/pathfinder


# TO-DO:
Detect simple beat 4/4 from a Pop song.

Known gaps in the current implementation:

- No downsampling. Everything runs at 44.1 kHz where the reference uses
  4096 Hz, so the comb-filter stage does roughly 10x the necessary work.
- Octave errors are avoided rather than resolved. A perceptual tempo prior
  (~100–150 BPM, per Scheirer) would decide 60-vs-120 on principle.
- Tempo resolution is fixed at 1 BPM over 60–179; the reference's recursive
  refinement for finer resolution is not implemented.
- Only two sample tracks, which is too few to tune the band weighting or a
  tempo prior against without overfitting.
