import sys
from pathlib import Path


if __package__:
    from .services.pronunciation.feature import (
        FeatureExtractionError,
        LPCFeatureExtractor,
    )
    from .services.pronunciation.lpc_evaluator import JsonReferenceRepository
else:
    package_directory = Path(__file__).resolve().parent
    sys.path.insert(0, str(package_directory.parent))
    from Legendaryvowels.services.pronunciation.feature import (
        FeatureExtractionError,
        LPCFeatureExtractor,
    )
    from Legendaryvowels.services.pronunciation.lpc_evaluator import (
        JsonReferenceRepository,
    )


def generate_references(
    audio_directory: Path,
    output_directory: Path,
) -> int:
    extractor = LPCFeatureExtractor()
    repository = JsonReferenceRepository(output_directory)
    audio_files = sorted(
        path
        for path in audio_directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".mp3"
    )
    if not audio_files:
        print(f"MP3 정답 음성을 찾을 수 없습니다: {audio_directory}")
        return 1

    failures = 0
    for audio_path in audio_files:
        vowel = audio_path.stem
        try:
            lpc_result = extractor.extract(str(audio_path))
            output_path = repository.save(vowel, lpc_result)
            print(f"[OK] {audio_path.name} -> {output_path.name}")
        except (FeatureExtractionError, ValueError, OSError) as error:
            failures += 1
            print(f"[FAIL] {audio_path.name}: {error}")

    return 1 if failures else 0


def main() -> None:
    directory = Path(__file__).resolve().parent
    exit_code = generate_references(
        directory / "reference_audio",
        directory / "reference_lpc",
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
