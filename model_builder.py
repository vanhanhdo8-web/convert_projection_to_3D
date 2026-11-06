"""
model_builder.py
================
Dựng mô hình 3D (lưới tam giác, "watertight") từ bản mô tả hình học (spec) dạng JSON.

Spec là thứ mà AI (Gemini) trả về sau khi đọc bản vẽ 3 hình chiếu. Dùng spec có cấu trúc
thay vì để AI tự viết code Three.js giúp file HTML luôn đúng khuôn mẫu, có đủ lỗ/rãnh,
và cùng một mô hình có thể xuất ra HTML, STL, OBJ, OpenSCAD.

Hệ tọa độ của spec (giống OpenSCAD):  X = dài,  Y = rộng (sâu),  Z = cao (hướng lên). Đơn vị mm.

Cấu trúc spec
-------------
{
  "title": "Gá chạc lỗ tròn",
  "units": "mm",
  "info": [["Dài x Rộng x Cao", "65 x 28 x 27"], ...],          # (tuỳ chọn) hiện ở bảng thông số
  "solids": [ ... ],     # các khối được HỢP (union) lại với nhau
  "cuts":   [ ... ],     # các khối bị TRỪ (difference) khỏi kết quả -> lỗ, rãnh, bậc cắt
  "openscad": "..."      # (tuỳ chọn) mã OpenSCAD tương ứng
}

Các loại khối (dùng cho cả "solids" và "cuts"):
  {"shape":"box",      "origin":[x,y,z], "size":[dx,dy,dz]}
  {"shape":"cylinder", "axis":"x|y|z", "start":[x,y,z], "length":L, "radius":r | "diameter":d}
                       (hoặc "center":[x,y,z] = tâm của trục thay cho "start")
  {"shape":"sphere",   "center":[x,y,z], "radius":r | "diameter":d}
  {"shape":"extrude",  "plane":"XY|XZ|YZ", "polygon": <profile>, "holes":[<profile>,...],
                       "from":a, "to":b}      # đùn biên dạng 2D dọc trục còn lại, từ a đến b
      XY -> biên dạng (x,y), đùn dọc +Z      XZ -> biên dạng (x,z), đùn dọc +Y
      YZ -> biên dạng (y,z), đùn dọc +X

<profile> (biên dạng 2D) là một trong:
  [[u,v],[u,v],...]                                   đa giác theo thứ tự các đỉnh
  {"circle":{"center":[u,v],"radius":r}}
  {"rect":{"origin":[u,v],"size":[w,h]}}
  {"slot":{"center":[u,v],"length":L,"width":W,"angle":deg}}   rãnh bầu dục hai đầu tròn
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry import box as shapely_box
from shapely.geometry import LineString
from shapely.ops import unary_union

CIRCLE_RES = 32  # số đoạn thẳng trên mỗi 1/4 đường tròn (càng cao càng mịn)


class SpecError(ValueError):
    """Spec không hợp lệ hoặc không dựng được hình."""


# --------------------------------------------------------------------------------------
# Tiện ích đọc số liệu
# --------------------------------------------------------------------------------------
def _f(value: Any, name: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise SpecError(f"'{name}' phải là số, nhận được {value!r}")
    if not math.isfinite(x):
        raise SpecError(f"'{name}' không hợp lệ ({value!r})")
    return x


def _vec(value: Any, n: int, name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != n:
        raise SpecError(f"'{name}' phải là danh sách {n} số, nhận được {value!r}")
    return [_f(v, name) for v in value]


def _radius(d: dict, name: str) -> float:
    if "radius" in d:
        r = _f(d["radius"], f"{name}.radius")
    elif "diameter" in d:
        r = _f(d["diameter"], f"{name}.diameter") / 2.0
    elif "r" in d:
        r = _f(d["r"], f"{name}.r")
    elif "d" in d:
        r = _f(d["d"], f"{name}.d") / 2.0
    else:
        raise SpecError(f"{name}: thiếu 'radius' hoặc 'diameter'")
    if r <= 0:
        raise SpecError(f"{name}: bán kính phải > 0")
    return r


# --------------------------------------------------------------------------------------
# Biên dạng 2D -> shapely
# --------------------------------------------------------------------------------------
def _profile_to_shape(profile: Any, name: str = "profile"):
    """Chuyển một biên dạng 2D trong spec thành đối tượng shapely."""
    if isinstance(profile, dict):
        if "circle" in profile:
            c = profile["circle"]
            cx, cy = _vec(c.get("center"), 2, f"{name}.circle.center")
            return Point(cx, cy).buffer(_radius(c, f"{name}.circle"), resolution=CIRCLE_RES)
        if "rect" in profile:
            r = profile["rect"]
            ox, oy = _vec(r.get("origin"), 2, f"{name}.rect.origin")
            w, h = _vec(r.get("size"), 2, f"{name}.rect.size")
            return shapely_box(min(ox, ox + w), min(oy, oy + h), max(ox, ox + w), max(oy, oy + h))
        if "slot" in profile:
            s = profile["slot"]
            cx, cy = _vec(s.get("center"), 2, f"{name}.slot.center")
            length = _f(s.get("length"), f"{name}.slot.length")
            width = _f(s.get("width"), f"{name}.slot.width")
            ang = math.radians(_f(s.get("angle", 0), f"{name}.slot.angle"))
            if width <= 0 or length < width:
                raise SpecError(f"{name}.slot: cần length >= width > 0")
            half = (length - width) / 2.0
            dx, dy = math.cos(ang) * half, math.sin(ang) * half
            line = LineString([(cx - dx, cy - dy), (cx + dx, cy + dy)])
            return line.buffer(width / 2.0, resolution=CIRCLE_RES)
        raise SpecError(f"{name}: biên dạng không hỗ trợ ({list(profile.keys())})")

    if isinstance(profile, (list, tuple)):
        pts = [tuple(_vec(p, 2, f"{name}[{i}]")) for i, p in enumerate(profile)]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            raise SpecError(f"{name}: đa giác cần ít nhất 3 đỉnh")
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)  # sửa đa giác tự cắt nhẹ
        if poly.is_empty or poly.area < 1e-9:
            raise SpecError(f"{name}: đa giác suy biến (diện tích = 0)")
        return poly

    raise SpecError(f"{name}: biên dạng phải là danh sách điểm hoặc circle/rect/slot")


# --------------------------------------------------------------------------------------
# Đặt khối 2D đã đùn vào đúng mặt phẳng / vị trí
# --------------------------------------------------------------------------------------
_PLANE_AXES = {
    # (u,v,w) cục bộ -> (x,y,z)
    "XY": np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float),
    "XZ": np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=float),  # x=u, y=w, z=v
    "YZ": np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float),  # x=w, y=u, z=v
}
_AXIS_PLANE = {"z": "XY", "y": "XZ", "x": "YZ"}


def _place(mesh: trimesh.Trimesh, plane: str, offset: float) -> trimesh.Trimesh:
    m = _PLANE_AXES[plane]
    verts = mesh.vertices @ m.T
    faces = mesh.faces.copy()
    if np.linalg.det(m) < 0:          # phép phản xạ -> đảo chiều mặt tam giác
        faces = faces[:, ::-1]
    off = np.zeros(3)
    off[{"XY": 2, "XZ": 1, "YZ": 0}[plane]] = offset
    return trimesh.Trimesh(verts + off, faces, process=True)


def _extrude(shape, plane: str, a: float, b: float) -> list[trimesh.Trimesh]:
    lo, hi = min(a, b), max(a, b)
    if hi - lo <= 1e-9:
        raise SpecError("khoảng đùn (from..to) bằng 0")
    polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    out = []
    for p in polys:
        if p.is_empty or p.area < 1e-9:
            continue
        m = trimesh.creation.extrude_polygon(p, hi - lo)
        out.append(_place(m, plane, lo))
    if not out:
        raise SpecError("biên dạng rỗng sau khi trừ lỗ")
    return out


# --------------------------------------------------------------------------------------
# Từng loại khối
# --------------------------------------------------------------------------------------
def _make_box(d: dict) -> list[trimesh.Trimesh]:
    if "origin" in d and "size" in d:
        ox, oy, oz = _vec(d["origin"], 3, "box.origin")
        sx, sy, sz = _vec(d["size"], 3, "box.size")
    elif "min" in d and "max" in d:
        ox, oy, oz = _vec(d["min"], 3, "box.min")
        mx, my, mz = _vec(d["max"], 3, "box.max")
        sx, sy, sz = mx - ox, my - oy, mz - oz
    else:
        raise SpecError("box cần 'origin' + 'size'")
    # cho phép size âm
    x0, x1 = sorted((ox, ox + sx))
    y0, y1 = sorted((oy, oy + sy))
    z0, z1 = sorted((oz, oz + sz))
    if min(x1 - x0, y1 - y0, z1 - z0) <= 1e-9:
        raise SpecError("box có kích thước bằng 0")
    m = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return [m]


def _make_cylinder(d: dict) -> list[trimesh.Trimesh]:
    axis = str(d.get("axis", "z")).lower()
    if axis not in _AXIS_PLANE:
        raise SpecError(f"cylinder.axis phải là x, y hoặc z (nhận {axis!r})")
    r = _radius(d, "cylinder")
    length = _f(d.get("length", d.get("height")), "cylinder.length")
    if length <= 0:
        raise SpecError("cylinder.length phải > 0")
    idx = {"x": 0, "y": 1, "z": 2}[axis]
    if "start" in d:
        p = _vec(d["start"], 3, "cylinder.start")
    elif "center" in d:
        p = _vec(d["center"], 3, "cylinder.center")
        p[idx] -= length / 2.0
    else:
        raise SpecError("cylinder cần 'start' (hoặc 'center')")
    # toạ độ vuông góc với trục -> (u,v) của mặt phẳng tương ứng
    plane = _AXIS_PLANE[axis]
    uv = {"XY": (p[0], p[1]), "XZ": (p[0], p[2]), "YZ": (p[1], p[2])}[plane]
    circle = Point(*uv).buffer(r, resolution=CIRCLE_RES)
    return _extrude(circle, plane, p[idx], p[idx] + length)


def _make_sphere(d: dict) -> list[trimesh.Trimesh]:
    c = _vec(d.get("center"), 3, "sphere.center")
    r = _radius(d, "sphere")
    m = trimesh.creation.icosphere(subdivisions=4, radius=r)
    m.apply_translation(c)
    return [m]


def _make_extrude(d: dict) -> list[trimesh.Trimesh]:
    plane = str(d.get("plane", "XY")).upper()
    if plane not in _PLANE_AXES:
        raise SpecError(f"extrude.plane phải là XY, XZ hoặc YZ (nhận {plane!r})")
    if "polygon" not in d:
        raise SpecError("extrude cần 'polygon'")
    shape = _profile_to_shape(d["polygon"], "extrude.polygon")
    holes = d.get("holes") or []
    if holes:
        hole_shapes = [_profile_to_shape(h, f"extrude.holes[{i}]") for i, h in enumerate(holes)]
        shape = shape.difference(unary_union(hole_shapes))
    a = _f(d.get("from", 0), "extrude.from")
    if "to" in d:
        b = _f(d["to"], "extrude.to")
    elif "height" in d:
        b = a + _f(d["height"], "extrude.height")
    else:
        raise SpecError("extrude cần 'to' hoặc 'height'")
    return _extrude(shape, plane, a, b)


_BUILDERS = {
    "box": _make_box,
    "cube": _make_box,
    "cylinder": _make_cylinder,
    "sphere": _make_sphere,
    "extrude": _make_extrude,
}


def _make_shape(d: Any) -> list[trimesh.Trimesh]:
    if not isinstance(d, dict):
        raise SpecError("mỗi khối phải là một object JSON")
    kind = str(d.get("shape", d.get("type", ""))).lower()
    if kind not in _BUILDERS:
        raise SpecError(f"loại khối không hỗ trợ: {kind!r}")
    return _BUILDERS[kind](d)


# --------------------------------------------------------------------------------------
# Boolean
# --------------------------------------------------------------------------------------
def _union(meshes: list[trimesh.Trimesh], warnings: list[str]) -> trimesh.Trimesh:
    if len(meshes) == 1:
        return meshes[0]
    try:
        return trimesh.boolean.union(meshes, engine="manifold")
    except Exception as exc:  # manifold3d thiếu hoặc lưới lỗi
        warnings.append(f"Không hợp nhất được các khối ({exc}); ghép trực tiếp.")
        return trimesh.util.concatenate(meshes)


def _difference(body: trimesh.Trimesh, cutter: trimesh.Trimesh, warnings: list[str]) -> trimesh.Trimesh:
    try:
        res = trimesh.boolean.difference([body, cutter], engine="manifold")
        if res is None or len(res.faces) == 0:
            raise SpecError("kết quả rỗng")
        return res
    except Exception as exc:
        warnings.append(f"Không cắt được lỗ/rãnh ({exc}). Hãy cài: pip install manifold3d")
        return body


# --------------------------------------------------------------------------------------
# API chính
# --------------------------------------------------------------------------------------
def validate_spec(spec: Any) -> dict:
    if not isinstance(spec, dict):
        raise SpecError("spec phải là một object JSON")
    solids = spec.get("solids")
    if not isinstance(solids, list) or not solids:
        raise SpecError("spec cần danh sách 'solids' không rỗng")
    cuts = spec.get("cuts", [])
    if cuts is None:
        cuts = []
    if not isinstance(cuts, list):
        raise SpecError("'cuts' phải là danh sách")
    return spec


def build_mesh(spec: dict) -> tuple[trimesh.Trimesh, list[str]]:
    """Dựng lưới tam giác từ spec. Trả về (mesh, danh sách cảnh báo)."""
    spec = validate_spec(spec)
    warnings: list[str] = []

    solids: list[trimesh.Trimesh] = []
    for i, s in enumerate(spec["solids"]):
        try:
            solids.extend(_make_shape(s))
        except SpecError as exc:
            raise SpecError(f"solids[{i}]: {exc}")
    body = _union(solids, warnings)

    cutters: list[trimesh.Trimesh] = []
    for i, c in enumerate(spec.get("cuts") or []):
        try:
            cutters.extend(_make_shape(c))
        except SpecError as exc:
            warnings.append(f"Bỏ qua cuts[{i}]: {exc}")
    if cutters:
        body = _difference(body, _union(cutters, warnings), warnings)

    body = trimesh.Trimesh(body.vertices, body.faces, process=True)
    body.merge_vertices()
    body.update_faces(body.nondegenerate_faces())
    body.remove_unreferenced_vertices()
    if len(body.faces) == 0:
        raise SpecError("mô hình rỗng")
    trimesh.repair.fix_normals(body)
    if body.volume < 0:
        body.invert()
    return body, warnings


def load_mesh_file(path: str) -> trimesh.Trimesh:
    """Đọc OBJ/STL/PLY/GLB... thành một Trimesh duy nhất."""
    obj = trimesh.load(path, force="mesh")
    if isinstance(obj, trimesh.Scene):
        obj = trimesh.util.concatenate(list(obj.geometry.values()))
    if not isinstance(obj, trimesh.Trimesh) or len(obj.faces) == 0:
        raise SpecError(f"Không đọc được lưới 3D từ {path}")
    return obj


# --------------------------------------------------------------------------------------
# Pháp tuyến "mượt có góc gập" – mịn ở mặt cong, sắc ở cạnh vuông (giống CAD)
# --------------------------------------------------------------------------------------
def shaded_arrays(mesh: trimesh.Trimesh, crease_deg: float = 35.0):
    """
    Trả về (positions[N,3], normals[N,3], indices[M]) đã khử trùng lặp.
    Pháp tuyến đỉnh được trung bình theo diện tích chỉ với các mặt lân cận lệch
    nhau < crease_deg, nên mặt trụ/lỗ tròn mịn còn cạnh vuông vẫn sắc nét.
    """
    v = np.asarray(mesh.vertices, dtype=np.float64)
    f = np.asarray(mesh.faces, dtype=np.int64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(n, axis=1)
    keep = area > 1e-12
    f, tri, n, area = f[keep], tri[keep], n[keep], area[keep]
    n = n / area[:, None]

    nf = len(f)
    nv = len(v)
    corner_vid = f.reshape(-1)
    face_of_corner = np.repeat(np.arange(nf), 3)
    order = np.argsort(corner_vid, kind="stable")
    sorted_vid = corner_vid[order]
    starts = np.searchsorted(sorted_vid, np.arange(nv), side="left")
    ends = np.searchsorted(sorted_vid, np.arange(nv), side="right")

    cos_t = math.cos(math.radians(crease_deg))
    normals = np.zeros((nf * 3, 3))
    for vid in range(nv):
        a, b = starts[vid], ends[vid]
        if a == b:
            continue
        corners = order[a:b]
        fidx = face_of_corner[corners]
        fn = n[fidx]
        w = area[fidx]
        mask = (fn @ fn.T) >= cos_t
        acc = (mask * w[None, :]) @ fn
        ln = np.linalg.norm(acc, axis=1, keepdims=True)
        ln[ln < 1e-12] = 1.0
        normals[corners] = acc / ln

    pos = tri.reshape(-1, 3)
    key = np.round(np.hstack([pos, normals]), 5)
    uniq, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return pos[first], normals[first], inverse.astype(np.uint32).reshape(-1)


# --------------------------------------------------------------------------------------
# Spec -> OpenSCAD (dùng khi AI không kèm mã OpenSCAD, hoặc để đảm bảo khớp 100% với 3D)
# --------------------------------------------------------------------------------------
def _n(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _scad_profile(profile: Any) -> str:
    if isinstance(profile, dict):
        if "circle" in profile:
            c = profile["circle"]
            cx, cy = _vec(c["center"], 2, "center")
            return f"translate([{_n(cx)}, {_n(cy)}]) circle(r={_n(_radius(c, 'circle'))}, $fn=96);"
        if "rect" in profile:
            r = profile["rect"]
            ox, oy = _vec(r["origin"], 2, "origin")
            w, h = _vec(r["size"], 2, "size")
            return f"translate([{_n(ox)}, {_n(oy)}]) square([{_n(w)}, {_n(h)}]);"
        if "slot" in profile:
            s = profile["slot"]
            cx, cy = _vec(s["center"], 2, "center")
            L, W = _f(s["length"], "length"), _f(s["width"], "width")
            ang = _f(s.get("angle", 0), "angle")
            half = (L - W) / 2.0
            return (
                f"translate([{_n(cx)}, {_n(cy)}]) rotate({_n(ang)}) hull() {{ "
                f"translate([{_n(-half)}, 0]) circle(d={_n(W)}, $fn=64); "
                f"translate([{_n(half)}, 0]) circle(d={_n(W)}, $fn=64); }}"
            )
    pts = ", ".join(f"[{_n(u)}, {_n(v)}]" for u, v in (_vec(p, 2, "pt") for p in profile))
    return f"polygon(points=[{pts}]);"


def _scad_shape(d: dict) -> str:
    kind = str(d.get("shape", d.get("type", ""))).lower()
    if kind in ("box", "cube"):
        if "origin" in d:
            ox, oy, oz = _vec(d["origin"], 3, "origin")
            sx, sy, sz = _vec(d["size"], 3, "size")
        else:
            ox, oy, oz = _vec(d["min"], 3, "min")
            mx, my, mz = _vec(d["max"], 3, "max")
            sx, sy, sz = mx - ox, my - oy, mz - oz
        return f"translate([{_n(ox)}, {_n(oy)}, {_n(oz)}]) cube([{_n(sx)}, {_n(sy)}, {_n(sz)}]);"
    if kind == "sphere":
        cx, cy, cz = _vec(d["center"], 3, "center")
        return f"translate([{_n(cx)}, {_n(cy)}, {_n(cz)}]) sphere(r={_n(_radius(d, 'sphere'))}, $fn=64);"
    if kind == "cylinder":
        axis = str(d.get("axis", "z")).lower()
        r = _radius(d, "cylinder")
        length = _f(d.get("length", d.get("height")), "length")
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        p = _vec(d["start"], 3, "start") if "start" in d else _vec(d["center"], 3, "center")
        if "start" not in d:
            p[idx] -= length / 2.0
        rot = {"z": "", "x": "rotate([0, 90, 0]) ", "y": "rotate([-90, 0, 0]) "}[axis]
        return (
            f"translate([{_n(p[0])}, {_n(p[1])}, {_n(p[2])}]) {rot}"
            f"cylinder(r={_n(r)}, h={_n(length)}, $fn=96);"
        )
    if kind == "extrude":
        plane = str(d.get("plane", "XY")).upper()
        a = _f(d.get("from", 0), "from")
        b = _f(d["to"], "to") if "to" in d else a + _f(d["height"], "height")
        lo, hi = min(a, b), max(a, b)
        inner = f"difference() {{ {_scad_profile(d['polygon'])} "
        for h in d.get("holes") or []:
            inner += _scad_profile(h) + " "
        inner += "}"
        ext = f"linear_extrude(height={_n(hi - lo)}) {inner}"
        if plane == "XY":
            return f"translate([0, 0, {_n(lo)}]) {ext}"
        if plane == "XZ":   # x=u, z=v, y=w
            return f"translate([0, {_n(hi)}, 0]) rotate([90, 0, 0]) {ext}"
        return (            # YZ: x=w, y=u, z=v
            f"multmatrix([[0,0,1,{_n(lo)}],[1,0,0,0],[0,1,0,0],[0,0,0,1]]) {ext}"
        )
    raise SpecError(f"loại khối không hỗ trợ: {kind!r}")


def spec_to_scad(spec: dict) -> str:
    """Sinh mã OpenSCAD tương đương với spec."""
    spec = validate_spec(spec)
    lines = [
        "// ================================================",
        f"// {spec.get('title', 'MÔ HÌNH CAD 3D TỪ BẢN VẼ KỸ THUẬT')}",
        f"// Đơn vị: {spec.get('units', 'mm')}  (X = dài, Y = rộng, Z = cao)",
        "// Tạo tự động từ dữ liệu hình học của AI",
        "// ================================================",
        "",
        "module object_3d() {",
        "    difference() {",
        "        union() {",
    ]
    for s in spec["solids"]:
        lines.append(f"            {_scad_shape(s)}")
    lines.append("        }")
    for c in spec.get("cuts") or []:
        lines.append(f"        {_scad_shape(c)}")
    lines += ["    }", "}", "", "object_3d();", ""]
    return "\n".join(lines)


def bounds_summary(mesh: trimesh.Trimesh) -> tuple[float, float, float]:
    ext = mesh.bounds[1] - mesh.bounds[0]
    return float(ext[0]), float(ext[1]), float(ext[2])
