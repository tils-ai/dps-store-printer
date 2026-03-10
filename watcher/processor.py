import logging
import os
import shutil
import tempfile
import zipfile

from pdf2image import convert_from_path
from PIL import Image

import config
from printer import print_image

logger = logging.getLogger(__name__)


def resize_image(image: Image.Image) -> Image.Image:
    """라벨 폭(72mm)에 맞게 리사이즈. 높이는 비율 유지."""
    target_width = config.LABEL_WIDTH_PX
    w, h = image.size
    ratio = target_width / w
    target_height = int(h * ratio)
    return image.resize((target_width, target_height), Image.LANCZOS)


def pdf_to_images(pdf_path: str):
    """PDF를 페이지별 이미지로 변환 후 리사이즈. 한 페이지씩 yield."""
    kwargs = {"dpi": config.RENDER_DPI}
    if config.POPPLER_PATH:
        kwargs["poppler_path"] = config.POPPLER_PATH

    for page in convert_from_path(pdf_path, **kwargs):
        yield resize_image(page)


def process_pdf(pdf_path: str):
    """PDF 파일을 이미지로 변환하여 한 페이지씩 출력."""
    logger.info("PDF 처리: %s", pdf_path)
    for i, image in enumerate(pdf_to_images(pdf_path), 1):
        logger.info("페이지 %d 출력 중...", i)
        print_image(image)


def process_zip(zip_path: str):
    """ZIP 파일에서 PDF를 추출하여 출력."""
    logger.info("ZIP 처리: %s", zip_path)
    tmpdir = tempfile.mkdtemp(prefix="label_")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
            if not pdf_names:
                raise ValueError(f"ZIP 내 PDF 파일 없음: {zip_path}")
            for name in sorted(pdf_names):
                extracted = zf.extract(name, tmpdir)
                process_pdf(extracted)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def process_file(file_path: str):
    """파일을 처리하고 완료/실패 폴더로 이동."""
    os.makedirs(config.DONE_DIR, exist_ok=True)
    os.makedirs(config.ERROR_DIR, exist_ok=True)

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext == ".pdf":
            process_pdf(file_path)
        elif ext == ".zip":
            process_zip(file_path)
        else:
            logger.warning("지원하지 않는 파일 형식: %s", filename)
            return

        dest = os.path.join(config.DONE_DIR, filename)
        dest = _unique_path(dest)
        shutil.move(file_path, dest)
        logger.info("완료 → %s", dest)

    except Exception:
        logger.exception("처리 실패: %s", filename)
        dest = os.path.join(config.ERROR_DIR, filename)
        dest = _unique_path(dest)
        try:
            shutil.move(file_path, dest)
        except Exception:
            logger.exception("에러 폴더 이동 실패: %s", filename)


def _unique_path(path: str) -> str:
    """동일 파일명 충돌 시 번호를 붙여 고유 경로 반환."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{base}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1
