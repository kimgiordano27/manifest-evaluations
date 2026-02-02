import pathlib
import json
from datetime import datetime, timezone

# -------- CONFIG --------
MIN_ASCII_LEN = 4
MAX_FILES_PER_APK = None  # set to an int for testing, e.g. 50
# ------------------------


def is_printable_ascii(b: int) -> bool:
    # printable ASCII + tab
    return b == 9 or 32 <= b <= 126


def extract_ascii_strings(data: bytes, min_len: int):
    """Yield (offset, string) for printable ASCII runs."""
    i = 0
    n = len(data)
    while i < n:
        if is_printable_ascii(data[i]):
            start = i
            buf = []
            while i < n and is_printable_ascii(data[i]):
                buf.append(data[i])
                i += 1
            if len(buf) >= min_len:
                s = bytes(buf).decode("ascii", errors="ignore")
                yield start, s
        else:
            i += 1


def normalize_one_so_ascii(so_path: pathlib.Path, out_base: pathlib.Path, rel_key: str):
    """
    Write:
      normalized/ascii/<rel_key>.txt
    rel_key should be a stable path-ish key (no drive letters).
    """
    data = so_path.read_bytes()

    ascii_path = out_base / "ascii" / f"{rel_key}.txt"
    ascii_path.parent.mkdir(parents=True, exist_ok=True)

    with ascii_path.open("w", encoding="utf-8", errors="replace") as f:
        for off, s in extract_ascii_strings(data, MIN_ASCII_LEN):
            f.write(f"{off:08x} {s}\n")

    return {"ascii": str(ascii_path)}


def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    repo_root = script_dir.parent

    decoded_apks_dir = repo_root / "decoded-apks"
    scan_results_dir = repo_root / "scan-results"

    print("Decoded APKs:", decoded_apks_dir.resolve(), "exists=", decoded_apks_dir.exists())
    print("Scan results:", scan_results_dir.resolve())

    scan_results_dir.mkdir(parents=True, exist_ok=True)

    for apk_dir in decoded_apks_dir.iterdir():
        if not apk_dir.is_dir():
            continue

        print(f"[+] Normalizing APK: {apk_dir.name}")

        apk_out = scan_results_dir / apk_dir.name
        normalized_dir = apk_out / "normalized"
        apk_out.mkdir(parents=True, exist_ok=True)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        so_files = list(apk_dir.rglob("*.so"))
        if MAX_FILES_PER_APK is not None:
            so_files = so_files[:MAX_FILES_PER_APK]

        meta = {
            "apk": apk_dir.name,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "decoded_path": str(apk_dir.resolve()),
            "summary": {
                "so_count": len(so_files),
                "normalized_count": 0,
                "errors": 0
            },
            "files": []
        }

        normalized_count = 0
        errors = 0

        for so_file in so_files:
            try:
                rel = so_file.relative_to(apk_dir)
                rel_key = "__".join(rel.parts)  # stable filename key

                created = normalize_one_so_ascii(so_file, normalized_dir, rel_key)

                meta["files"].append({
                    "so_file": str(rel),
                    "rel_key": rel_key,
                    "normalized_outputs": created
                })
                normalized_count += 1

            except Exception as e:
                errors += 1
                meta["files"].append({
                    "so_file": str(so_file),
                    "error": f"{type(e).__name__}: {e}"
                })

        meta["summary"]["normalized_count"] = normalized_count
        meta["summary"]["errors"] = errors

        out_meta = apk_out / "normalize_meta.json"
        out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        print(f"    ↳ normalized {normalized_count} .so files (errors: {errors})")
        print(f"    ↳ wrote {out_meta}")


if __name__ == "__main__":
    main()

