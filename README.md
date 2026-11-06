# 📐 Convert Projection to 3D (AI Powered)

Phần mềm tự động chuyển ảnh bản vẽ kỹ thuật (3 hình chiếu: đứng, bằng, cạnh) thành **mô hình 3D tương tác** và mã nguồn CAD, sử dụng **Google Gemini AI (gói Free 100%)**.

---

## 🌟 Điểm nổi bật

- **File HTML 3D luôn đúng chuẩn.** AI không còn tự viết code Three.js (mỗi lần một kiểu, hay thiếu lỗ/rãnh). Thay vào đó AI trả về *dữ liệu hình học* (khối, lỗ, rãnh, đùn biên dạng…), phần mềm tự dựng mô hình rồi đổ vào **một khuôn HTML cố định**: nền tối, lưới nền, vật liệu xanh kim loại bóng, viền trắng kiểu CAD, đổ bóng mềm, bảng thông số, nút *Đặt lại góc nhìn / Viền cạnh / Lưới nền / Tự xoay*.
- **Xem 3D trực tiếp ngay trong `gui.py`, mượt như HTML.** Khung xem nhúng chính file HTML Three.js (Chromium nhúng) nên **màu sắc, độ bóng, đổ bóng, độ mượt khi xoay giống hệt** khi mở file `.html` trên trình duyệt (không còn dùng matplotlib).
- **Chạy offline:** Three.js được nhúng sẵn trong mỗi file HTML (không cần mạng/CDN), gửi cho người khác là xem được ngay.
- **Một mô hình – nhiều định dạng, khớp 100%:** `.html` (Three.js) · `.scad` (OpenSCAD) · `.stl` (in 3D / CNC) · `.obj` · `.json` (dữ liệu hình học, sửa tay được).
- **Mặt cong mịn, cạnh vuông sắc:** pháp tuyến tính theo góc gập (như phần mềm CAD), lỗ tròn/mặt trụ không bị "múi".
- **Bền bỉ với API Free:** thử `gemini-2.5-flash` nhiều lần (3s/6s/10s/15s) khi 429/503, sau đó mới sang model dự phòng; tự hỏi lại AI nếu JSON trả về hỏng hoặc không dựng được hình.
- **Tiện dụng:** kéo-thả ảnh, xoay ảnh 90°, tự xoay đúng theo EXIF của ảnh điện thoại, lưu API Key, mở thư mục kết quả, xem lại file OBJ/STL/JSON có sẵn.

---

## 🚀 Cài đặt

Yêu cầu: **Python 3.10 – 3.13**.

```bash
git clone https://github.com/vanhanhdo8-web/convert_projection_to_3D.git
cd convert_projection_to_3D
pip install -r requirements.txt
```

Thư viện: `pillow`, `numpy`, `trimesh`, `shapely`, `mapbox-earcut`, `manifold3d` (cắt lỗ/rãnh chính xác), `PySide6` (giao diện + khung xem 3D).

---

## 📖 Sử dụng

### Cách 1: Giao diện đồ họa (khuyên dùng)
- **Windows:** bấm đúp `run_app.bat` (tự cài thư viện lần đầu) hoặc `python gui.py`
- **Linux/macOS:** `./run_app.sh` hoặc `python3 gui.py`

1. Nhập **Gemini API Key** miễn phí (lấy tại [Google AI Studio](https://aistudio.google.com/)) → **Lưu API Key**.
2. **Chọn ảnh** bản vẽ (hoặc kéo-thả vào cửa sổ). Nếu ảnh bị ngang, bấm **🔄 Xoay ảnh 90°**.
3. Bấm **⚡ BẮT ĐẦU CHUYỂN ĐỔI SANG 3D**.
4. Mô hình hiện ngay ở khung bên phải – xoay bằng chuột trái, di chuyển bằng chuột phải, zoom bằng con lăn.
5. Kết quả nằm trong thư mục `output/` (nút **📁 Mở thư mục chứa file**). Nút **🚀 Mở xem 3D trên trình duyệt** mở file HTML đầy đủ.

### Cách 2: Dòng lệnh
```bash
python gemini_drawing_to_cad.py ban_ve.jpg -n ten_file
```
API Key lấy từ `--key`, biến môi trường `GEMINI_API_KEY` hoặc `config.json`.

### Tạo HTML từ file 3D có sẵn
```bash
python create_viewer.py model_3d.obj                  # hoặc .stl / .ply / .glb
python create_viewer.py examples/ga_chac.json -t "Gá chạc"   # từ dữ liệu hình học
```

---

## 🧩 Định dạng dữ liệu hình học (`.json`)

Hệ tọa độ giống OpenSCAD: **X = dài, Y = rộng, Z = cao**, đơn vị mm. Các khối trong `solids` được **hợp**, các khối trong `cuts` bị **trừ** (lỗ, rãnh, bậc cắt).

```json
{
  "title": "Gá chạc lỗ tròn",
  "info": [["Lỗ tròn", "Ø13"], ["Rãnh chữ U", "rộng 18, sâu 14"]],
  "solids": [
    {"shape": "box", "origin": [0, 0, 0],  "size": [65, 28, 12]},
    {"shape": "box", "origin": [33, 0, 12], "size": [32, 28, 15]}
  ],
  "cuts": [
    {"shape": "cylinder", "axis": "z", "start": [20, 14, -1], "length": 14, "diameter": 13},
    {"shape": "box", "origin": [51, 5, 12], "size": [15, 18, 16]}
  ]
}
```

Khối hỗ trợ: `box`, `cylinder` (trục x/y/z), `sphere`, `extrude` (đùn biên dạng 2D trên mặt phẳng XY/XZ/YZ, biên dạng có thể là đa giác, `circle`, `rect`, `slot`, kèm `holes`). Chi tiết xem đầu file `model_builder.py`.

---

## 📂 Cấu trúc dự án

```
├── gui.py                    # Giao diện chính (PySide6 + khung xem 3D nhúng)
├── gemini_client.py          # Gọi Gemini: prompt, retry, fallback, phân tích JSON
├── model_builder.py          # Dựng mesh 3D từ dữ liệu hình học (union/cut), sinh OpenSCAD
├── viewer_builder.py         # Khuôn HTML Three.js chuẩn (màu, bóng, ánh sáng)
├── converter.py              # Quy trình ảnh -> AI -> mesh -> HTML/SCAD/STL/OBJ/JSON
├── gemini_drawing_to_cad.py  # Bản dòng lệnh
├── create_viewer.py          # OBJ/STL/JSON -> HTML xem 3D
├── vendor/                   # Three.js r128 + OrbitControls (nhúng offline)
├── examples/                 # Ví dụ: ga_chac.* (đầu ra mới) và legacy/ (file cũ)
├── output/                   # Kết quả xuất ra (tự tạo)
├── run_app.bat / run_app.sh  # Khởi chạy nhanh
├── requirements.txt
├── config.example.json       # Mẫu file lưu API Key
└── .gitignore
```

Trong `output/`, mỗi lần chuyển đổi tạo: `<tên>_viewer.html`, `<tên>.scad` (khớp 100% với 3D), `<tên>_ai.scad` (bản OpenSCAD có tham số do AI viết, nếu có), `<tên>.stl`, `<tên>.obj`, `<tên>.json`.

---

## 🛠️ Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Khung 3D trống/đen | Cập nhật driver card đồ họa; thử `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu` (chạy phần mềm, chậm hơn) hoặc bấm *Mở xem 3D trên trình duyệt*. |
| Báo thiếu `manifold3d` / lỗ không được cắt | `pip install manifold3d` |
| Lỗi 429 / 503 | Gói Free của Gemini đang quá tải/hết lượt – phần mềm tự thử lại và đổi model; đợi ít phút rồi chạy lại. |
| Mô hình sai chi tiết | Chụp ảnh rõ, thẳng, đủ 3 hình chiếu và kích thước; có thể sửa `output/<tên>.json` rồi xem lại bằng nút *📥 Xem file OBJ/STL/JSON*. |

## 🔒 Bảo mật
`config.json` (chứa API Key cá nhân) nằm trong `.gitignore`, không bị đưa lên GitHub. API Key được gửi qua header HTTP, không nằm trong URL.

## 📄 License
Phát hành theo giấy phép [MIT License](LICENSE). Three.js: MIT (`vendor/THREE_LICENSE.txt`).
