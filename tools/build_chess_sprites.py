# tools/build_chess_sprites.py
#
# Offline tool:
#   Convert web-downloaded chess piece PNGs into normalized runtime sprites
#   with the exact names the app expects.
#
# Reads from:
#   assets/raw_sprites/   (non-recursive; also accepts assets/raw_sprites/assets/ if present)
#
# Writes to:
#   assets/sprites/
#
# Output files (exact):
#   wp.png, wn.png, wb.png, wr.png, wq.png, wk.png,
#   bp.png, bn.png, bb.png, br.png, bq.png, bk.png

from __future__ import annotations

from pathlib import Path
import shutil
import time
import ui


# ----------------------------
# CONFIG (edit these)
# ----------------------------

OUT_SIZE = 512  # 256 or 512 safe for Scene

RAW_SPRITES_DIR = Path("assets/raw_sprites")
OUTPUT_SPRITES_DIR = Path("assets/sprites")


# ----------------------------
# Constants
# ----------------------------

TARGETS = {
    "wp.png", "wn.png", "wb.png", "wr.png", "wq.png", "wk.png",
    "bp.png", "bn.png", "bb.png", "br.png", "bq.png", "bk.png",
}

PIECE_LETTERS = ("p", "n", "b", "r", "q", "k")


# ----------------------------
# Paths
# ----------------------------

def project_root() -> Path:
    # tools/ -> project root
    return Path(__file__).resolve().parent.parent

def raw_sprites_dir() -> Path:
    return project_root() / RAW_SPRITES_DIR

def output_sprites_dir() -> Path:
    return project_root() / OUTPUT_SPRITES_DIR

def input_dirs() -> list[Path]:
    """
    Primary: assets/raw_sprites/
    Also accept: assets/raw_sprites/assets/ (in case downloads were nested)
    """
    base = raw_sprites_dir()
    dirs = [base]
    nested = base / "assets"
    if nested.is_dir():
        dirs.append(nested)
    return dirs


# ----------------------------
# Detection helpers
# ----------------------------

def _detect_color(filename: str) -> str | None:
    """
    Return 'w' or 'b' from common downloaded naming patterns.
    Supports:
      - lt45/dt45 (your original convention)
      - 'white'/'black'
      - some token-ish hints
    """
    n = filename.lower()

    if "lt45" in n:
        return "w"
    if "dt45" in n:
        return "b"

    if "white" in n or "wht" in n:
        return "w"
    if "black" in n or "blk" in n:
        return "b"

    # token-ish hints (best effort)
    if "_w" in n or "-w" in n or " w" in n:
        return "w"
    if "_b" in n or "-b" in n or " b" in n:
        return "b"

    return None

def _detect_piece(filename: str) -> str | None:
    """
    Return one of p n b r q k from filename.
    Supports:
      - piece words
      - single-letter tokens (e.g. _p, -p)
      - lt45/dt45 forms
    """
    n = filename.lower()

    # Words first (less ambiguous)
    if "pawn" in n:
        return "p"
    if "knight" in n:
        return "n"
    if "bishop" in n:
        return "b"
    if "rook" in n:
        return "r"
    if "queen" in n:
        return "q"
    if "king" in n:
        return "k"

    for k in PIECE_LETTERS:
        if f"_{k}" in n or f"-{k}" in n or f"{k}lt45" in n or f"{k}dt45" in n:
            return k

    return None

def detect_target_name(filename: str) -> str | None:
    """
    Produce the exact runtime sprite filename (e.g., 'wp.png') or None if unrecognized.
    """
    color = _detect_color(filename)
    if not color:
        return None
    piece = _detect_piece(filename)
    if not piece:
        return None
    return f"{color}{piece}.png"


# ----------------------------
# Rendering
# ----------------------------

def safe_rerender_png(src_path: Path, dst_path: Path, out_size: int):
    data = src_path.read_bytes()
    img = ui.Image.from_data(data)
    if img is None:
        raise RuntimeError("Image decode failed")

    # Force a known-size RGBA canvas and scale to fill the square.
    with ui.ImageContext(out_size, out_size) as ctx:
        ui.set_color((0, 0, 0, 0))
        ui.Path.rect(0, 0, out_size, out_size).fill()
        img.draw(0, 0, out_size, out_size)
        fixed = ctx.get_image()

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(fixed.to_png())


# ----------------------------
# IO helpers
# ----------------------------

def iter_candidate_pngs(dirs: list[Path]) -> list[Path]:
    """
    Non-recursive scan of input dirs. Ignores already-normalized target names to avoid reprocessing.
    """
    out: list[Path] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if not p.is_file():
                continue
            if p.suffix.lower() != ".png":
                continue
            if p.name.startswith("_"):
                continue
            if p.name.lower() in TARGETS:
                continue
            out.append(p)
    return out


# ----------------------------
# Main
# ----------------------------

def main():
    in_dirs = input_dirs()
    out_dir = output_sprites_dir()

    if not any(d.is_dir() for d in in_dirs):
        raise SystemExit(
            "Missing input folder.\n"
            f"Expected: {raw_sprites_dir()}"
        )

    candidates = iter_candidate_pngs(in_dirs)
    if not candidates:
        raise SystemExit(
            "No PNGs found to convert.\n"
            "Looked in:\n - " + "\n - ".join(str(d) for d in in_dirs)
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = out_dir / f"_backup_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    produced: set[str] = set()
    kept_from: dict[str, str] = {}

    for src in candidates:
        fname = src.name
        target = detect_target_name(fname)

        if not target:
            print(f"Skipping (unrecognized): {fname}")
            continue

        dst = out_dir / target

        if target in produced:
            print(f"Skipping duplicate for {target}: {fname} (kept {kept_from[target]})")
            continue

        # Backup existing destination if present
        if dst.exists():
            shutil.copy2(str(dst), str(backup_dir / target))

        try:
            safe_rerender_png(src, dst, OUT_SIZE)
            produced.add(target)
            kept_from[target] = fname
            print(f"OK: {fname}  ->  {target}")
        except Exception as e:
            print(f"FAILED: {fname}: {e}")

    missing = sorted(TARGETS - produced)
    if missing:
        print("\nMissing pieces:")
        for m in missing:
            print(" -", m)
    else:
        print("\nAll 12 pieces generated successfully.")

    print("\nInput dirs:")
    for d in in_dirs:
        print(" -", d)
    print(f"\nOutput dir:   {out_dir}")
    print(f"Backup dir:   {backup_dir}")


if __name__ == "__main__":
    main()
