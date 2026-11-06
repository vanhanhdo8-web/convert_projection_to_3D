"""
Dòng lệnh: chuyển ảnh bản vẽ kỹ thuật -> mô hình 3D (HTML Three.js, OpenSCAD, STL, OBJ).

    python gemini_drawing_to_cad.py                       # hỏi từng bước
    python gemini_drawing_to_cad.py anh.jpg -n ten_file   # truyền tham số
API key lấy từ --key, biến môi trường GEMINI_API_KEY hoặc config.json.
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # console tiếng Việt trên Windows
except Exception:
    pass

from converter import DEFAULT_OUTPUT_DIR, BASE_DIR, convert_image
from gemini_client import GeminiError


def read_saved_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            return str(json.load(f).get("api_key", "")).strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Chuyển ảnh bản vẽ hình chiếu sang mô hình 3D bằng Gemini")
    ap.add_argument("image", nargs="?", help="đường dẫn ảnh bản vẽ")
    ap.add_argument("-n", "--name", help="tên file xuất (mặc định: theo tên ảnh)")
    ap.add_argument("-o", "--out", default=DEFAULT_OUTPUT_DIR, help="thư mục xuất")
    ap.add_argument("--key", help="Gemini API key")
    args = ap.parse_args()

    print("=== TOOL CHUYỂN BẢN VẼ SANG 3D & HTML TỰ ĐỘNG BẰNG GEMINI API FREE ===")
    api_key = (args.key or read_saved_key()).strip()
    if not api_key:
        api_key = input("Nhập Gemini API Key miễn phí: ").strip()
    if not api_key:
        print("Cần API Key để chạy!")
        return 1

    img = args.image or input("Đường dẫn file ảnh bản vẽ: ").strip().strip('"')
    if not os.path.isfile(img):
        print(f"Lỗi: không tìm thấy file ảnh '{img}'")
        return 1

    name = args.name or os.path.splitext(os.path.basename(img))[0]
    try:
        res = convert_image(img, api_key, out_dir=args.out, name=name, progress=lambda m: print(" •", m))
    except GeminiError as e:
        print("Lỗi:", e)
        return 2
    except Exception as e:
        print("Lỗi:", e)
        return 3

    print(f"\n[OK] Model dùng: {res.model}")
    for label, path in (("HTML 3D Viewer", res.html), ("OpenSCAD", res.scad), ("STL", res.stl), ("OBJ", res.obj)):
        print(f"[OK] {label}: {path}")
    for w in res.warnings:
        print("[!]", w)
    print(f"👉 Bấm đúp '{res.html}' để xem và xoay 3D trên trình duyệt!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
