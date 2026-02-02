import pathlib
import json
from datetime import datetime

# -------- CONFIG --------
DECODED_APKS_DIR = pathlib.Path("../decoded-apks")
OUTPUT_DIR = pathlib.Path("../scan-results")
SEARCH_TERMS_FILE = pathlib.Path("search_terms.txt")

MAX_HITS_PER_TERM_PER_FILE = 50   # cap to prevent insane output
MAX_TERMS = 500                   # safety
# ------------------------


def load_search_terms():
    terms = []
    for line in SEARCH_TERMS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line.lower())
        if len(terms) >= MAX_TERMS:
            break
    return terms


def find_bytes_all(data: bytes, needle: bytes, max_hits: int):
    """Find up to max_hits occurrences of needle in data; return offsets."""
    hits = []
    start = 0
    nlen = len(needle)
    if nlen == 0:
        return hits

    while len(hits) < max_hits:
        idx = data.find(needle, start)
        if idx == -1:
            break
        hits.append(idx)
        start = idx + 1  # allow overlaps (rare but fine)
    return hits


def scan_file_for_terms(path: pathlib.Path, terms):
    """
    Scan raw bytes for ASCII/UTF-8 and UTF-16LE encodings of each term.
    Returns a list of finding dicts.
    """
    findings = []

    try:
        data = path.read_bytes()
    except Exception as e:
        return [{
            "type": "read_error",
            "term": None,
            "detail": f"{type(e).__name__}: {e}"
        }]

    for term in terms:
        # ASCII/UTF-8
        b_ascii = term.encode("utf-8", errors="ignore")
        if b_ascii:
            offs = find_bytes_all(data, b_ascii, MAX_HITS_PER_TERM_PER_FILE)
            for off in offs:
                findings.append({
                    "type": "bytes_ascii",
                    "term": term,
                    "offset_hex": f"{off:08x}"
                })

        # UTF-16LE
        b_u16 = term.encode("utf-16le", errors="ignore")
        if b_u16:
            offs = find_bytes_all(data, b_u16, MAX_HITS_PER_TERM_PER_FILE)
            for off in offs:
                findings.append({
                    "type": "bytes_utf16le",
                    "term": term,
                    "offset_hex": f"{off:08x}"
                })

    return findings


def main():
    # Resolve based on file location so running from anywhere works
    script_dir = pathlib.Path(__file__).resolve().parent
    repo_root = script_dir.parent

    decoded_dir = (repo_root / "decoded-apks")
    out_dir = (repo_root / "scan-results")
    terms_file = (script_dir / "search_terms.txt")

    # Use the resolved paths
    global DECODED_APKS_DIR, OUTPUT_DIR, SEARCH_TERMS_FILE
    DECODED_APKS_DIR = decoded_dir
    OUTPUT_DIR = out_dir
    SEARCH_TERMS_FILE = terms_file

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    terms = load_search_terms()
    print("CWD:", pathlib.Path(".").resolve())
    print("Decoded APKs:", DECODED_APKS_DIR.resolve(), "exists=", DECODED_APKS_DIR.exists())
    print("Output dir:", OUTPUT_DIR.resolve())
    print("Search terms loaded:", len(terms))

    for apk_dir in DECODED_APKS_DIR.iterdir():
        if not apk_dir.is_dir():
            continue

        print(f"[+] Scanning APK: {apk_dir.name}")

        apk_out = OUTPUT_DIR / apk_dir.name
        apk_out.mkdir(parents=True, exist_ok=True)

        so_files = list(apk_dir.rglob("*.so"))

        results = {
            "apk": apk_dir.name,
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "decoded_path": str(apk_dir.resolve()),
            "summary": {
                "so_count": len(so_files),
                "files_with_term_hits": 0,
                "total_hits": 0
            },
            "matches": []
        }

        files_with_hits = 0
        total_hits = 0

        for so_file in so_files:
            findings = scan_file_for_terms(so_file, terms)

            # keep only actual term hits (ignore read_error in "matches" unless you want it)
            term_hits = [f for f in findings if f.get("term") is not None]

            if term_hits:
                files_with_hits += 1
                total_hits += len(term_hits)

                results["matches"].append({
                    "so_file": str(so_file.relative_to(apk_dir)),
                    "findings": term_hits
                })

        results["summary"]["files_with_term_hits"] = files_with_hits
        results["summary"]["total_hits"] = total_hits

        out_file = apk_out / "matches.json"
        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"    ↳ wrote {out_file} (hit files: {files_with_hits}, total hits: {total_hits})")


if __name__ == "__main__":
    main()
