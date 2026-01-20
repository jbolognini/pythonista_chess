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

import os
import shutil
import time
import ui


# ----------------------------
# CONFIG (edit these)
# ----------------------------

OUT_SIZE = 512  # 256 or 512 safe for Scene

RAW_SPRITES_DIR = "assets/raw_sprites"
OUTPUT_SPRITES_DIR = "assets/sprites"


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

def project_root() -> str:
    # tools/ -> project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def raw_sprites_dir() -> str:
    return os.path.join(project_root(), RAW_SPRITES_DIR)

def output_sprites_dir() -> str:
    return os.path.join(project_root(), OUTPUT_SPRITES_DIR)

def input_dirs() -> list[str]:
    """
    Primary: assets/raw_sprites/
    Also accept: assets/raw_sprites/assets/ (in case downloads were nested)
    """
    base = raw_sprites_dir()
    dirs = [base]
    nested = os.path.join(base, "assets")
    if os.path.isdir(nested):
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

def safe_rerender_png(src_path: str, dst_path: str, out_size: int):
    data = open(src_path, "rb").read()
    img = ui.Image.from_data(data)
    if img is None:
        raise RuntimeError("Image decode failed")

    # Force a known-size RGBA canvas and scale to fill the square.
    with ui.ImageContext(out_size, out_size) as ctx:
        ui.set_color((0, 0, 0, 0))
        ui.Path.rect(0, 0, out_size, out_size).fill()
        img.draw(0, 0, out_size, out_size)
        fixed = ctx.get_image()

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, "wb") as f:
        f.write(fixed.to_png())


# ----------------------------
# IO helpers
# ----------------------------

def iter_candidate_pngs(dirs: list[str]) -> list[str]:
    """
    Non-recursive scan of input dirs. Ignores already-normalized target names to avoid reprocessing.
    """
    out: list[str] = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.lower().endswith(".png"):
                continue
            if fname.startswith("_"):
                continue
            if fname.lower() in TARGETS:
                continue
            out.append(os.path.join(d, fname))
    return out


# ----------------------------
# Main
# ----------------------------

def main():
    in_dirs = input_dirs()
    out_dir = output_sprites_dir()

    if not any(os.path.isdir(d) for d in in_dirs):
        raise SystemExit(
            "Missing input folder.\n"
            f"Expected: {raw_sprites_dir()}"
        )

    candidates = iter_candidate_pngs(in_dirs)
    if not candidates:
        raise SystemExit(
            "No PNGs found to convert.\n"
            "Looked in:\n - " + "\n - ".join(in_dirs)
        )

    os.makedirs(out_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(out_dir, f"_backup_{stamp}")
    os.makedirs(backup_dir, exist_ok=True)

    produced: set[str] = set()
    kept_from: dict[str, str] = {}

    for src in candidates:
        fname = os.path.basename(src)
        target = detect_target_name(fname)

        if not target:
            print(f"Skipping (unrecognized): {fname}")
            continue

        dst = os.path.join(out_dir, target)

        if target in produced:
            print(f"Skipping duplicate for {target}: {fname} (kept {kept_from[target]})")
            continue

        # Backup existing destination if present
        if os.path.exists(dst):
            shutil.copy2(dst, os.path.join(backup_dir, target))

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

    print(f"\nInput dirs:   {', '.join(in_dirs)}")
    print(f"Output dir:   {out_dir}")
    print(f"Backup dir:   {backup_dir}")


if __name__ == "__main__":
    main()
