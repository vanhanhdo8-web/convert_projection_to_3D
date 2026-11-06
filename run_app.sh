#!/usr/bin/env bash
# Khởi chạy nhanh trên Linux / macOS
cd "$(dirname "$0")"
python3 -c "import PySide6, PIL, numpy, trimesh, shapely, mapbox_earcut, manifold3d" 2>/dev/null || {
  echo "Đang cài đặt thư viện cần thiết..."
  python3 -m pip install -r requirements.txt || exit 1
}
exec python3 gui.py
