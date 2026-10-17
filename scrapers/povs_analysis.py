"""Assign POVS levels to endorsements whose matched YouTube transcripts exist."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .logging_config import configure_logging


PROMPT_PATH = Path("scrapers/enrichers/povs/level_prompt.md")


def _video_id(url: str) -> str:
    match = re.search(r"[?&]v=([\w-]{6,})", url)
    return match.group(1) if match else ""


def _stable_key(record: dict[str, Any]) -> str:
    fields = {key: record.get(key) for key in ("assessor-id", "name", "label", "year", "url", "video-id")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _number_transcript(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in normalized.splitlines() if line.strip()]
    numbered = "\n".join(f"{index}: {line}" for index, line in enumerate(lines, 1))
    return numbered, hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_transcripts(archive_path: Path) -> dict[str, tuple[str, str]]:
    with zipfile.ZipFile(archive_path) as archive:
        result: dict[str, tuple[str, str]] = {}
        for member in archive.namelist():
            if not member.startswith("transcripts/") or not member.endswith(".txt"):
                continue
            video_id = Path(member).stem
            text = archive.read(member).decode("utf-8", errors="replace")
            numbered, digest = _number_transcript(text)
            result[video_id] = (numbered, digest)
        return result


def _endorsements_for_assessor(assessor_id: str, individuals_directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(individuals_directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for index, endorsement in enumerate(document.get("endorsements", [])):
            if endorsement.get("assessor-id") != assessor_id:
                continue
            for link in endorsement.get("evidence-links", []):
                video_id = _video_id(str(link.get("url", "")))
                if video_id:
                    records.append({**endorsement, "video-id": video_id, "person-file": str(path), "endorsement-index": index})
                    break
    return records


def _prompt(transcript: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{NUMBERED_TRANSCRIPT}}", transcript)


def _validate_analysis(result: dict[str, Any], transcript: str) -> dict[str, Any]:
    if set(result) != {"level", "insufficient_evidence", "explanation", "citations"}:
        raise ValueError("analysis output has unexpected keys")
    if not isinstance(result["level"], int) or not 1 <= result["level"] <= 6:
        raise ValueError("level must be an integer from 1 through 6")
    if not isinstance(result["insufficient_evidence"], bool) or not isinstance(result["explanation"], str):
        raise ValueError("invalid analysis scalar fields")
    lines = {index: line for index, line in enumerate(transcript.splitlines(), 1)}
    seen: set[tuple[int, int]] = set()
    for citation in result["citations"]:
        start, end = citation.get("start_line"), citation.get("end_line")
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or start > end or (start, end) in seen:
            raise ValueError("invalid or duplicate citation range")
        expected = "\n".join(lines.get(index, "").split(": ", 1)[-1] for index in range(start, end + 1))
        if citation.get("quote") != expected:
            raise ValueError("citation quote does not exactly match transcript")
        seen.add((start, end))
    return result


def analyze_assessor(
    assessor_id: str,
    *,
    archive_directory: Path = Path("data/archives/yt-transcripts"),
    individuals_directory: Path = Path("data/individuals"),
    output_directory: Path = Path("data/enrichments"),
    model: str = "gpt-4.1-mini",
    prepare_only: bool = False,
) -> dict[str, int]:
    archive_path = archive_directory / f"{assessor_id}-transcripts.zip"
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    transcripts = _load_transcripts(archive_path)
    matched = [item for item in _endorsements_for_assessor(assessor_id, individuals_directory) if item["video-id"] in transcripts]
    output_path = output_directory / f"{assessor_id}-youtube-recordings" / "povs-analysis.json"
    previous: dict[str, Any] = {}
    if output_path.is_file():
        previous = {item["endorsement-key"]: item for item in json.loads(output_path.read_text(encoding="utf-8")).get("results", []) if item.get("status") == "analyzed"}
    client = None
    if not prepare_only:
        from openai import OpenAI
        client = OpenAI()
    results: list[dict[str, Any]] = []
    pending_records: list[dict[str, Any]] = []
    analyzed = skipped = pending = 0
    for item in matched:
        transcript, transcript_hash = transcripts[item["video-id"]]
        key = _stable_key(item)
        old = previous.get(key)
        if old and old.get("transcript-sha256") == transcript_hash and old.get("prompt-sha256") == hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest():
            results.append(old)
            skipped += 1
            continue
        base = {
            "endorsement-key": key,
            "assessor-id": assessor_id,
            "person-file": item["person-file"],
            "endorsement-index": item["endorsement-index"],
            "name": item.get("name", ""),
            "label": item.get("label", ""),
            "video-id": item["video-id"],
            "transcript-member": f"transcripts/{item['video-id']}.txt",
            "transcript-sha256": transcript_hash,
            "prompt-sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        }
        if prepare_only:
            base["status"] = "pending_model_analysis"
            pending_records.append(base)
            pending += 1
            continue
        response = client.chat.completions.create(model=model, temperature=0, seed=0, response_format={"type": "json_object"}, messages=[{"role": "user", "content": _prompt(transcript)}])
        analysis = _validate_analysis(json.loads(response.choices[0].message.content), transcript)
        results.append({**base, "status": "analyzed", "povs-level": analysis["level"], "analysis": analysis})
        analyzed += 1
    output_directory.joinpath(f"{assessor_id}-youtube-recordings").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema-version": "1",
        "assessor-id": assessor_id,
        "results": sorted(results, key=lambda item: item["endorsement-key"]),
        "pending": sorted(pending_records, key=lambda item: item["endorsement-key"]),
    }
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output_path)
    return {"matched": len(matched), "analyzed": analyzed, "skipped": skipped, "pending": pending}


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="povs-analysis")
    parser.add_argument("--assessor", required=True)
    parser.add_argument("--model", default=os.getenv("POVS_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    result = analyze_assessor(args.assessor, model=args.model, prepare_only=args.prepare_only)
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
