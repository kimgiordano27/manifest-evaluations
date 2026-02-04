from pathlib import Path
import csv
from collections import defaultdict


INPUT_TXT = Path(r"../scan-results/master-results.txt")
OUT_DIR = Path(r"../scan-results/exports")
OUT_DIR.mkdir(parents=True, exist_ok=True)


OUT_WIDE_CSV = OUT_DIR / "app_functionality.csv"
OUT_LONG_CSV = OUT_DIR / "app_functionality_long.csv"
OUT_TXT = OUT_DIR / "app_functionality.txt"

GAME_PREFIX = "===== GAME:"
CATEGORY_PREFIX = "[CATEGORY]"

def parse_master_results_txt(path: Path) -> dict[str, set[str]]:
    """
    Returns:
      game_to_categories: { "AR-toolkit-decoded": {"Eye-Tracking Enablement", ...}, ... }
    """
    game_to_categories = defaultdict(set)
    current_game = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()

            # New game block
            if line.startswith(GAME_PREFIX):
                # Example: "===== GAME: AR-toolkit-decoded ====="
                # Pull the middle part after "===== GAME:" and before "====="
                current_game = line[len(GAME_PREFIX):].strip()
                if current_game.endswith("====="):
                    current_game = current_game[:-5].strip()
                continue

            # Category line
            # Example: "  [CATEGORY] Eye-Tracking Enablement"
            if CATEGORY_PREFIX in line and current_game:
                # everything after "[CATEGORY]" is the category name
                idx = line.find(CATEGORY_PREFIX)
                cat = line[idx + len(CATEGORY_PREFIX):].strip()
                if cat:
                    game_to_categories[current_game].add(cat)

    return game_to_categories


def write_wide_csv(game_to_categories: dict[str, set[str]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "detected_functionality"])
        for game in sorted(game_to_categories.keys()):
            cats = sorted(game_to_categories[game])
            w.writerow([game, "; ".join(cats)])


def write_long_csv(game_to_categories: dict[str, set[str]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "functionality"])
        for game in sorted(game_to_categories.keys()):
            for cat in sorted(game_to_categories[game]):
                w.writerow([game, cat])


def write_txt(game_to_categories: dict[str, set[str]], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        for game in sorted(game_to_categories.keys()):
            cats = sorted(game_to_categories[game])
            f.write(f"{game}:\n")
            for cat in cats:
                f.write(f"  - {cat}\n")
            f.write("\n")


def main():
    game_to_categories = parse_master_results_txt(INPUT_TXT)

    write_wide_csv(game_to_categories, OUT_WIDE_CSV)
    write_long_csv(game_to_categories, OUT_LONG_CSV)
    write_txt(game_to_categories, OUT_TXT)

    print(f"Parsed {len(game_to_categories)} apps.")
    print(f"Wrote:\n  {OUT_WIDE_CSV}\n  {OUT_LONG_CSV}\n  {OUT_TXT}")


if __name__ == "__main__":
    main()
