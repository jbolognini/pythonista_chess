from pathlib import Path
from PIL import Image, ImageFilter

SCRIPT_DIR = Path(__file__).resolve().parent
IN_DIR = (SCRIPT_DIR / "../assets/sprites").resolve()
OUT_DIR = IN_DIR
if not IN_DIR.exists():
    raise RuntimeError(f"Sprites directory not found: {SPRITES_DIR}")

HALO_SUFFIX = "_halo"
DILATE_PX = 6        # try 4–8 for 512px sprites
BLUR_PX = 1.2        # try 0.8–1.5

WHITE_PIECES = ["wp", "wn", "wb", "wr", "wq", "wk"]

def dilate_alpha(alpha: Image.Image, px: int) -> Image.Image:
    # Simple dilation by repeated max-filter passes.
    # Each pass expands by ~1 px (more or less depending on kernel).
    a = alpha
    for _ in range(px):
        a = a.filter(ImageFilter.MaxFilter(3))
    return a

def make_halo(src_path: Path, out_path: Path):
    im = Image.open(src_path).convert("RGBA")
    r, g, b, a = im.split()

    # solid white silhouette using alpha only
    halo_alpha = dilate_alpha(a, DILATE_PX)

    # optional soften so it reads as glow instead of jagged edge
    if BLUR_PX > 0:
        halo_alpha = halo_alpha.filter(ImageFilter.GaussianBlur(BLUR_PX))

    # build halo image: white RGB + halo alpha
    halo = Image.new("RGBA", im.size, (255, 255, 255, 0))
    hr, hg, hb, _ = halo.split()
    halo = Image.merge("RGBA", (hr, hg, hb, halo_alpha))

    halo.save(out_path)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for base in WHITE_PIECES:
        src = IN_DIR / f"{base}.png"
        out = OUT_DIR / f"{base}{HALO_SUFFIX}.png"
        print("making", out)
        make_halo(src, out)

if __name__ == "__main__":
    main()
