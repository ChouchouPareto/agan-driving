import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.core.config import get_settings
from app.ocr_services import recognize


def sample_image(kind: str) -> bytes:
    image = Image.new("RGB", (1500, 720), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("/System/Library/Fonts/Hiragino Sans GB.ttc")
    font = ImageFont.truetype(str(font_path), 44) if font_path.exists() else ImageFont.load_default()
    lines = [
        "驾驶机动车通过没有交通信号的交叉路口怎样行驶？",
        "A. 减速慢行，并让右方道路来车先行",
        "B. 加速通过",
        "C. 左方车辆先行",
        "D. 鸣喇叭后直接通过",
    ]
    if kind == "long_option":
        lines[1] = "A. 进入路口前减速慢行，仔细观察，并让右方道路来车先行"
    if kind == "irrelevant":
        lines = ["这是一张非题目图片", "系统不应替用户判断答案"]
    for index, line in enumerate(lines):
        draw.text((70, 70 + index * 115), line, fill="black", font=font)
    if kind == "rotated":
        image = image.rotate(3, expand=False, fillcolor="white")
    if kind == "low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.42).filter(ImageFilter.GaussianBlur(0.8))
    if kind == "small":
        image = image.resize((750, 360))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> None:
    settings = get_settings()
    if settings.mock_ocr:
        raise SystemExit("SKIP: DASHSCOPE_API_KEY is not configured; real OCR smoke was not run.")
    results = []
    for kind in ["clear", "rotated", "low_contrast", "long_option", "irrelevant"]:
        result = recognize(sample_image(kind), "image/png")
        output = {
            "sample": kind,
            "question_type": result.question_type,
            "stem": result.stem.value,
            "options": [{"label": item.label, "value": item.value} for item in result.options],
            "warnings": result.warnings,
        }
        if result.stem.value in {"题干", "stem"} or (result.options and all(item.value in {"选项", "option"} for item in result.options)):
            raise SystemExit(f"FAIL: {kind} copied placeholders instead of recognizing the image.")
        results.append(output)
    print(json.dumps({"model": settings.ocr_model_id, "samples": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
