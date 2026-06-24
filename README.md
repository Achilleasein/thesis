# thesis

# Running the app

The project runs on Windows, macOS and Linux. You only need a system Python
(3.10 or newer) that includes Tk; everything else is installed automatically
into a local virtual environment.

```sh
python run.py
```

This creates `.venv/`, installs the dependencies from `requirements.txt`, and
launches the Rhythm Detector GUI. Useful flags:

- `python run.py --recreate` — rebuild the virtual environment from scratch.
- `python run.py --skip-install` — launch without reinstalling dependencies.

If the launcher reports that Tkinter is missing, it prints the exact install
command for your platform (e.g. `sudo apt install python3-tk`,
`sudo dnf install python3-tkinter`, `brew install python-tk`, or re-running the
python.org installer on Windows with the Tcl/Tk option enabled).

## Running the tests

```sh
python -m pip install -r requirements.txt pytest
python -m pytest
```

The headless smoke tests (decode → filterbank → tempo) are exercised on
Windows, macOS and Linux across Python 3.10–3.13 by the GitHub Actions CI
workflow.

# Notes:
Detecting beat from a song with drums is easy, will do it with fitlerbank
Its different to detect the rhythm in a purely instrumental song.
Beat is different than rhythm


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



