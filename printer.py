import logging
import os
import sys
import time
from PIL import Image

import config

logger = logging.getLogger(__name__)


def list_printers() -> list[str]:
    """Windows에 설치된 프린터 이름 목록을 반환한다.

    Windows 외 환경(개발/DRYRUN)에서는 빈 리스트를 반환한다.
    """
    if sys.platform != "win32":
        return []
    try:
        import win32print  # Windows 전용 — lazy import

        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [p[2] for p in printers]
    except Exception:
        logger.exception("프린터 목록 조회 실패")
        return []


def print_image(image: Image.Image, printer_name: str = None):
    """이미지를 Windows 프린터로 출력한다.

    config.PRINTER_DRYRUN이 켜져있으면 실제 인쇄 대신 preview/ 폴더에 PNG로 저장한다
    (실물 라벨기 없이 출력 결과 검증용).
    """
    if config.PRINTER_DRYRUN:
        os.makedirs(config.PREVIEW_DIR, exist_ok=True)
        path = os.path.join(config.PREVIEW_DIR, f"{int(time.time() * 1000)}.png")
        image.save(path)
        logger.info("[DRYRUN] %s 저장 (실제 인쇄 생략)", path)
        return

    # win32는 Windows 전용 — DRYRUN/타 OS에서 import만 시도해도 실패하므로 lazy import
    import win32ui
    from PIL import ImageWin

    printer_name = printer_name or config.PRINTER_NAME

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    try:
        printable_width = hdc.GetDeviceCaps(110)   # PHYSICALWIDTH
        printable_height = hdc.GetDeviceCaps(111)  # PHYSICALHEIGHT

        # 프린터 해상도에 맞게 이미지 스케일링
        img_width, img_height = image.size
        scale = printable_width / img_width
        scaled_height = int(img_height * scale)

        hdc.StartDoc("LabelPrint")
        hdc.StartPage()

        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (0, 0, printable_width, scaled_height))

        hdc.EndPage()
        hdc.EndDoc()
        logger.info("출력 완료: %dx%d -> %dx%d", img_width, img_height, printable_width, scaled_height)
    finally:
        hdc.DeleteDC()


def print_images(images: list[Image.Image], printer_name: str = None):
    """여러 이미지를 순차적으로 출력한다."""
    for i, img in enumerate(images, 1):
        logger.info("페이지 %d/%d 출력 중...", i, len(images))
        print_image(img, printer_name)
