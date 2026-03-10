import logging
import win32print
import win32ui
from PIL import Image, ImageWin

import config

logger = logging.getLogger(__name__)


def print_image(image: Image.Image, printer_name: str = None):
    """이미지를 Windows 프린터로 출력한다."""
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
