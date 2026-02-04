import pathlib
import json
import csv
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict


MAX_TERMS = 500
MAX_EXAMPLES_PER_TERM_PER_FILE = 25   
REBUILD_MASTER_RESULTS = True         
WRITE_CSV_SUMMARY = True             





CATEGORY_RULES = [
    # 1) Foveated rendering
    ("Foveated Rendering",
     {"foveation", "foveated rendering", "foveated graphics", "foveated display", "foveated rendering mode", "foveated"},
     {"foveat"}),

    # 2) Raw data collection / state APIs
    ("Raw Data Collection",
     {"EyeTrackingProvider", "EyeTrackingState", "GazeProvider",
      "ovrp_GetEyeGazesState", "ovrp_GetEyeTrackingState", "ovrp_GetEyeTrackingState2",
      "ovrpEyeGazesState", "ovrpEyeGaze", "ovrpEyeTrackingState",
      "GetEyeGazeData"},
     {"ovrp_GetEye", "ovrpEye", "EyeTrackingState", "EyeTrackingProvider", "GetEyeGazeData"}),

    # 3) Capability / enablement / supported checks
    ("Eye-Tracking Enablement",
     {"EyeTracked", "eyeTrackingSupported", "eyeGazeSupported",
      "ovrp_SetEyeTrackingEnabled", "ovrp_GetEyeTrackingEnabled",
      "FOculusEyeTracking", "IOculusEyeTrackerModule", "eye tracking",
      "XR_EXT_eye_gaze_interaction", "xrLocateEyeGazesEXT", "XrEyeGazesEXT", "XrEyeGazeEXT", "XrEyeGazesInfoEXT",
      "xrLocateEyeGazes", "XR_EXT_eye_gaze_interaction", "XrEyeGaze"},
     {"Supported", "SetEyeTrackingEnabled", "GetEyeTrackingEnabled", "OculusEye"}),

    # 4) Interaction / selection input (dwell-to-click etc.)
    ("Gaze Interactions",
     {"EyeGazeInteractor", "GazeInteractor",
      "interaction selection", "dwell time"},
     {"Interactor", "dwell", "selection", "gaze input"}),

    # 5) Gaze geometry
    ("Gaze Geometry",
     {"EyeGazeDirection", "EyeGazePosition", "EyeGazeRotation", "EyeOpenAmount", "eyeOpenness"},
     {"GazeDirection", "GazePosition", "GazeRotation", "EyeOpen"}),

    # 6) Biometric signals & metrics
    ("Biometric Signals & Metrics",
        {"PupilDilation", "BlinkRate", "BlinkDuration", "SaccadeVelocity", "SaccadeAmplitude", "fixation", 
         "fixation duration", "attention measurement", "attentionScore", "focused object"},
        {"Pupil", "Blink", "Saccade", "fixation", "attention", "focused object"}), 

]


def categorize_term(term: str):
    """
    Return (category, confidence) for a term based on rules.
    Confidence:
      - high: exact term match
      - medium: substring/pattern match
      - low: fallback assignment
    """
    t = term.strip()
    tl = t.lower()

    for category, exact_terms, substr_patterns in CATEGORY_RULES:
        for e in exact_terms:
            if tl == e.lower():
                return category, "high"
        for p in substr_patterns:
            if p.lower() in tl:
                return category, "medium"

    # If nothing matched any rule, force it into a real category
    # (You can change this default if you prefer a different “catch-all”.)
    return "Eye-Tracking Enablement", "low"



# ------------------------
# IO + scanning
# ------------------------

def load_search_terms(terms_path: pathlib.Path):
    terms = []
    for line in terms_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
        if len(terms) >= MAX_TERMS:
            break
    return terms


def collect_matching_lines(text: str, term: str, limit: int):
    """Return up to `limit` lines containing `term` (case-insensitive)."""
    
    t = term.lower()
    out = []
    for line in text.splitlines():
        if t in line.lower():
            out.append(line.rstrip("\n"))
            if len(out) >= limit:
                break
    return out


def scan_text_file(txt_path: pathlib.Path, terms):
    """
    Case-insensitive scan of a normalized ASCII text file.
    Returns a list of hits: {term, category, confidence, examples[]}
    """
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [{"type": "read_error", "term": None, "detail": f"{type(e).__name__}: {e}"}]

    lower_text = text.lower()
    hits = []

    for term in terms:
        if term.lower() in lower_text:
            examples = collect_matching_lines(text, term, MAX_EXAMPLES_PER_TERM_PER_FILE)
            category, conf = categorize_term(term)
            hits.append({
                "term": term,
                "category": category,
                "category_confidence": conf,
                "examples": examples
            })

    return hits


def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    repo_root = script_dir.parent

    scan_results_dir = repo_root / "scan-results"
    terms_path = script_dir / "search_terms.txt"

    print("Scan results:", scan_results_dir.resolve(), "exists=", scan_results_dir.exists())
    print("Terms file:", terms_path.resolve(), "exists=", terms_path.exists())

    terms = load_search_terms(terms_path)
    print("Search terms loaded:", len(terms))

    scan_results_dir.mkdir(parents=True, exist_ok=True)

    # Build master report in memory grouped by game
    master_lines: List[str] = []
    master_lines.append("# master-results.txt")
    master_lines.append("# One report containing only matches from scanning normalized ASCII outputs")
    master_lines.append("# Grouped by GAME -> FILE -> CATEGORY -> TERM")
    master_lines.append(f"# generated_utc: {datetime.now(timezone.utc).isoformat()}")
    master_lines.append("")
    master_lines.append("")

    # Collect CSV rows
    csv_rows: List[Dict[str, str]] = []

    # seperates out any APKS that have eye tracking enabled but no other use cases
    enablement_only_apks: List[str] = []
    FALLBACK_CATEGORY = "Eye-Tracking Enablement"



    # Iterate APK folders under scan-results
    apk_dirs = sorted([p for p in scan_results_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower())

    for apk_out in apk_dirs:
        normalized_ascii_dir = apk_out / "normalized" / "ascii"
        if not normalized_ascii_dir.exists():
            continue

        print(f"[+] Scanning normalized ASCII for: {apk_out.name}")

        txt_files = sorted(list(normalized_ascii_dir.rglob("*.txt")), key=lambda p: str(p).lower())

        results = {
            "apk": apk_out.name,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "normalized_ascii_path": str(normalized_ascii_dir.resolve()),
            "summary": {
                "txt_files_scanned": len(txt_files),
                "files_with_hits": 0,
                "total_term_hits": 0
            },
            "matches": []
        }

        files_with_hits = 0
        total_term_hits = 0

        # Master section for this game
        game_block: List[str] = []
        game_block.append(f"===== GAME: {apk_out.name} =====")
        game_block.append("")

        for txt in txt_files:
            hits = scan_text_file(txt, terms)
            term_hits = [h for h in hits if h.get("term") is not None]

            if not term_hits:
                continue

            files_with_hits += 1
            total_term_hits += len(term_hits)

            # Save per-APK JSON result
            results["matches"].append({
                "txt_file": str(txt.relative_to(apk_out)),
                "hits": term_hits
            })

            # Group master output: FILE -> CATEGORY -> TERM
            # First group term_hits by category
            by_cat: Dict[str, List[dict]] = {}
            for h in term_hits:
                by_cat.setdefault(h["category"], []).append(h)

                # Add CSV rows (one row per hit term per file)
                csv_rows.append({
                    "apk": apk_out.name,
                    "txt_file": str(txt.relative_to(apk_out)).replace("\\", "/"),
                    "category": h["category"],
                    "category_confidence": h["category_confidence"],
                    "term": h["term"],
                    "example_count": str(len(h.get("examples", [])))
                })

            game_block.append(f"File: {txt.relative_to(apk_out).as_posix()}")
            # categories in stable order: alphabetical, with unknown last
            cats = sorted(by_cat.keys())
            for cat in cats:
                game_block.append(f"  [CATEGORY] {cat}")
                for h in by_cat[cat]:
                    game_block.append(f"    TERM: {h['term']} (confidence={h['category_confidence']})")
                    for line in h["examples"]:
                        game_block.append(f"      {line}")
                    game_block.append("")
            game_block.append("")  # blank line between files

        results["summary"]["files_with_hits"] = files_with_hits
        results["summary"]["total_term_hits"] = total_term_hits
        # --- enablement-only detection for this APK ---
        all_hits = [
            h
            for m in results["matches"]
            for h in m.get("hits", [])
        ]

        has_enablement = any(h.get("category") == FALLBACK_CATEGORY for h in all_hits)
        has_non_enablement = any(h.get("category") != FALLBACK_CATEGORY for h in all_hits)

        if has_enablement and not has_non_enablement:
            enablement_only_apks.append(apk_out.name)


        # Write per-APK JSON
        out_file = apk_out / "scan_matches.json"
        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"    ↳ wrote {out_file} (files_with_hits: {files_with_hits}, total_term_hits: {total_term_hits})")

        # Only add the game section to master if there were hits
        if files_with_hits > 0:
            master_lines.extend(game_block)
            master_lines.append("")

    # Write master report once
    master_path = scan_results_dir / "master-results.txt"
    mode = "w" if REBUILD_MASTER_RESULTS else "a"
    with master_path.open(mode, encoding="utf-8", errors="replace") as f:
        f.write("\n".join(master_lines))
        if not master_lines[-1].endswith("\n"):
            f.write("\n")
    print(f"[+] Wrote master results grouped by game: {master_path.resolve()}")

    # Write CSV summary once
    if WRITE_CSV_SUMMARY:
        csv_path = scan_results_dir / "scan_summary.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["apk", "txt_file", "category", "category_confidence", "term", "example_count"]
            )
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        print(f"[+] Wrote CSV summary: {csv_path.resolve()}")

    print("\n=== APKs with ONLY Eye-Tracking Enablement hits ===")
    if enablement_only_apks:
        for name in enablement_only_apks:
            print(" -", name)
    else:
        print(" (none)")

    (enablement_only_path := scan_results_dir / "enablement_only_apks.txt").write_text(
        "\n".join(enablement_only_apks) + ("\n" if enablement_only_apks else ""),
        encoding="utf-8"
    )
    print(f"[+] Wrote enablement-only list: {enablement_only_path.resolve()}")


if __name__ == "__main__":
    main()
