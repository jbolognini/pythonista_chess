import os
import shutil
import time
import ui

ASSETS_DIR = 'assets'
OUT_SIZE = 512  # 256 or 512 both safe for scene

PIECE_MAP = {
    'p': 'p',
    'n': 'n',
    'b': 'b',
    'r': 'r',
    'q': 'q',
    'k': 'k',
}

TARGETS = {
    'wp.png','wn.png','wb.png','wr.png','wq.png','wk.png',
    'bp.png','bn.png','bb.png','br.png','bq.png','bk.png',
}

def detect_target_name(filename: str) -> str | None:
    name = filename.lower()

    # Detect color
    if 'lt45' in name:      # white (light)
        color = 'w'
    elif 'dt45' in name:    # black (dark)
        color = 'b'
    else:
        return None

    # Detect piece letter
    for k in PIECE_MAP:
        if f'_{k}' in name or f'{k}lt45' in name or f'{k}dt45' in name:
            return f'{color}{k}.png'

    return None

def safe_rerender_png(src_path: str, dst_path: str, out_size: int):
    data = open(src_path, 'rb').read()
    img = ui.Image.from_data(data)
    if img is None:
        raise RuntimeError("Image decode failed")

    with ui.ImageContext(out_size, out_size) as ctx:
        ui.set_color((0, 0, 0, 0))
        ui.Path.rect(0, 0, out_size, out_size).fill()
        img.draw(0, 0, out_size, out_size)
        fixed = ctx.get_image()

    with open(dst_path, 'wb') as f:
        f.write(fixed.to_png())

def main():
    if not os.path.isdir(ASSETS_DIR):
        raise SystemExit("Missing assets/ folder")

    stamp = time.strftime('%Y%m%d-%H%M%S')
    backup_dir = os.path.join(ASSETS_DIR, f'_orig_{stamp}')
    os.makedirs(backup_dir, exist_ok=True)

    produced = set()

    for fname in sorted(os.listdir(ASSETS_DIR)):
        if not fname.lower().endswith('.png'):
            continue
        if fname.startswith('_orig_'):
            continue

        target = detect_target_name(fname)
        if not target:
            print(f"Skipping (unrecognized): {fname}")
            continue

        src = os.path.join(ASSETS_DIR, fname)
        dst = os.path.join(ASSETS_DIR, target)

        shutil.copy2(src, os.path.join(backup_dir, fname))

        if target in produced:
            print(f"Skipping duplicate for {target}: {fname}")
            continue

        try:
            safe_rerender_png(src, dst, OUT_SIZE)
            produced.add(target)
            print(f"OK: {fname} → {target}")
        except Exception as e:
            print(f"FAILED: {fname}: {e}")

    missing = sorted(TARGETS - produced)
    if missing:
        print("\nMissing pieces:")
        for m in missing:
            print(" -", m)
    else:
        print("\nAll 12 pieces generated successfully.")

    print(f"\nBackups in: {backup_dir}")

if __name__ == '__main__':
    main()
