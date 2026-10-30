"""Measure how stable and how accurate the scoring is.

Usage (from the backend folder, with a real GROQ_API_KEY in .env):

    python -m eval.run_eval --runs 5
    python -m eval.run_eval --runs 5 --baseline     # also run the old LLM-invented score

For every resume the full pipeline runs several times. We report:
  * the spread of scores between runs (smaller is better)
  * the rank correlation with the human scores in cases.json (closer to 1 is better)

Put your own resumes (remove personal details first) in sample_data/ and list them in cases.json.
"""
import argparse
import json
from pathlib import Path

from app.services import engine
from eval.metrics import mean, spearman, stdev

ROOT = Path(__file__).resolve().parent.parent / "sample_data"


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_new(job_text: str, resume_text: str, runs: int) -> list[float]:
    scores = []
    for _ in range(runs):
        job = engine.parse_jd(job_text)  # parsed again each run so JD variance is included
        scores.append(engine.analyze_resume_text(job, resume_text)["score"])
    return scores


def run_legacy(job_text: str, resume_text: str, runs: int) -> list[float]:
    from eval.legacy import legacy_score

    scores = []
    for _ in range(runs):
        job = engine.parse_jd(job_text)
        resume = engine.parse_resume(resume_text)
        scores.append(legacy_score(job, resume))
    return scores


def summarize(label: str, per_case: list[list[float]], human: list[float]) -> dict:
    means = [mean(s) for s in per_case]
    spreads = [stdev(s) for s in per_case]
    ranges = [max(s) - min(s) for s in per_case]
    corr = spearman(means, human)
    print(f"\n{label}")
    print(f"  average spread between runs (std dev): {mean(spreads):.2f} points")
    print(f"  average worst-case range between runs: {mean(ranges):.2f} points")
    print(f"  rank correlation with human scores:    {corr:.2f}" if corr is not None else "  rank correlation: not enough data")
    return {"std": mean(spreads), "range": mean(ranges), "spearman": corr}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--cases", type=Path, default=ROOT / "cases.json")
    parser.add_argument("--baseline", action="store_true", help="also run the old LLM-invented score")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    human = [float(c["human_score"]) for c in cases]

    new_scores, old_scores = [], []
    print(f"{'case':28} {'human':>6} {'new mean':>9} {'new range':>10}" + (f" {'old mean':>9} {'old range':>10}" if args.baseline else ""))
    for case in cases:
        jd_text = (ROOT / case["jd"]).read_text(encoding="utf-8")
        resume_text = (ROOT / case["resume"]).read_text(encoding="utf-8")
        new = run_new(jd_text, resume_text, args.runs)
        new_scores.append(new)
        line = f"{case['resume']:28} {case['human_score']:>6} {mean(new):>9.1f} {max(new) - min(new):>10.1f}"
        if args.baseline:
            old = run_legacy(jd_text, resume_text, args.runs)
            old_scores.append(old)
            line += f" {mean(old):>9.1f} {max(old) - min(old):>10.1f}"
        print(line)

    new_summary = summarize("NEW: skills checked by AI, score computed in code, temperature 0", new_scores, human)
    if args.baseline:
        old_summary = summarize("OLD: AI invents the percentage, default temperature", old_scores, human)
        if old_summary["std"] > 0:
            drop = 100 * (1 - new_summary["std"] / old_summary["std"])
            print(f"\nScore spread reduced by about {drop:.0f}% (std dev {old_summary['std']:.2f} -> {new_summary['std']:.2f}).")


if __name__ == "__main__":
    main()
