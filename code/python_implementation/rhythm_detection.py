"""Command-line entry point for the filterbank-based rhythm detector.

Decodes each input file, splits it into frequency bands, extracts an onset
signal per band and scores it against a bank of comb filters, then writes the
analysis plots and reports the detected fundamental tempo.

Files to analyse must be named explicitly, either as arguments or via
``--default-tracks`` for the two bundled samples.
"""
import logging
import sys

import numpy as np

import app_paths
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


DEFAULT_TRACKS_FLAG = "--default-tracks"


def default_tracks() -> list[str]:
    """Paths to the bundled sample tracks that are present on this machine.

    Thin wrapper over app_paths.bundled_tracks(), which knows the several places
    the audio can live depending on whether this is a source checkout, a bundle
    with the tracks embedded, or an unzipped download with a sibling
    music_files/ folder. Only existing paths come back, so a short list here
    means the samples are genuinely unavailable.
    """
    return app_paths.bundled_tracks()


def resolve_input_files(argv: list[str]) -> tuple[list[str], int]:
    """Turn command-line arguments into the list of files to analyse.

    Returns ``(files, exit_code)``; a non-zero exit code means nothing should be
    analysed and the reason has already been logged.

    Selecting the bundled samples is deliberate, never implicit: an empty
    command line used to quietly analyse them, which made the two sample tracks
    look like part of every run's output.
    """
    args = [a for a in argv if a.strip()]

    if DEFAULT_TRACKS_FLAG in args:
        file_paths = default_tracks()
        if len(file_paths) < len(app_paths.SAMPLE_TRACK_NAMES):
            logger.error("%s was given but the bundled sample tracks are not available. "
                         "Looked in:\n%s", DEFAULT_TRACKS_FLAG, app_paths.music_dir_hint())
            return [], 2
        logger.info("Using the %d bundled sample track(s):\n%s", len(file_paths),
                    "\n".join(f"  {i}) {p}" for i, p in enumerate(file_paths, start=1)))
        # Any other arguments are analysed too, so the samples can be compared
        # against a track of your own in a single run.
        file_paths += [a for a in args if a != DEFAULT_TRACKS_FLAG]
        return file_paths, 0

    if not args:
        logger.error("No input files given.")
        logger.error("Pass the audio files to analyse as arguments, e.g. "
                     "`python rhythm_detection.py track1.mp3 track2.mp3`, "
                     "or use %s for the two bundled samples.", DEFAULT_TRACKS_FLAG)
        return [], 2

    logger.info("Using %d CLI-provided file(s):\n%s", len(args),
                "\n".join(f"  {i}) {p}" for i, p in enumerate(args, start=1)))
    return args, 0


def main() -> int:
    """Analyse each input file and write its plots. Returns a process exit code."""
    file_paths, exit_code = resolve_input_files(sys.argv[1:])
    if exit_code:
        return exit_code

    # Frozen builds cannot write next to the executable (see app_paths.results_dir).
    results_dir = app_paths.ensure_results_dir()
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
