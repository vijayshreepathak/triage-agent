"""Run the 100-case clinical dataset through a live triage server.

Usage (server must be running, e.g. `uvicorn app.api.main:app`):

    python scripts/evaluate_dataset.py                     # all 100 cases
    python scripts/evaluate_dataset.py --case case_025     # single case
    python scripts/evaluate_dataset.py --concurrency 2     # be gentle on rate limits

Writes one JSON result per line to results.jsonl and prints an urgency
distribution + search-usage summary at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

import httpx

DATASET_URL = "https://ai-stance.vercel.app/api/cases"


async def _fetch_cases(client: httpx.AsyncClient, dataset_url: str) -> list[dict[str, str]]:
    response = await client.get(dataset_url)
    response.raise_for_status()
    return response.json()["cases"]


async def _triage_one(
    client: httpx.AsyncClient, base_url: str, case: dict[str, str], semaphore: asyncio.Semaphore
) -> dict[str, object]:
    async with semaphore:
        response = await client.post(
            f"{base_url}/triage",
            json={"patient_id": case["patient_id"], "message": case["message"]},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset-url", default=DATASET_URL)
    parser.add_argument("--case", default=None, help="Run a single case, e.g. case_025")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--out", default="results.jsonl")
    args = parser.parse_args()

    async with httpx.AsyncClient() as client:
        cases = await _fetch_cases(client, args.dataset_url)
        if args.case:
            cases = [c for c in cases if c["patient_id"] == args.case]
            if not cases:
                raise SystemExit(f"case {args.case!r} not found in dataset")

        semaphore = asyncio.Semaphore(args.concurrency)
        results = await asyncio.gather(
            *(_triage_one(client, args.base_url, case, semaphore) for case in cases),
            return_exceptions=True,
        )

    ok: list[dict[str, object]] = []
    failures = 0
    with Path(args.out).open("w", encoding="utf-8") as fh:
        for case, result in zip(cases, results, strict=True):
            if isinstance(result, BaseException):
                failures += 1
                print(f"FAILED {case['patient_id']}: {result!r}")
                continue
            ok.append(result)
            fh.write(json.dumps(result) + "\n")

    print(f"\ncompleted: {len(ok)}  failed: {failures}  -> {args.out}")
    if ok:
        urgency_counts = Counter(str(r["urgency_level"]) for r in ok)
        searched = sum(1 for r in ok if r["sources"])
        print(f"urgency distribution: {dict(urgency_counts)}")
        print(f"responses with grounded sources: {searched}/{len(ok)}")
        if args.case:
            print("\n" + json.dumps(ok[0], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
