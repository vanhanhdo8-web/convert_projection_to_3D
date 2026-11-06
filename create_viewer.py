"""
Tạo file HTML xem 3D (Three.js) từ một mô hình có sẵn: .obj / .stl / .ply / .glb hoặc file spec .json.

    python create_viewer.py model_3d.obj
    python create_viewer.py examples/ga_chac.json -o ga_chac_viewer.html -t "Gá chạc"
"""
import argparse
import json
import os
import sys

import model_builder as mb
import viewer_builder as vb


def main() -> int:
    ap = argparse.ArgumentParser(description="Tạo HTML xem 3D từ OBJ/STL/JSON")
    ap.add_argument("model", help="file .obj/.stl/.ply/.glb hoặc spec .json")
    ap.add_argument("-o", "--out", help="file HTML đầu ra (mặc định: <tên>_viewer.html)")
    ap.add_argument("-t", "--title", help="tiêu đề hiển thị")
    args = ap.parse_args()

    base, ext = os.path.splitext(args.model)
    info, title, units = None, args.title, "mm"
    try:
        if ext.lower() == ".json":
            with open(args.model, "r", encoding="utf-8") as f:
                spec = json.load(f)
            mesh, warnings = mb.build_mesh(spec)
            for w in warnings:
                print("[!]", w)
            info, units = spec.get("info"), spec.get("units", "mm")
            title = title or spec.get("title")
        else:
            mesh = mb.load_mesh_file(args.model)
            # lưới nhập vào thường là Z hướng lên (OpenSCAD/CAD) – giống quy ước của spec
    except Exception as exc:
        print("Lỗi:", exc)
        return 1

    out = args.out or f"{base}_viewer.html"
    vb.write_viewer(out, mesh=mesh, title=title or os.path.basename(base), info=info, units=units)
    print("Đã tạo:", os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
