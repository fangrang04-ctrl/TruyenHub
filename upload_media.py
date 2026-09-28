import os
from pathlib import Path
import cloudinary
import cloudinary.uploader

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"

if not os.environ.get("CLOUDINARY_URL"):
    raise RuntimeError("Chưa có CLOUDINARY_URL")

cloudinary.config(secure=True)

files = [
    p for p in MEDIA_DIR.rglob("*")
    if p.is_file()
]

print(f"Tìm thấy {len(files)} file trong media/")

success = 0
failed = 0

for file_path in files:
    relative_path = file_path.relative_to(MEDIA_DIR)
    public_id = str(relative_path.with_suffix("")).replace("\\", "/")

    try:
        result = cloudinary.uploader.upload(
            str(file_path),
            public_id=public_id,
            resource_type="auto",
            overwrite=True,
        )

        success += 1
        print(f"[OK] {relative_path} -> {result['secure_url']}")

    except Exception as e:
        failed += 1
        print(f"[ERROR] {relative_path}: {e}")

print()
print(f"Hoàn thành: {success} thành công, {failed} lỗi")