# rythm_detection.py

import os
import sys
import numpy as np
import logging

from comb_filter_module import analyze_tempo
from diff_rect_module import diff_rect
from envelope_module import get_envelope
from filterbank_module import read_mp3, create_filterbank

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rythm_detection")

def get_scheirer_bands(fs: int) -> list[tuple[int, int]]:
    """
    Define the frequency bands for analysis (can be expanded as needed).
    """
    nyquist = fs / 2
    return [
        (1, 200),
        (200, 400),
        (400, 800),
        (800, 1600),
        (1600, 3200),
        (3200, min(nyquist, 5000))
    ]

def main() -> int:
    # Determine input files: use CLI args if two provided, else fallback
    cli_files = [p for p in sys.argv[1:] if p.strip()]
    if len(cli_files) == 2:
        file_paths = cli_files
        logger.info("Using CLI-provided files:\n  1) %s\n  2) %s", file_paths[0], file_paths[1])
    else:
        file_paths = [
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "music_files", "pathfinder.mp3")),
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "music_files", "celebration.mp3")),
        ]
        logger.warning("CLI did not provide exactly 2 files; falling back to defaults:\n  1) %s\n  2) %s",
                       file_paths[0], file_paths[1])

    # Prepare output directory next to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(script_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    logger.info("Results directory: %s", results_dir)

    # Import plot handler only when needed (keeps plotting concerns separate)
    from plot_handler import save_plots
    logger.info("Plot handler loaded.")

    # Tempo search range
    tempo_range = np.arange(60, 180, 1, dtype=float)
    logger.info("Tempo range: %d to %d BPM (step 1)", int(tempo_range.min()), int(tempo_range.max()))

    for idx, filename in enumerate(file_paths, start=1):
        logger.info("(%d/%d) Processing file: %s", idx, len(file_paths), filename)

        # Read audio
        try:
            signal, fs = read_mp3(filename)
            logger.info("Read audio: fs=%d Hz, samples=%d", fs, len(signal))
        except Exception as e:
            logger.exception("Failed to read audio file: %s", filename)
            continue

        # Frequency bands
        bands = get_scheirer_bands(fs)
        logger.info("Bands: %s", ", ".join([f"{lo}-{hi} Hz" for (lo, hi) in bands]))

        # Filterbank
        try:
            filtered_signals = create_filterbank(signal, fs, bands)
            logger.info("Created filterbank: %d band(s)", len(filtered_signals))
        except Exception as e:
            logger.exception("Failed to create filterbank for: %s", filename)
            continue

        # Build time axis for original signal
        t = np.arange(len(signal)) / fs

        # Per-band energies collection (for plotting)
        per_band_energies: list[np.ndarray] = []
        for b_idx, filtered_signal in enumerate(filtered_signals, start=1):
            lo, hi = bands[b_idx - 1]
            logger.info("Band %d/%d (%d-%d Hz): envelope -> diff-rect -> comb energies",
                        b_idx, len(filtered_signals), lo, hi)
            try:
                envelope = get_envelope(filtered_signal, fs)
                diff_rect_signal = diff_rect(envelope, fs)
                energies = analyze_tempo(diff_rect_signal, fs, tempo_range)
                per_band_energies.append(energies)
                logger.info("Band %d energies computed (len=%d)", b_idx, len(energies))
            except Exception as e:
                logger.exception("Failed processing band %d (%d-%d Hz)", b_idx, lo, hi)
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
            # Keep the plain prints for GUI auto-detection if needed (SAVED: lines printed by plot_handler)
            logger.info("Fundamental Tempo: %.2f BPM", fundamental_tempo)
            print(f"Fundamental Tempo: {fundamental_tempo} BPM")
        except Exception as e:
            logger.exception("Failed to save plots for: %s", filename)
            continue

    logger.info("Processing completed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())