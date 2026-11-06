"""
viewer_builder.py
=================
Tạo file HTML Three.js "chuẩn" để xem mô hình 3D: nền tối, lưới nền, vật liệu xanh kim loại
bóng, viền trắng kiểu CAD, đổ bóng mềm, bảng thông số và các nút điều khiển.

Cùng một file HTML này vừa được mở trên trình duyệt, vừa được nhúng trực tiếp trong khung
"Xem 3D trực tiếp" của gui.py, nên màu sắc / độ bóng / độ mượt luôn giống nhau.
"""
from __future__ import annotations

import base64
import html
import json
import math
import os
from typing import Iterable

import numpy as np

from model_builder import shaded_arrays

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "vendor")

CDN_THREE = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
CDN_ORBIT = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"


def _read_vendor(name: str) -> str | None:
    path = os.path.join(VENDOR_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().replace("</script", "<\\/script")
    return None


def _libs_block() -> str:
    """Nhúng sẵn Three.js (chạy offline). Nếu thiếu thư mục vendor thì dùng CDN."""
    three = _read_vendor("three.min.js")
    orbit = _read_vendor("OrbitControls.js")
    if three and orbit:
        return f"<script>\n{three}\n</script>\n<script>\n{orbit}\n</script>"
    return f'<script src="{CDN_THREE}"></script>\n<script src="{CDN_ORBIT}"></script>'


def _b64(arr: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def _info_items(info: Iterable | None) -> str:
    rows = []
    for item in info or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append(f"<li><b>{html.escape(str(item[0]))}:</b> {html.escape(str(item[1]))}</li>")
        elif isinstance(item, dict) and "label" in item:
            rows.append(
                f"<li><b>{html.escape(str(item['label']))}:</b> {html.escape(str(item.get('value', '')))}</li>"
            )
        else:
            rows.append(f"<li>{html.escape(str(item))}</li>")
    return "\n".join(rows)


def _fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def mesh_payload(mesh) -> dict:
    """Chuyển trimesh (Z hướng lên) sang dữ liệu cho Three.js (Y hướng lên), đặt đáy lên mặt lưới."""
    pos, nor, idx = shaded_arrays(mesh)
    # (x, y, z)_CAD -> (x, z, -y)_three  (phép quay, không đổi chiều mặt)
    pos3 = np.stack([pos[:, 0], pos[:, 2], -pos[:, 1]], axis=1)
    nor3 = np.stack([nor[:, 0], nor[:, 2], -nor[:, 1]], axis=1)
    lo, hi = pos3.min(axis=0), pos3.max(axis=0)
    shift = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -(lo[2] + hi[2]) / 2.0])
    pos3 = pos3 + shift
    size = (hi - lo)
    return {
        "p": _b64(pos3.astype("<f4")),
        "n": _b64(nor3.astype("<f4")),
        "i": _b64(idx.astype("<u4")),
        "size": [float(size[0]), float(size[1]), float(size[2])],  # x, y(up), z
    }


def build_viewer_html(
    mesh=None,
    title: str = "Mô Hình 3D Từ Bản Vẽ Kỹ Thuật",
    info: Iterable | None = None,
    units: str = "mm",
    empty_message: str = "Chưa có mô hình. Hãy chọn ảnh bản vẽ và bấm “Bắt đầu chuyển đổi”.",
) -> str:
    """Trả về chuỗi HTML hoàn chỉnh (tự chứa, chạy offline)."""
    if mesh is not None:
        payload = mesh_payload(mesh)
        sx, sy, sz = payload["size"]
        # kích thước theo hệ CAD: dài (x), rộng (z three), cao (y three)
        dims = f"{_fmt(sx)} x {_fmt(sz)} x {_fmt(sy)} {units}"
        info = list(info or [])
        has_overall = any(
            isinstance(it, (list, tuple)) and len(it) >= 2
            and "dài" in str(it[0]).lower() and "cao" in str(it[0]).lower()
            for it in info
        )
        rows = _info_items(info)
        if not has_overall:
            rows = f"<li><b>Kích thước bao (Dài x Rộng x Cao):</b> {html.escape(dims)}</li>\n" + rows
        data = json.dumps(payload)
    else:
        payload = None
        rows = f"<li>{html.escape(empty_message)}</li>"
        data = "null"

    page = _TEMPLATE
    page = page.replace("__TITLE__", html.escape(title))
    page = page.replace("__ROWS__", rows)
    page = page.replace("__LIBS__", _libs_block())
    page = page.replace("__DATA__", data)
    return page


def write_viewer(path: str, **kwargs) -> str:
    content = build_viewer_html(**kwargs)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ======================================================================================
# Khuôn mẫu HTML  (màu sắc / vật liệu / ánh sáng lấy theo bản chuẩn 1511176551_2_viewer.html)
# ======================================================================================
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__</title>
    <style>
        * { box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background-color: #1a1a24;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #ffffff;
        }
        canvas { display: block; outline: none; }
        #info-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(20, 20, 30, 0.85);
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            border: 1px solid rgba(255,255,255,0.1);
            pointer-events: none;
            max-width: 340px;
        }
        h2 { margin: 0 0 10px 0; font-size: 18px; color: #4facfe; }
        ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; color: #cccccc; }
        #controls-hint {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.6);
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 12px;
            color: #aaa;
            pointer-events: none;
            white-space: nowrap;
        }
        #toolbar {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        #toolbar button {
            font: 12px 'Segoe UI', Tahoma, sans-serif;
            color: #dfe6ee;
            background: rgba(20, 20, 30, 0.85);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 8px;
            padding: 8px 12px;
            cursor: pointer;
            text-align: left;
            transition: background .15s, border-color .15s;
        }
        #toolbar button:hover { background: rgba(79,172,254,0.25); border-color: #4facfe; }
        #toolbar button.off { opacity: .55; }
        #error {
            display: none;
            position: absolute; inset: 0;
            align-items: center; justify-content: center;
            text-align: center; padding: 30px; color: #ff9b9b; font-size: 15px;
        }
        @media (max-width: 640px) {
            #controls-hint { display: none; }
            #info-panel { max-width: 70vw; }
        }
    </style>
    <!-- Three.js r128 + OrbitControls (nhúng sẵn, chạy được cả khi không có mạng) -->
    __LIBS__
</head>
<body>

    <div id="info-panel">
        <h2>__TITLE__</h2>
        <ul>
__ROWS__
        </ul>
    </div>

    <div id="toolbar">
        <button id="btn-reset" title="Quay về góc nhìn ban đầu">⟲ Đặt lại góc nhìn</button>
        <button id="btn-edges" title="Bật/tắt viền cạnh">▭ Viền cạnh</button>
        <button id="btn-grid" title="Bật/tắt lưới nền">▦ Lưới nền</button>
        <button id="btn-spin" class="off" title="Tự động xoay">⟳ Tự xoay</button>
    </div>

    <div id="controls-hint">
        Click chuột trái + kéo để XOAY | Chuột phải để DI CHUYỂN | Lăn chuột để PHÓNG TO/THU NHỎ
    </div>
    <div id="error"></div>

    <script>
    (function () {
        const DATA = __DATA__;

        function fail(msg) {
            const e = document.getElementById('error');
            e.style.display = 'flex'; e.textContent = msg;
        }
        if (typeof THREE === 'undefined') { fail('Không tải được thư viện Three.js.'); return; }

        function b64ToBuffer(b64) {
            const bin = atob(b64), u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            return u8.buffer;
        }

        // ---- kích thước mô hình (trục Y hướng lên, đáy nằm trên mặt lưới y = 0) ----
        const size = DATA ? DATA.size : [60, 30, 40];
        const S = Math.max(size[0], size[1], size[2], 1);          // cạnh lớn nhất
        const R = 0.5 * Math.sqrt(size[0]*size[0] + size[1]*size[1] + size[2]*size[2]);
        const target = new THREE.Vector3(0, size[1] / 2, 0);

        // 1. Scene, Camera, Renderer
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a24);

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, S / 200, S * 80);
        const camDir = new THREE.Vector3(0.62, 0.46, 0.70).normalize();
        const camDist = Math.max(R, S * 0.6) * 3.0;
        function resetCamera() {
            camera.position.copy(target).addScaledVector(camDir, camDist);
            controls.target.copy(target);
            controls.update();
        }

        let renderer;
        try {
            renderer = new THREE.WebGLRenderer({ antialias: true });
        } catch (err) {
            fail('Trình duyệt không bật được WebGL, không thể hiển thị 3D.');
            return;
        }
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        document.body.appendChild(renderer.domElement);

        // 2. OrbitControls
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.minDistance = S * 0.25;
        controls.maxDistance = S * 25;
        controls.autoRotateSpeed = 2.0;

        // 3. Ánh sáng
        scene.add(new THREE.AmbientLight(0xffffff, 0.6));

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(S * 0.8, S * 1.3, S * 0.95);
        dirLight1.target.position.copy(target);
        dirLight1.castShadow = true;
        dirLight1.shadow.mapSize.width = 2048;
        dirLight1.shadow.mapSize.height = 2048;
        dirLight1.shadow.camera.left = -S * 1.6;
        dirLight1.shadow.camera.right = S * 1.6;
        dirLight1.shadow.camera.top = S * 1.6;
        dirLight1.shadow.camera.bottom = -S * 1.6;
        dirLight1.shadow.camera.near = S * 0.1;
        dirLight1.shadow.camera.far = S * 6;
        dirLight1.shadow.bias = -0.0004;
        dirLight1.shadow.normalBias = S * 0.002;
        scene.add(dirLight1);
        scene.add(dirLight1.target);

        const dirLight2 = new THREE.DirectionalLight(0x4facfe, 0.3);
        dirLight2.position.set(-S * 0.8, -S * 0.5, -S * 0.8);
        scene.add(dirLight2);

        // 4. Lưới nền + mặt hứng bóng
        const niceSteps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000];
        let step = niceSteps.find(s => s >= S / 14) || 1000;
        const gridSize = Math.max(step * 4, Math.ceil((S * 3.2) / (step * 2)) * (step * 2));
        const grid = new THREE.GridHelper(gridSize, gridSize / step, 0x4facfe, 0x333344);
        grid.position.y = -S * 0.002;
        scene.add(grid);

        const ground = new THREE.Mesh(
            new THREE.PlaneGeometry(gridSize, gridSize),
            new THREE.ShadowMaterial({ opacity: 0.35 })
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -S * 0.001;
        ground.receiveShadow = true;
        scene.add(ground);

        // 5. Vật thể 3D
        let edgeLines = null;
        if (DATA) {
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(b64ToBuffer(DATA.p)), 3));
            geo.setAttribute('normal',   new THREE.BufferAttribute(new Float32Array(b64ToBuffer(DATA.n)), 3));
            geo.setIndex(new THREE.BufferAttribute(new Uint32Array(b64ToBuffer(DATA.i)), 1));

            // Vật liệu kim loại xanh (giống bản chuẩn)
            const material = new THREE.MeshStandardMaterial({
                color: 0x3a7bd5,
                metalness: 0.4,
                roughness: 0.3,
                polygonOffset: true,
                polygonOffsetFactor: 1,
                polygonOffsetUnits: 1
            });
            const mesh = new THREE.Mesh(geo, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            scene.add(mesh);

            // Viền cạnh trắng kiểu CAD (chỉ vẽ cạnh gập > 30°)
            const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff });
            edgeLines = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 30), lineMaterial);
            scene.add(edgeLines);
        }

        resetCamera();

        // 6. Nút điều khiển
        function toggle(btn, fn) {
            btn.addEventListener('click', () => { const on = fn(); btn.classList.toggle('off', !on); });
        }
        document.getElementById('btn-reset').addEventListener('click', resetCamera);
        toggle(document.getElementById('btn-edges'), () => { if (!edgeLines) return true; edgeLines.visible = !edgeLines.visible; return edgeLines.visible; });
        toggle(document.getElementById('btn-grid'),  () => { grid.visible = !grid.visible; return grid.visible; });
        toggle(document.getElementById('btn-spin'),  () => { controls.autoRotate = !controls.autoRotate; return controls.autoRotate; });
        window.resetView = resetCamera;   // để gui.py gọi được

        // 7. Resize + vòng lặp render
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();
    })();
    </script>
</body>
</html>
"""
