"""Cross-platform smoke tests for the rhythm-detection pipeline.

These run headless (no GUI, no display) and are the verification target for
the CI matrix: if they pass on Windows/macOS/Linux across several Python
versions, the dependency stack and the core algorithm are sound on those
platforms.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPL_DIR = REPO_ROOT / "code" / "python_implementation"
MUSIC_DIR = REPO_ROOT / "music_files"
sys.path.insert(0, str(IMPL_DIR))

# The implementation is a flat set of sibling modules rather than an installed
# package, so the path above has to be set before any of them can be imported.
# pylint: disable=wrong-import-position
from comb_filter_module import (  # noqa: E402
    analyze_tempo,
    combine_band_energies,
    create_comb_filter,
    find_fundamental_tempo,
)
from diff_rect_module import diff_rect  # noqa: E402
from envelope_module import get_envelope  # noqa: E402
from filterbank_module import create_filterbank, read_audio  # noqa: E402
from plot_handler import decimate_for_plot  # noqa: E402  (forces the Agg backend)
from rhythm_detection import get_scheirer_bands  # noqa: E402
# pylint: enable=wrong-import-position

# Must match the range rhythm_detection.main() searches.
TEMPO_RANGE = np.arange(60, 180, 1.0)


def _index_of(tempo: float) -> int:
    return int(np.argmin(np.abs(TEMPO_RANGE - tempo)))


def test_comb_filter_shape():
    """A comb filter for a given tempo has the expected impulses."""
    fs = 8000
    comb = create_comb_filter(fs, tempo=120, num_impulses=3)
    period = int(fs * 60 / 120)
    assert comb.sum() == 3
    assert comb[0] == 1.0
    assert comb[period] == 1.0
    assert comb[2 * period] == 1.0


def test_analyze_tempo_prefers_true_tempo():
    """An impulse train at 120 BPM scores higher at 120 than at off-beat tempos."""
    fs = 11025
    bpm = 120
    period = int(fs * 60 / bpm)
    signal = np.zeros(period * 40, dtype=float)  # ~20 s of clicks
    signal[::period] = 1.0

    energies = analyze_tempo(signal, fs, TEMPO_RANGE)

    assert energies.shape == TEMPO_RANGE.shape
    assert np.all(np.isfinite(energies))
    # 120 BPM should beat clearly non-harmonic neighbours.
    assert energies[_index_of(120)] > energies[_index_of(100)]
    assert energies[_index_of(120)] > energies[_index_of(140)]


@pytest.mark.parametrize("name", ["celebration.mp3", "pathfinder.mp3"])
def test_decode_bundled_audio(name):
    """soundfile/audioread can decode the bundled MP3s on this platform."""
    path = MUSIC_DIR / name
    assert path.is_file(), f"missing test asset: {path}"
    signal, fs = read_audio(str(path))
    assert fs > 0
    assert signal.ndim == 1
    assert len(signal) > fs  # at least one second of audio
    assert np.all(np.isfinite(signal))


def _bump(centre_bpm: float, amplitude: float, baseline: float = 0.0) -> np.ndarray:
    """A single smooth peak at `centre_bpm`, for building synthetic band curves."""
    return baseline + amplitude * np.exp(-((TEMPO_RANGE - centre_bpm) ** 2) / (2 * 4.0 ** 2))


def test_combine_band_energies_gives_quiet_bands_an_equal_vote():
    """Two agreeing quiet bands must outvote one loud band.

    This is the whole point of standardising: with a raw sum, the 1-200 Hz band
    carries ~47% of the weight and the top three bands ~1-4% each, so the loud
    band decides the answer alone no matter what the others say.
    """
    loud = _bump(100, amplitude=1e6, baseline=1e7)   # huge energy, peaks at 100
    quiet_a = _bump(140, amplitude=1.0, baseline=5.0)  # tiny energy, peaks at 140
    quiet_b = _bump(140, amplitude=1.0, baseline=5.0)

    bands = [loud, quiet_a, quiet_b]

    # Raw sum: the loud band wins outright, its two dissenters are rounding error.
    assert find_fundamental_tempo(TEMPO_RANGE, sum(bands)) == 100.0
    # Standardised: two votes for 140 beat one for 100.
    assert find_fundamental_tempo(TEMPO_RANGE, combine_band_energies(bands)) == 140.0


def test_combine_band_energies_skips_flat_bands():
    """A failed band contributes zeros, which has no variance and must not become NaN."""
    good = _bump(120, amplitude=1.0, baseline=5.0)
    flat = np.zeros_like(TEMPO_RANGE)  # what main() appends when a band raises

    combined = combine_band_energies([good, flat, np.full_like(TEMPO_RANGE, 3.0)])

    assert np.all(np.isfinite(combined)), "flat band produced NaN/inf"
    assert find_fundamental_tempo(TEMPO_RANGE, combined) == 120.0


def test_combine_band_energies_rejects_empty_input():
    with pytest.raises(ValueError):
        combine_band_energies([])


def test_find_fundamental_tempo_ignores_boundary_maximum():
    """A tall value at the edge of the range must lose to a genuine interior peak.

    This is the octave-alias case: a comb at half the true tempo scores highly,
    and when that alias lands on the first grid point there is no left-hand
    neighbour to disqualify it, so a plain argmax would report it.
    """
    tempos = np.arange(60, 180, 1.0)
    energies = np.full_like(tempos, 100.0)
    energies[0] = 500.0  # boundary alias -- the global maximum
    energies[tempos == 120] = 300.0  # the real peak

    assert np.argmax(energies) == 0  # a plain argmax would pick the boundary
    assert find_fundamental_tempo(tempos, energies) == 120.0


def test_find_fundamental_tempo_falls_back_when_monotone():
    """With no interior peak at all there is nothing to pick but the maximum."""
    tempos = np.arange(60, 180, 1.0)
    energies = np.linspace(500.0, 100.0, tempos.size)  # strictly decreasing
    assert find_fundamental_tempo(tempos, energies) == 60.0


@pytest.mark.parametrize("name,expected_bpm", [
    ("pathfinder.mp3", 120.0),
    ("celebration.mp3", 80.0),
])
def test_detects_known_tempo(name, expected_bpm):
    """End-to-end accuracy: decode -> filterbank -> envelope -> diff-rect -> tempo.

    Pins the detected tempo of the bundled tracks so that changes to the
    envelope window, the comb-filter maths or the peak picking cannot silently
    regress accuracy. A +/-2 BPM tolerance absorbs FFT rounding differences
    across the platform and Python-version matrix without letting an octave
    error (60 or 160 instead of 80) slip through.
    """
    signal, fs = read_audio(str(MUSIC_DIR / name))
    signal = signal[: fs * 20]  # 20 s slice keeps CI fast; the answer is stable

    per_band = []
    for band in create_filterbank(signal, fs, get_scheirer_bands(fs)):
        onsets = diff_rect(get_envelope(band, fs))
        per_band.append(analyze_tempo(onsets, fs, TEMPO_RANGE))

    # Same aggregation as plot_handler.save_plots, so this covers the real path.
    detected = find_fundamental_tempo(TEMPO_RANGE, combine_band_energies(per_band))
    assert abs(detected - expected_bpm) <= 2.0, (
        f"{name}: expected ~{expected_bpm} BPM, got {detected}"
    )


def test_decimate_for_plot_keeps_isolated_peaks():
    """Decimation must not hide an extreme -- the failure mode of plain subsampling."""
    n = 100_000
    time_axis = np.arange(n) / 1000.0
    signal = np.zeros(n)
    signal[12_345] = 1.0   # lone positive spike
    signal[54_321] = -1.0  # lone negative spike

    out_t, out_y = decimate_for_plot(time_axis, signal, max_points=1000)

    assert out_y.size <= 1000
    assert out_t.size == out_y.size
    assert np.isclose(out_y.max(), 1.0), "positive peak lost by decimation"
    assert np.isclose(out_y.min(), -1.0), "negative peak lost by decimation"
    assert np.all(np.diff(out_t) >= 0), "time axis must stay monotonic"
    assert out_t[0] >= time_axis[0] and out_t[-1] <= time_axis[-1]


def test_decimate_for_plot_passes_small_input_through():
    """Nothing to gain below the threshold, so the arrays come back untouched."""
    time_axis = np.arange(10) / 10.0
    signal = np.arange(10.0)
    out_t, out_y = decimate_for_plot(time_axis, signal, max_points=8000)
    assert out_t is time_axis and out_y is signal


def test_bands_stay_below_nyquist():
    """Band edges must normalise to < 1.0 or butter() rejects them outright."""
    for fs in (8000, 11025, 16000, 22050, 44100, 48000):
        bands = get_scheirer_bands(fs)
        assert bands, f"no usable bands at fs={fs}"
        for lowcut, highcut in bands:
            assert 0 < lowcut < highcut < fs / 2, f"bad band {(lowcut, highcut)} at fs={fs}"
        # And the filterbank must actually build at that rate.
        create_filterbank(np.zeros(fs, dtype=float), fs, bands)
