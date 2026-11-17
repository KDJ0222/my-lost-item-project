"""Preview against disposable sample data without modifying the real database.

Run: python -m scripts.preview_qa
"""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import uvicorn

from database import initialize_database
from main import create_app
from models import Item


def main():
    with TemporaryDirectory(prefix="campus-find-qa-") as directory:
        root = Path(directory)
        static_dir = root / "static"
        upload_dir = static_dir / "uploads"
        upload_dir.mkdir(parents=True)
        sample = root / "sample-wallet.png"
        image = Image.new("RGB", (400, 300), "#f1efe6")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((75, 85, 325, 225), radius=15, fill="#143d70")
        draw.line((90, 115, 310, 115), fill="#b3c3d4", width=3)
        draw.rounded_rectangle((265, 140, 335, 175), radius=5, fill="#1d4d84")
        image.save(sample)
        engine = create_engine(f"sqlite:///{(root / 'qa.db').as_posix()}", connect_args={"check_same_thread":False})
        initialize_database(engine)
        with Session(engine) as db:
            db.add_all([Item(
                title=f"화면 검증용 물품 {index:02d}", category="지갑", color="파랑",
                location=("중앙도서관" if index % 2 else "학생회관") + " 1층",
                keywords=["파랑", "가죽"], author="QA 사용자", contact="qa@example.com",
                report_type="lost" if index % 3 == 0 else "found",
                event_date=date(2026, 11, 1),
            ) for index in range(1, 22)])
            db.commit()
        print(f"QA sample image: {sample}", flush=True)
        print("Disposable preview: http://127.0.0.1:8001/", flush=True)
        uvicorn.run(create_app(db_engine=engine, static_dir=static_dir), host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
