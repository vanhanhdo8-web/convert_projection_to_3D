"""
gemini_client.py
================
Gọi Google Gemini (gói Free) để đọc ảnh bản vẽ 3 hình chiếu và trả về "spec" hình học (JSON).

- Thử model tốt nhất nhiều lần (khi 429/503), rồi mới chuyển sang model dự phòng.
- Gửi API key qua header (không nằm trong URL nên không lộ trong thông báo lỗi).
- Tự kiểm tra spec bằng `post_process` (vd. dựng thử mesh); nếu hỏng thì hỏi lại AI.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

from PIL import Image, ImageOps

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
BEST_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
RETRY_WAITS = [3, 6, 10, 15]      # giây chờ giữa các lần thử lại với model chính
FALLBACK_TRIES = 2
REQUEST_TIMEOUT = 180

ProgressFn = Callable[[str], None]


class GeminiError(RuntimeError):
    pass


@dataclass
class GeminiResult:
    spec: dict
    scad: Optional[str]
    raw_text: str
    model: str
    post: Any = None          # kết quả của post_process (vd. mesh)


# --------------------------------------------------------------------------------------
# Ảnh
# --------------------------------------------------------------------------------------
def prepare_image(im: Image.Image, max_dim: int = 1600) -> tuple[str, str]:
    """Chuẩn hoá ảnh (xoay theo EXIF, thu nhỏ, JPEG) -> (base64, mime)."""
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))   # nền trắng, không bị đen khi bỏ alpha
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
    if max(im.size) > max_dim:
        scale = max_dim / max(im.size)
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def load_image(path: str) -> Image.Image:
    im = Image.open(path)
    im.load()
    return ImageOps.exif_transpose(im)


# --------------------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------------------
_EXAMPLE = {
    "title": "Gá chạc lỗ tròn",
    "units": "mm",
    "info": [
        ["Dài x Rộng x Cao", "65 x 28 x 27"],
        ["Chiều cao đế", "12"],
        ["Lỗ tròn bên trái", "Ø13, tâm cách mép trái 20"],
        ["Rãnh chữ U", "rộng 18, sâu 14"],
    ],
    "solids": [
        {"shape": "box", "origin": [0, 0, 0], "size": [65, 28, 12]},
        {"shape": "box", "origin": [33, 0, 12], "size": [32, 28, 15]},
    ],
    "cuts": [
        {"shape": "cylinder", "axis": "z", "start": [20, 14, -1], "length": 14, "diameter": 13},
        {"shape": "box", "origin": [51, 5, 12], "size": [15, 18, 16]},
    ],
    "openscad": "$fn=100;\nmodule object_3d(){ difference(){ union(){ cube([65,28,12]); translate([33,0,12]) cube([32,28,15]); } translate([20,14,-1]) cylinder(d=13,h=14); translate([51,5,12]) cube([15,18,16]); } }\nobject_3d();",
}

PROMPT = """Bạn là kỹ sư CAD 3D chuyên đọc bản vẽ kỹ thuật cơ khí (hình chiếu đứng, hình chiếu bằng, hình chiếu cạnh, nét liền, nét đứt, kích thước ghi trên hình).

NHIỆM VỤ: đọc kỹ ảnh bản vẽ và dựng lại vật thể 3D dưới dạng JSON mô tả hình học (không viết code Three.js).

HỆ TỌA ĐỘ (đơn vị mm, giống OpenSCAD): X = chiều dài, Y = chiều rộng (sâu), Z = chiều cao (hướng lên).
Đặt góc dưới - trước - trái của vật thể tại (0,0,0). Hình chiếu đứng thể hiện (X,Z), hình chiếu bằng thể hiện (X,Y), hình chiếu cạnh thể hiện (Y,Z).
Hãy đối chiếu CẢ BA hình chiếu để suy ra đúng hình khối; nét đứt là phần khuất (lỗ, rãnh, bậc chìm).

ĐỊNH DẠNG TRẢ VỀ - MỘT object JSON duy nhất, KHÔNG kèm markdown/giải thích:
{
  "title": "tên ngắn của chi tiết",
  "units": "mm",
  "info": [["Nhãn", "giá trị"], ...],     // thông số quan trọng đọc từ bản vẽ (đường kính lỗ, chiều sâu rãnh...)
  "solids": [ ...khối... ],               // các khối được HỢP lại thành thân vật thể
  "cuts":   [ ...khối... ],               // các khối bị TRỪ đi: lỗ, rãnh, bậc cắt, hốc
  "openscad": "mã OpenSCAD hoàn chỉnh, có biến tham số, cho đúng vật thể này"
}

CÁC LOẠI KHỐI (dùng cho cả solids và cuts):
- {"shape":"box","origin":[x,y,z],"size":[dx,dy,dz]}
- {"shape":"cylinder","axis":"x|y|z","start":[x,y,z],"length":L,"diameter":d}   (start = tâm mặt đáy; có thể dùng "radius")
- {"shape":"sphere","center":[x,y,z],"diameter":d}
- {"shape":"extrude","plane":"XY|XZ|YZ","polygon":<biên dạng>,"holes":[<biên dạng>,...],"from":a,"to":b}
    đùn biên dạng 2D theo trục còn lại: XY -> toạ độ (x,y) đùn dọc Z; XZ -> (x,z) đùn dọc Y; YZ -> (y,z) đùn dọc X.
    Dùng cho chi tiết có hình chiếu là hình chữ L, chữ U, hình thang, đa giác, hoặc có lỗ tròn xuyên.
<biên dạng> là: [[u,v],[u,v],...] (đa giác, đi theo thứ tự các đỉnh) | {"circle":{"center":[u,v],"radius":r}} | {"rect":{"origin":[u,v],"size":[w,h]}} | {"slot":{"center":[u,v],"length":L,"width":W,"angle":0}}

QUY TẮC:
1. Mọi lỗ, rãnh, hốc, bậc cắt phải được mô tả bằng "cuts". Với lỗ xuyên/rãnh xuyên, kéo khối cắt vượt ra ngoài vật thể khoảng 1 mm mỗi phía để cắt sạch.
2. Dùng đúng số đo ghi trên bản vẽ. Nếu thiếu số đo, tính từ tỉ lệ các hình chiếu. Không bỏ sót chi tiết nào nhìn thấy trên bản vẽ.
3. Cung tròn trong đa giác phải xấp xỉ bằng ít nhất 24 điểm - nhưng ưu tiên dùng circle / slot / cylinder.
4. Phần "solids" và "openscad" phải mô tả CÙNG một vật thể.
5. Chỉ trả JSON hợp lệ (dấu nháy kép, không có chú thích // , không có dấu phẩy thừa).

VÍ DỤ ĐỊNH DẠNG (chỉ minh hoạ cấu trúc, KHÔNG phải vật thể của bạn):
""" + json.dumps(_EXAMPLE, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------------------
# Phân tích phản hồi
# --------------------------------------------------------------------------------------
def _extract_json(text: str) -> Any:
    t = text.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        chunk = t[a : b + 1]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            # bỏ dấu phẩy thừa trước } hoặc ]
            fixed = re.sub(r",\s*([}\]])", r"\1", chunk)
            return json.loads(fixed)
    raise GeminiError("AI không trả về JSON hợp lệ")


def parse_response_text(text: str) -> tuple[dict, Optional[str]]:
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise GeminiError("JSON của AI không phải một object")
    spec = data.get("spec") if isinstance(data.get("spec"), dict) else data
    scad = spec.pop("openscad", None) or data.get("openscad")
    if isinstance(scad, list):
        scad = "\n".join(map(str, scad))
    if not scad:
        m = re.search(r"```openscad\s*(.*?)```", text, re.S)
        scad = m.group(1).strip() if m else None
    if isinstance(scad, str):
        if "\\n" in scad and "\n" not in scad:
            scad = scad.replace("\\n", "\n")
    return spec, scad


def _response_text(result: dict) -> str:
    cands = result.get("candidates") or []
    if not cands:
        fb = result.get("promptFeedback", {})
        raise GeminiError(f"AI không trả kết quả ({fb.get('blockReason', 'không rõ lý do')})")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise GeminiError(f"AI trả về nội dung rỗng (finishReason={cands[0].get('finishReason')})")
    return text


# --------------------------------------------------------------------------------------
# Gọi API
# --------------------------------------------------------------------------------------
def _call(model: str, api_key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{API_ROOT}/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_message(e: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(e.read().decode("utf-8"))
        return f"({e.code}) {body.get('error', {}).get('message', body)}"
    except Exception:
        return f"({e.code}) {e.reason}"


def generate_spec(
    image_b64: str,
    mime: str,
    api_key: str,
    progress: ProgressFn = print,
    post_process: Optional[Callable[[dict], Any]] = None,
) -> GeminiResult:
    """
    Gửi ảnh cho Gemini và trả về GeminiResult.
    post_process(spec) có thể ném lỗi (vd. không dựng được mesh) -> thử lại.
    """
    if not api_key:
        raise GeminiError("Thiếu Gemini API Key")

    payload = {
        "contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": mime, "data": image_b64}}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }

    plan = [(BEST_MODEL, RETRY_WAITS)] + [(m, [2] * FALLBACK_TRIES) for m in FALLBACK_MODELS]
    last_error = "không rõ"

    for model, waits in plan:
        json_mode = True
        attempt = 0
        while attempt < len(waits):
            wait = waits[attempt]
            attempt += 1
            tag = f"{model} (lần {attempt}/{len(waits)})"
            progress(f"Gửi bản vẽ tới {tag}...")
            body = payload if json_mode else {**payload, "generationConfig": {"temperature": 0.2}}
            try:
                result = _call(model, api_key, body)
                text = _response_text(result)
                spec, scad = parse_response_text(text)
                post = post_process(spec) if post_process else None
                progress(f"Thành công với {model}.")
                return GeminiResult(spec=spec, scad=scad, raw_text=text, model=model, post=post)
            except urllib.error.HTTPError as e:
                msg = _http_message(e)
                last_error = f"{model} {msg}"
                if e.code in (401, 403) or "API key" in msg:
                    raise GeminiError(f"API Key không hợp lệ hoặc bị từ chối: {msg}")
                if e.code == 400 and json_mode and ("mime" in msg.lower() or "json" in msg.lower()):
                    json_mode = False        # model không hỗ trợ JSON mode -> thử lại thường
                    attempt -= 1
                    continue
                if e.code in (429, 500, 502, 503, 504):
                    if attempt < len(waits):
                        progress(f"{model} đang bận ({e.code}). Thử lại sau {wait}s...")
                        time.sleep(wait)
                        continue
                    progress(f"{model} không phản hồi. Chuyển sang model dự phòng...")
                    break
                progress(f"{model} lỗi {e.code}. Chuyển model khác...")
                break                         # 404/400... -> model khác
            except (GeminiError, ValueError, json.JSONDecodeError) as e:
                # JSON hỏng hoặc spec không dựng được -> hỏi lại
                last_error = f"{model}: {e}"
                progress(f"Dữ liệu AI trả về chưa dùng được ({e}). Thử lại...")
                time.sleep(1)
                continue
            except Exception as e:             # mất mạng, timeout...
                last_error = f"{model}: {e}"
                progress(f"Lỗi kết nối: {e}. Thử lại sau 2s...")
                time.sleep(2)
                continue

    raise GeminiError(f"Không thể lấy kết quả từ các model Gemini. Lỗi cuối: {last_error}")
