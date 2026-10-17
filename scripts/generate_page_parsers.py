"""Materialize one standalone parser module for every configured archive page."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
ASSESSORS = ROOT / "data" / "assessors"
SOURCE_DIR = ROOT / "scrapers" / "assessors"

PARSERS = {
    "acm-ccs": ("acm_ccs", "parse_acm_ccs", "direct"),
    "black-hat": ("black_hat", "parse_black_hat_page", "black_hat"),
    "blue-team-con": ("blue_team_con", "parse_blue_team_con", "direct"),
    "bluehat": ("bluehat", "parse_bluehat", "direct"),
    "cansecwest": ("cansecwest", "parse_cansecwest", "direct"),
    "ccc": ("ccc", "parse_ccc", "direct"),
    "def-con": ("def_con", "parse_def_con_page", "def_con"),
    "derbycon": ("derbycon", "parse_derbycon", "direct"),
    "grrcon": ("grrcon", "parse_grrcon", "direct"),
    "hitb": ("hitb", "parse_hitb_session", "direct"),
    "ieee-sp": ("ieee_sp", "parse_ieee_sp", "direct"),
    "layer-one": ("layer_one", "parse_layer_one", "direct"),
    "ndss": ("ndss", "parse_index", "direct"),
    "offensivecon": ("offensivecon", "parse_offensivecon", "offensivecon"),
    "usenix-security": ("usenix_security", "parse_usenix_security", "direct"),
}


def _page_id(index: int, url: str) -> str:
    path = urlsplit(url).path.strip("/") or "root"
    slug = re.sub(r"[^a-z0-9]+", "-", path.casefold()).strip("-") or "root"
    return f"page-{index:03d}-{slug[:80]}"


def _year(url: str) -> int:
    matches = re.findall(r"(?:19|20)\d{2}", url)
    return int(matches[-1]) if matches else 0


def _module_text(assessor_id: str, index: int, url: str) -> str:
    source_name, parser_name, mode = PARSERS[assessor_id]
    source = (SOURCE_DIR / f"{source_name}.py").read_text(encoding="utf-8")
    source = source.replace("from ..", "from scrapers.")
    source = source.replace("from __future__ import annotations\n", "")
    page_id = _page_id(index, url)
    year = _year(url)
    if mode == "black_hat":
        region = "middle-east" if "mea" in url.casefold() else "usa"
        call = f"return {parser_name}(body, source_url, {year}, {region!r})"
    elif mode == "def_con":
        number = next(iter(re.findall(r"defcon[-_/]?(\d+)", url.casefold())), "0")
        call = f"return {parser_name}({int(number)}, body, source_url, None)"
    elif mode == "offensivecon":
        call = f"return {parser_name}(body, source_url, {year})"
    else:
        call = f"return {parser_name}(body, source_url)"
    return (
        f'"""Standalone parser for archive page {url}."""\n'
        f"from __future__ import annotations\n\n"
        f"# This file owns exactly one archived page; do not broaden its URL scope.\n"
        f"PAGE_ID = {page_id!r}\n"
        f"SOURCE_URL = {url!r}\n"
        f"YEAR = {year}\n\n"
        f"{source}\n\n"
        f"def parse_page(body: bytes | str, source_url: str = SOURCE_URL):\n"
        f"    {call}\n"
    )


def main() -> None:
    generated: set[Path] = set()
    for config_path in sorted(ASSESSORS.glob("*.json")):
        assessor_id = config_path.stem
        if assessor_id not in PARSERS:
            continue
        document = json.loads(config_path.read_text(encoding="utf-8"))
        urls = document.get("links", {}).get("processUrls", [])
        output_dir = SOURCE_DIR / assessor_id
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, url in enumerate(urls, 1):
            path = output_dir / f"{_page_id(index, url)}.py"
            path.write_text(_module_text(assessor_id, index, url), encoding="utf-8")
            generated.add(path)
    print(f"generated {len(generated)} page parser modules")


if __name__ == "__main__":
    main()
