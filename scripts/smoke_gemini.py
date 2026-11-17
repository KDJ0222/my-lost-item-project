"""Run one real Gemini image analysis without changing the project database.

Usage: python -m scripts.smoke_gemini [path/to/photo.png]
The default image is a small synthetic test image, not a user's uploaded photo.
"""

import argparse
from io import BytesIO
from pathlib import Path
import re

from fastapi import HTTPException
from google.genai.errors import APIError
from PIL import Image, ImageDraw

from config import get_settings
from services.gemini import analyze_image
from services.images import MAX_IMAGE_SIZE, inspect_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path)
    parser.add_argument("--diagnose", action="store_true", help="Show a redacted provider error message")
    args = parser.parse_args()
    if args.image:
        with args.image.open("rb") as file:
            data = file.read(MAX_IMAGE_SIZE + 1)
    else:
        image = Image.new("RGB", (320, 240), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((60, 70, 260, 180), radius=12, fill="navy")
        draw.line((70, 100, 250, 100), fill="gray", width=3)
        output = BytesIO()
        image.save(output, format="PNG")
        data = output.getvalue()
    try:
        if len(data) > MAX_IMAGE_SIZE:
            raise HTTPException(413, "이미지는 최대 5MB까지 업로드할 수 있습니다.")
        _, mime_type = inspect_image(data)
        result = analyze_image(data, mime_type)
    except HTTPException as exc:
        print(f"Gemini smoke test failed: HTTP {exc.status_code} - {exc.detail}")
        if args.diagnose and isinstance(exc.__cause__, APIError):
            message = exc.__cause__.message or ""
            api_key = get_settings().gemini_api_key
            if api_key:
                message = message.replace(api_key, "[REDACTED]")
            message = re.sub(r"AIza[A-Za-z0-9_-]+", "[REDACTED]", message)
            message = re.sub(r"https?://\S+", "[URL]", message)
            print(f"Provider status: {exc.__cause__.code}; message: {message[:1000]}")
        return 1
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
