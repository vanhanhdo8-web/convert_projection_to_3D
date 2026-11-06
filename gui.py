"""
Giao diện: chuyển ảnh bản vẽ 3 hình chiếu sang mô hình 3D bằng Gemini AI (gói Free).

Khung "Xem 3D trực tiếp" nhúng chính file HTML Three.js (Chromium bên trong ứng dụng) nên
màu sắc, độ bóng, đổ bóng và độ mượt khi xoay giống hệt khi mở file .html trên trình duyệt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

# Bật tăng tốc GPU cho WebGL trong Chromium nhúng (phải đặt trước khi tạo QApplication)
_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
for _f in ("--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--enable-zero-copy"):
    if _f not in _flags:
        _flags += " " + _f
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()

from PIL import Image, ImageOps
from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView

    HAS_WEBENGINE = True
except Exception:  # thiếu QtWebEngine -> vẫn chạy, chỉ mở viewer bằng trình duyệt ngoài
    HAS_WEBENGINE = False

import converter
import gemini_client as gc
import model_builder as mb
import viewer_builder as vb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OUTPUT_DIR = converter.DEFAULT_OUTPUT_DIR
CACHE_DIR = os.path.join(tempfile.gettempdir(), "convert_projection_to_3d")

STYLE = """
* { font-family: 'Segoe UI', 'Noto Sans', 'Helvetica Neue', Arial; }
QMainWindow, QWidget#root { background: #1E1E24; }
QWidget#panel { background: #282A36; border-radius: 6px; }
QLabel { color: #F8F8F2; }
QLabel#header { color: #00D2BE; font-size: 17px; font-weight: bold; }
QLabel#sub { color: #A0AAB2; font-size: 11px; font-style: italic; }
QLabel#muted { color: #6272A4; font-size: 11px; }
QLabel#status { color: #8BE9FD; font-size: 11px; font-style: italic; }
QLabel#section { color: #50FA7B; font-size: 14px; font-weight: bold; }
QGroupBox { color: #00D2BE; font-weight: bold; font-size: 13px; border: 1px solid #44475A;
            border-radius: 6px; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit { background: #1E1E24; color: #FFFFFF; border: 1px solid #44475A; border-radius: 4px; padding: 5px; }
QLineEdit:focus { border-color: #00D2BE; }
QPushButton { background: #44475A; color: #F8F8F2; border: none; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #565a73; }
QPushButton:disabled { background: #343746; color: #7a7f99; }
QPushButton#browse { background: #BD93F9; color: #282A36; font-weight: bold; font-size: 13px; padding: 9px; }
QPushButton#browse:hover { background: #cdaafc; }
QPushButton#save { background: #50FA7B; color: #282A36; font-weight: bold; }
QPushButton#save:hover { background: #7bfc9b; }
QPushButton#convert { background: #FF79C6; color: #282A36; font-weight: bold; font-size: 14px; padding: 13px; }
QPushButton#convert:hover { background: #ff93d1; }
QPushButton#convert:disabled { background: #7a4b66; color: #c9b3c0; }
QPushButton#open { background: #50FA7B; color: #282A36; font-weight: bold; }
QPushButton#open:hover { background: #7bfc9b; }
QPushButton#open:disabled { background: #2f6b43; color: #8fb59c; }
QProgressBar { background: #1E1E24; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #00D2BE; border-radius: 3px; }
QLabel#preview { background: #1E1E24; border: 1px dashed #44475A; border-radius: 4px; color: #6272A4; }
"""


def open_path(path: str) -> None:
    """Mở thư mục / file bằng ứng dụng mặc định của hệ điều hành."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        QMessageBox.warning(None, "Không mở được", f"{path}\n\n{exc}")


def pil_to_pixmap(im: Image.Image, max_w: int, max_h: int) -> QPixmap:
    thumb = im.convert("RGB")
    thumb.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    qimg = QImage(thumb.tobytes("raw", "RGB"), thumb.width, thumb.height, thumb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


# --------------------------------------------------------------------------------------
# Luồng nền gọi AI (không làm treo giao diện)
# --------------------------------------------------------------------------------------
class ConvertWorker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, image: Image.Image, api_key: str, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._image, self._key, self._name = image, api_key, name

    def run(self) -> None:
        try:
            res = converter.convert_image(
                self._image, self._key, out_dir=OUTPUT_DIR, name=self._name, progress=self.progress.emit
            )
            self.succeeded.emit(res)
        except Exception as exc:
            self.failed.emit(str(exc))


# --------------------------------------------------------------------------------------
# Cửa sổ chính
# --------------------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chuyển Bản Vẽ 2D Sang 3D - AI Gemini Free")
        self.resize(1280, 780)
        self.setMinimumSize(1020, 660)
        self.setAcceptDrops(True)

        self.image: Image.Image | None = None
        self.image_path = ""
        self.latest_html: str | None = None
        self.worker: ConvertWorker | None = None

        self._build_ui()
        self._load_config()
        self.show_empty_viewer()

    # ----- giao diện -----
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 10, 14, 12)
        outer.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("📐 TỰ ĐỘNG CHUYỂN BẢN VẼ HÌNH CHIẾU SANG MÔ HÌNH 3D")
        title.setObjectName("header")
        sub = QLabel("Powered by Gemini 2.5 Flash (Free Tier)")
        sub.setObjectName("sub")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(sub)
        outer.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, 1)

        body.addWidget(self._build_left(), 0)
        body.addWidget(self._build_right(), 1)

    def _build_left(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        panel.setFixedWidth(410)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 8, 14, 14)
        lay.setSpacing(8)

        # 1. API key
        box = QGroupBox("🔑 1. Gemini API Key (Miễn phí)")
        bl = QVBoxLayout(box)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Dán API Key lấy tại aistudio.google.com")
        bl.addWidget(self.key_edit)
        row = QHBoxLayout()
        self.btn_eye = QPushButton("Hiện")
        self.btn_eye.clicked.connect(self._toggle_key)
        btn_save = QPushButton("💾 Lưu API Key")
        btn_save.setObjectName("save")
        btn_save.clicked.connect(self._on_save_key)
        row.addWidget(self.btn_eye)
        row.addStretch(1)
        row.addWidget(btn_save)
        bl.addLayout(row)
        lay.addWidget(box)

        # 2. Ảnh bản vẽ
        box2 = QGroupBox("🖼️ 2. Chọn Ảnh Bản Vẽ Kỹ Thuật")
        b2 = QVBoxLayout(box2)
        btn_browse = QPushButton("📂 Chọn file ảnh từ máy tính...  (hoặc kéo thả vào đây)")
        btn_browse.setObjectName("browse")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.clicked.connect(self.choose_image)
        b2.addWidget(btn_browse)

        row2 = QHBoxLayout()
        self.lbl_path = QLabel("Chưa chọn ảnh nào")
        self.lbl_path.setObjectName("muted")
        self.lbl_path.setWordWrap(True)
        self.btn_rotate = QPushButton("🔄 Xoay ảnh 90°")
        self.btn_rotate.setEnabled(False)
        self.btn_rotate.clicked.connect(self.rotate_image)
        row2.addWidget(self.lbl_path, 1)
        row2.addWidget(self.btn_rotate)
        b2.addLayout(row2)

        self.preview = QLabel("[Xem trước ảnh bản vẽ]")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(190)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        b2.addWidget(self.preview, 1)
        lay.addWidget(box2, 1)

        # 3. Tên file + chạy
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Tên file xuất:"))
        self.name_edit = QLineEdit("my_model")
        row3.addWidget(self.name_edit, 1)
        lay.addLayout(row3)

        self.btn_convert = QPushButton("⚡ BẮT ĐẦU CHUYỂN ĐỔI SANG 3D")
        self.btn_convert.setObjectName("convert")
        self.btn_convert.setCursor(Qt.PointingHandCursor)
        self.btn_convert.clicked.connect(self.start_conversion)
        lay.addWidget(self.btn_convert)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.lbl_status = QLabel("Sẵn sàng. Hãy chọn ảnh và bấm 'Bắt đầu chuyển đổi'.")
        self.lbl_status.setObjectName("status")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)
        return panel

    def _build_right(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        t = QLabel("🧊 XEM MÔ HÌNH 3D TRỰC TIẾP")
        t.setObjectName("section")
        hint = QLabel("(Chuột trái: xoay 360° • Chuột phải: di chuyển • Con lăn: zoom)")
        hint.setObjectName("muted")
        top.addWidget(t)
        top.addWidget(hint)
        top.addStretch(1)
        lay.addLayout(top)

        frame = QFrame()
        frame.setStyleSheet("background:#1a1a24; border-radius:4px;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        if HAS_WEBENGINE:
            self.view = QWebEngineView()
            s = self.view.settings()
            s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
            s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            self.view.page().setBackgroundColor(Qt.GlobalColor.black)
            fl.addWidget(self.view)
        else:
            self.view = None
            msg = QLabel(
                "Chưa có QtWebEngine nên không xem 3D trực tiếp trong cửa sổ này.\n"
                "Hãy chạy:  pip install PySide6\n"
                "Hoặc bấm 'Mở trên trình duyệt' để xem."
            )
            msg.setAlignment(Qt.AlignCenter)
            msg.setObjectName("muted")
            fl.addWidget(msg)
        lay.addWidget(frame, 1)

        bar = QHBoxLayout()
        self.btn_open_html = QPushButton("🚀 MỞ XEM 3D TRÊN TRÌNH DUYỆT")
        self.btn_open_html.setObjectName("open")
        self.btn_open_html.setEnabled(False)
        self.btn_open_html.clicked.connect(self.open_html_viewer)
        btn_reset = QPushButton("⟲ Đặt lại góc nhìn")
        btn_reset.clicked.connect(self.reset_view)
        btn_load = QPushButton("📥 Xem file OBJ/STL/JSON...")
        btn_load.clicked.connect(self.load_existing_model)
        btn_dir = QPushButton("📁 Mở thư mục chứa file")
        btn_dir.clicked.connect(self.open_folder)
        for b in (self.btn_open_html, btn_reset, btn_load, btn_dir):
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        return panel

    # ----- cấu hình -----
    def _load_config(self) -> None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                key = json.load(f).get("api_key", key) or key
        except Exception:
            pass
        self.key_edit.setText(key)

    def _save_config(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"api_key": self.key_edit.text().strip()}, f, indent=2)
        except Exception as exc:
            print("Lỗi lưu cấu hình:", exc)

    def _toggle_key(self) -> None:
        hidden = self.key_edit.echoMode() == QLineEdit.Password
        self.key_edit.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
        self.btn_eye.setText("Ẩn" if hidden else "Hiện")

    def _on_save_key(self) -> None:
        self._save_config()
        QMessageBox.information(self, "Đã Lưu", "API Key đã được lưu! Lần sau mở ứng dụng sẽ tự động điền.")

    # ----- ảnh -----
    def choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh bản vẽ kỹ thuật", "", "Ảnh (*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff);;Tất cả (*.*)"
        )
        if path:
            self.set_image(path)

    def set_image(self, path: str) -> None:
        try:
            self.image = gc.load_image(path)       # đã xoay đúng theo EXIF (ảnh chụp điện thoại)
        except Exception as exc:
            self.image = None
            self.preview.setPixmap(QPixmap())
            self.preview.setText(f"Không đọc được ảnh: {exc}")
            return
        self.image_path = path
        self.lbl_path.setText(os.path.basename(path))
        self.name_edit.setText(converter.safe_name(os.path.splitext(os.path.basename(path))[0]))
        self.btn_rotate.setEnabled(True)
        self._update_preview()

    def rotate_image(self) -> None:
        if self.image is not None:
            self.image = self.image.rotate(270, expand=True)    # 90° theo chiều kim đồng hồ
            self._update_preview()

    def _update_preview(self) -> None:
        if self.image is None:
            return
        w = max(self.preview.width() - 8, 200)
        h = max(self.preview.height() - 8, 150)
        self.preview.setPixmap(pil_to_pixmap(self.image, w, h))

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._update_preview()

    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:  # noqa: N802
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")):
                self.set_image(p)
                break

    # ----- chuyển đổi -----
    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def start_conversion(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập Gemini API Key (lấy miễn phí tại aistudio.google.com).")
            return
        if self.image is None:
            QMessageBox.warning(self, "Thiếu Ảnh", "Vui lòng chọn file ảnh bản vẽ kỹ thuật hợp lệ.")
            return
        name = converter.safe_name(self.name_edit.text())
        self._save_config()
        self.btn_convert.setEnabled(False)
        self.btn_convert.setText("⏳ Đang xử lý...")
        self.progress.setRange(0, 0)           # thanh chạy liên tục
        self.set_status("Đang gửi bản vẽ và gọi Gemini AI phân tích...")

        self.worker = ConvertWorker(self.image.copy(), key, name, self)
        self.worker.progress.connect(self.set_status)
        self.worker.succeeded.connect(self.on_success)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self) -> None:
        self.btn_convert.setEnabled(True)
        self.btn_convert.setText("⚡ BẮT ĐẦU CHUYỂN ĐỔI SANG 3D")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def on_success(self, res: converter.ConversionResult) -> None:
        self.latest_html = res.html
        self.btn_open_html.setEnabled(True)
        msg = f"Thành công ({res.model})! Đã tạo: {res.name}_viewer.html, .scad, .stl, .obj trong thư mục output"
        if res.warnings:
            msg += "\n⚠ " + " | ".join(res.warnings)
        self.set_status(msg)
        self.show_html(res.html)

    def on_error(self, err: str) -> None:
        self.set_status("Có lỗi xảy ra trong quá trình xử lý.")
        QMessageBox.critical(self, "Lỗi", err)

    # ----- viewer -----
    def show_html(self, path: str) -> None:
        if self.view is not None:
            self.view.load(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            webbrowser.open(Path(path).resolve().as_uri())

    def show_empty_viewer(self) -> None:
        if self.view is None:
            return
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, "empty_viewer.html")
        vb.write_viewer(path, mesh=None, title="Xem Mô Hình 3D")
        self.view.load(QUrl.fromLocalFile(path))

    def reset_view(self) -> None:
        if self.view is not None:
            self.view.page().runJavaScript("window.resetView && window.resetView();")

    def open_html_viewer(self) -> None:
        if self.latest_html and os.path.exists(self.latest_html):
            webbrowser.open(Path(self.latest_html).resolve().as_uri())
        else:
            QMessageBox.information(self, "Thông báo", "Chưa có file HTML nào được tạo.")

    def open_folder(self) -> None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        open_path(OUTPUT_DIR)

    def load_existing_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn mô hình 3D", "", "Mô hình (*.obj *.stl *.ply *.glb *.gltf *.json);;Tất cả (*.*)"
        )
        if not path:
            return
        try:
            base, ext = os.path.splitext(os.path.basename(path))
            info, title = None, base
            if ext.lower() == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    spec = json.load(f)
                mesh, _ = mb.build_mesh(spec)
                info, title = spec.get("info"), spec.get("title") or base
            else:
                mesh = mb.load_mesh_file(path)
            os.makedirs(CACHE_DIR, exist_ok=True)
            out = os.path.join(CACHE_DIR, f"{converter.safe_name(base)}_viewer.html")
            vb.write_viewer(out, mesh=mesh, title=title, info=info)
            self.latest_html = out
            self.btn_open_html.setEnabled(True)
            self.show_html(out)
            self.set_status(f"Đang xem: {os.path.basename(path)}")
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi", f"Không mở được mô hình:\n{exc}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
