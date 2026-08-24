"""Command-line entry point for the filterbank-based rhythm detector.

Decodes each input file, splits it into frequency bands, extracts an onset
signal per band and scores it against a bank of comb filters, then writes the
analysis plots and reports the detected fundamental tempo.
"""
import logging
import os
import sys

import numpy as np

from comb_filter_module import analyze_tempo
from diff_rect_module import diff_rect
from envelope_module import get_envelope
from filterbank_module import read_audio, bandpass_filter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rhythm_detection")

def get_scheirer_bands(fs: int) -> list[tuple[float, float]]:
    """
    Define the frequency bands for analysis (can be expanded as needed).

    Every edge must stay strictly below Nyquist -- butter() rejects a normalised
    cutoff of exactly 1.0 -- so bands are clipped against the sample rate rather
    than assumed to fit. At 44.1 kHz all six survive untouched; at low rates the
    bands that no longer fit are narrowed or dropped instead of raising.
    """
    edges = [1, 200, 400, 800, 1600, 3200, 5000]
    # Stay a hair under Nyquist so the top edge normalises to < 1.0.
    limit = 0.999 * (fs / 2)

    bands: list[tuple[float, float]] = []
    for lowcut, highcut in zip(edges, edges[1:]):
        if lowcut >= limit:
            break  # band starts at or above Nyquist: nothing left to analyse
        bands.append((float(lowcut), float(min(highcut, limit))))

    if not bands:
        raise ValueError(f"Sample rate {fs} Hz is too low for any analysis band.")
    logger.debug("Bands for fs=%d Hz: %s", fs, bands)
    return bands

def format_tempo_line(filename: str, bpm: float) -> str:
    """Build the machine-readable result line the GUI parses off stdout.

    The GUI matches these with ``GUI_functionality.TEMPO_LINE_RE``. Defined as a
    function so the format lives in exactly one place and the producer/consumer
    agreement can be tested; the BPM precedes the path so that a path containing
    spaces is still captured whole.
    """
    return f"TEMPO: {bpm:.2f} BPM {filename}"


def default_tracks() -> list[str]:
    """Paths to the bundled sample tracks, used when the CLI provides no files.

    The audio lives in <repo>/music_files, i.e. two levels above this module
    (<repo>/code/python_implementation/). When frozen by PyInstaller there is no
    repo tree, so look for a music_files folder next to the executable instead.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return [os.path.join(base, "music_files", name)
            for name in ("pathfinder.mp3", "celebration.mp3")]


def main() -> int:
    """Analyse each input file and write its plots. Returns a process exit code."""
    # Determine input files: analyse whatever the CLI provides, else fall back
    # to the bundled sample tracks.
    cli_files = [p for p in sys.argv[1:] if p.strip()]
    if cli_files:
        file_paths = cli_files
        logger.info("Using %d CLI-provided file(s):\n%s", len(file_paths),
                    "\n".join(f"  {i}) {p}" for i, p in enumerate(file_paths, start=1)))
    else:
        file_paths = default_tracks()
        logger.warning("No files given on the command line; falling back to defaults:\n%s",
                       "\n".join(f"  {i}) {p}" for i, p in enumerate(file_paths, start=1)))
        missing = [p for p in file_paths if not os.path.isfile(p)]
        if missing:
            logger.error("The bundled sample tracks are not available:\n%s",
                         "\n".join(f"  {p}" for p in missing))
            logger.error("Pass the audio files to analyse as arguments, e.g. "
                         "`python rhythm_detection.py track1.mp3 track2.mp3`.")
            return 2

    # Prepare output directory. When frozen by PyInstaller the script lives in a
    # temporary extraction dir (_MEIPASS) that is deleted on exit, so write the
    # results next to the executable instead; otherwise write next to this script.
    if getattr(sys, "frozen", False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(script_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    logger.info("Results directory: %s", results_dir)

    # Imported here rather than at module scope so that importing this module
    # (e.g. from the tests) does not pull in matplotlib.
    from plot_handler import save_plots  # pylint: disable=import-outside-toplevel
    logger.info("Plot handler loaded.")

    # Tempo search range
    tempo_range = np.arange(60, 180, 1, dtype=float)
    logger.info("Tempo range: %d to %d BPM (step 1)", int(tempo_range.min()), int(tempo_range.max()))

    for idx, filename in enumerate(file_paths, start=1):
        logger.info("(%d/%d) Processing file: %s", idx, len(file_paths), filename)

        # Read audio
        try:
            signal, fs = read_audio(filename)
            logger.info("Read audio: fs=%d Hz, samples=%d", fs, len(signal))
        except Exception:
            logger.exception("Failed to read audio file: %s", filename)
            continue

        # Frequency bands
        bands = get_scheirer_bands(fs)
        logger.info("Bands: %s", ", ".join(f"{lo:g}-{hi:g} Hz" for (lo, hi) in bands))

        # Build time axis for original signal
        t = np.arange(len(signal)) / fs

        # Per-band energies collection (for plotting).
        #
        # One band at a time rather than create_filterbank's full list: each
        # filtered copy is the same size as the input (86 MB for a 4-minute
        # track), so materialising all six costs ~0.5 GB to no purpose. The
        # intermediates are dropped as soon as the next stage has consumed them.
        per_band_energies: list[np.ndarray] = []
        for b_idx, (lo, hi) in enumerate(bands, start=1):
            logger.info("Band %d/%d (%g-%g Hz): filter -> envelope -> diff-rect -> comb energies",
                        b_idx, len(bands), lo, hi)
            try:
                filtered_signal = bandpass_filter(signal, lo, hi, fs)
                envelope = get_envelope(filtered_signal, fs)
                del filtered_signal
                diff_rect_signal = diff_rect(envelope)
                del envelope
                energies = analyze_tempo(diff_rect_signal, fs, tempo_range)
                del diff_rect_signal
                per_band_energies.append(energies)
                logger.info("Band %d energies computed (len=%d)", b_idx, len(energies))
            except Exception:
                logger.exception("Failed processing band %d (%g-%g Hz)", b_idx, lo, hi)
                per_band_energies.append(np.zeros_like(tempo_range))

        # Delegate plotting and saving to the plot handler
        try:
            analysis_path, total_path, fundamental_tempo = save_plots(
                input_filename=filename,
                time_axis=t,
                original_signal=signal,
                bands=bands,
                tempo_range=tempo_range,
                per_band_energies=per_band_energies,
                results_dir=results_dir,
            )
            logger.info("Saved plots:\n  analysis: %s\n  total: %s", analysis_path, total_path)
            # Machine-readable result line on stdout, alongside the SAVED: lines
            # that plot_handler prints. The GUI parses these to show the tempo,
            # so the path is included: a file that fails earlier prints nothing
            # at all, which would silently shift a positional match.
            logger.info("Fundamental Tempo: %.2f BPM", fundamental_tempo)
            print(format_tempo_line(filename, fundamental_tempo))
        except Exception:
            logger.exception("Failed to save plots for: %s", filename)
            continue

    logger.info("Processing completed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
