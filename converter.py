"""
converter.py
============
Quy trình hoàn chỉnh dùng chung cho giao diện (gui.py) và dòng lệnh:

    ảnh bản vẽ ──► Gemini ──► spec JSON ──► mesh 3D ──► HTML Three.js + OpenSCAD + STL + OBJ
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

import gemini_client as gc
import model_builder as mb
import viewer_builder as vb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "output")


@dataclass
class ConversionResult:
    name: str
    html: str
    scad: str
    stl: str
    obj: str
    json: str
    model: str
    warnings: list[str] = field(default_factory=list)
    title: str = ""


def safe_name(name: str, default: str = "my_model") -> str:
    name = re.sub(r"[^\w\-.]+", "_", (name or "").strip()).strip("._")
    return name or default


def save_outputs(
    spec: dict,
    mesh,
    out_dir: str,
    name: str,
    scad: Optional[str] = None,
    model: str = "",
    warnings: Optional[list[str]] = None,
) -> ConversionResult:
    """Ghi HTML / SCAD / STL / OBJ / JSON cho một mô hình đã dựng."""
    name = safe_name(name)
    os.makedirs(out_dir, exist_ok=True)
    p = lambda ext: os.path.join(out_dir, f"{name}{ext}")

    title = str(spec.get("title") or name)
    vb.write_viewer(p("_viewer.html"), mesh=mesh, title=title, info=spec.get("info"), units=spec.get("units", "mm"))

    # .scad chính được sinh thẳng từ spec nên luôn KHỚP 100% với mô hình 3D / HTML / STL.
    # Bản OpenSCAD có tham số do AI viết (nếu có) được lưu kèm ở <tên>_ai.scad.
    try:
        exact_scad = mb.spec_to_scad(spec)
    except Exception as exc:  # spec lạ -> vẫn xuất các file còn lại
        exact_scad = f"// Không sinh được mã OpenSCAD: {exc}\n"
    with open(p(".scad"), "w", encoding="utf-8") as f:
        f.write(exact_scad)
    if scad:
        with open(p("_ai.scad"), "w", encoding="utf-8") as f:
            f.write(scad)

    mesh.export(p(".stl"))
    mesh.export(p(".obj"))
    with open(p(".json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    return ConversionResult(
        name=name,
        html=p("_viewer.html"),
        scad=p(".scad"),
        stl=p(".stl"),
        obj=p(".obj"),
        json=p(".json"),
        model=model,
        warnings=list(warnings or []),
        title=title,
    )


def convert_image(
    image: "str | Image.Image",
    api_key: str,
    out_dir: str = DEFAULT_OUTPUT_DIR,
    name: str = "my_model",
    progress=print,
) -> ConversionResult:
    """Chuyển một ảnh bản vẽ (đường dẫn hoặc PIL.Image) thành bộ file 3D."""
    progress("Đang tối ưu ảnh bản vẽ...")
    im = gc.load_image(image) if isinstance(image, str) else image
    b64, mime = gc.prepare_image(im)

    def build(spec: dict):
        return mb.build_mesh(spec)          # (mesh, warnings); ném SpecError nếu spec hỏng

    result = gc.generate_spec(b64, mime, api_key, progress=progress, post_process=build)
    mesh, warnings = result.post

    progress("Đang dựng mô hình 3D và xuất file...")
    return save_outputs(result.spec, mesh, out_dir, name, scad=result.scad, model=result.model, warnings=warnings)
