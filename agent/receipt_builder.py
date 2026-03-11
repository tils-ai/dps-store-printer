import logging
import os
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 폰트 경로 후보
_FONT_PATHS = [
    "C:/Windows/Fonts/malgun.ttf",    # 맑은 고딕
    "C:/Windows/Fonts/malgunbd.ttf",  # 맑은 고딕 Bold
    "C:/Windows/Fonts/gulim.ttc",     # 굴림
]

_font_cache = {}

# 색상 (감열 프린터: 흑백만 지원, 회색은 출력 안됨)
_BLACK = "#000000"
_GRAY = "#000000"
_LIGHT_GRAY = "#000000"
_RULE_GRAY = "#000000"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """한글 폰트 로드. 캐시 사용."""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    # Bold 요청 시 malgunbd.ttf 우선
    paths = _FONT_PATHS if not bold else [_FONT_PATHS[1]] + _FONT_PATHS
    for path in paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue

    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def format_price(amount: int) -> str:
    return f"{amount:,}원"


def _format_date(iso_str: str) -> str:
    """ISO 날짜를 '2026. 03. 11. 14:30' 형식으로."""
    if not iso_str:
        return ""
    try:
        if "T" in iso_str:
            date_part = iso_str[:10]
            time_part = iso_str[11:16]
            y, m, d = date_part.split("-")
            return f"{y}. {m}. {d}. {time_part}"
        return iso_str
    except Exception:
        return iso_str


def build_receipt_images(
    receipt: dict,
    printer_dpi: int = 203,
) -> list[Image.Image]:
    """접수증 이미지를 생성한다.
    dualCopy=True이면 [매장용, 고객용] 2장, False이면 1장 반환.
    """
    dual_copy = receipt.get("dualCopy", True)

    if dual_copy:
        return [
            _build_single(receipt, printer_dpi, copy_label="매장용"),
            _build_single(receipt, printer_dpi, copy_label="고객용"),
        ]
    else:
        return [_build_single(receipt, printer_dpi, copy_label=None)]


def _build_single(
    receipt: dict,
    printer_dpi: int,
    copy_label: str | None = None,
) -> Image.Image:
    """접수증 이미지 1장을 생성한다."""
    width_mm = receipt.get("receiptWidthMm", 72)
    width_px = int(width_mm / 25.4 * printer_dpi)

    # DPI 비례 폰트 크기 (감열 프린터용 2배 크기)
    scale = printer_dpi / 203
    font_brand = _load_font(int(40 * scale), bold=True)      # 브랜드명
    font_body = _load_font(int(26 * scale))                   # 본문
    font_medium = _load_font(int(26 * scale), bold=True)      # 중간 굵기
    font_order_num = _load_font(int(32 * scale), bold=True)   # 주문번호
    font_contact = _load_font(int(30 * scale), bold=True)     # 연락처
    font_total = _load_font(int(30 * scale), bold=True)       # 총 결제금액
    font_small = _load_font(int(22 * scale))                  # 작은 텍스트
    font_item_detail = _load_font(int(24 * scale))            # 상품 옵션

    margin = int(24 * scale)
    line_gap = int(8 * scale)
    section_pad = int(16 * scale)

    # 임시 캔버스
    canvas_height = int(4000 * scale)
    img = Image.new("RGB", (width_px, canvas_height), "white")
    draw = ImageDraw.Draw(img)

    y = margin

    def text_height(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]

    def text_width(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def draw_center(text, font, y_pos, fill=_BLACK):
        tw = text_width(text, font)
        x = (width_px - tw) // 2
        draw.text((x, y_pos), text, fill=fill, font=font)
        return y_pos + text_height(text, font) + line_gap

    def draw_lr(left_text, right_text, left_font, right_font, y_pos,
                left_fill=_BLACK, right_fill=_BLACK):
        draw.text((margin, y_pos), left_text, fill=left_fill, font=left_font)
        rw = text_width(right_text, right_font)
        draw.text((width_px - margin - rw, y_pos), right_text,
                  fill=right_fill, font=right_font)
        lh = text_height(left_text, left_font)
        rh = text_height(right_text, right_font)
        return y_pos + max(lh, rh) + line_gap

    def draw_dashed_line(y_pos):
        """점선 구분선."""
        dash_len = int(4 * scale)
        gap_len = int(3 * scale)
        x = margin
        while x < width_px - margin:
            x_end = min(x + dash_len, width_px - margin)
            draw.line([(x, y_pos), (x_end, y_pos)], fill=_LIGHT_GRAY, width=1)
            x = x_end + gap_len
        return y_pos

    def draw_thin_line(y_pos):
        """얇은 실선."""
        draw.line([(margin, y_pos), (width_px - margin, y_pos)],
                  fill=_RULE_GRAY, width=1)
        return y_pos

    # === 헤더: 브랜드명 + 복사 라벨 ===
    y += section_pad

    brand_name = receipt.get("brandName", "")
    if brand_name:
        y = draw_center(brand_name, font_brand, y)

    if copy_label:
        y = draw_center(copy_label, font_small, y, fill=_GRAY)

    y += section_pad
    y = draw_dashed_line(y)
    y += section_pad

    # === 주문 정보 ===
    order_number = receipt.get("orderNumber", "")
    created_at = _format_date(receipt.get("createdAt", ""))
    recipient = receipt.get("recipientName", "")
    contact = receipt.get("contact", "")

    if order_number:
        y = draw_lr("주문번호", order_number, font_body, font_order_num, y,
                     left_fill=_GRAY)
        y += int(2 * scale)
    if created_at:
        y = draw_lr("일시", created_at, font_body, font_body, y,
                     left_fill=_GRAY)
    if recipient:
        y = draw_lr("수령인", recipient, font_body, font_body, y,
                     left_fill=_GRAY)
    if contact:
        y = draw_lr("연락처", contact, font_body, font_contact, y,
                     left_fill=_GRAY)

    y += section_pad
    y = draw_dashed_line(y)
    y += section_pad

    # === 상품 목록 ===
    items = receipt.get("items", [])
    for item in items:
        product_name = item.get("productName", "")
        draw.text((margin, y), product_name, fill=_BLACK, font=font_medium)
        y += text_height(product_name, font_medium) + line_gap

        option = item.get("optionName", "") or "기본"
        qty = item.get("quantity", 1)
        price = item.get("totalPrice", 0)
        detail = f"{option} × {qty}"
        y = draw_lr(detail, format_price(price), font_item_detail, font_item_detail, y,
                     left_fill=_GRAY, right_fill=_GRAY)
        y += int(4 * scale)

    y += section_pad
    y = draw_dashed_line(y)
    y += section_pad

    # === 금액 ===
    items_total = receipt.get("itemsTotal", 0)
    shipping = receipt.get("shippingAmount", 0)
    discount = receipt.get("discountAmount", 0)
    total = receipt.get("totalAmount", 0)

    y = draw_lr("상품금액", format_price(items_total), font_body, font_body, y,
                 left_fill=_GRAY)
    if shipping:
        y = draw_lr("배송비", format_price(shipping), font_body, font_body, y,
                     left_fill=_GRAY)
    if discount:
        y = draw_lr("할인", f"-{format_price(discount)}", font_body, font_body, y,
                     left_fill=_GRAY)

    # 총 결제금액 위 실선
    y += int(4 * scale)
    y = draw_thin_line(y)
    y += int(4 * scale)

    y = draw_lr("총 결제금액", format_price(total), font_total, font_total, y)

    y += section_pad
    y = draw_dashed_line(y)
    y += section_pad

    # === 결제 정보 ===
    payment_method = receipt.get("paymentMethod", "")
    payment_status = receipt.get("paymentStatus", "")
    if payment_method or payment_status:
        payment_value = " / ".join(filter(None, [payment_method, payment_status]))
        y = draw_lr("결제", payment_value, font_body, font_body, y,
                     left_fill=_GRAY)
        y += section_pad
        y = draw_dashed_line(y)
        y += section_pad

    # === 예상 소요시간 (수기 기입란) ===
    draw.text((margin, y), "예상 소요시간", fill=_GRAY, font=font_small)
    y += text_height("예상 소요시간", font_small) + int(6 * scale)
    line_y = y + int(48 * scale)
    draw_thin_line(line_y)
    y = line_y + section_pad

    y += section_pad
    y = draw_dashed_line(y)
    y += section_pad

    # === 출력 시각 ===
    now = datetime.now().strftime("%Y. %m. %d. %H:%M")
    y = draw_center(f"{now} 출력", font_small, y, fill=_LIGHT_GRAY)

    y += margin

    # 최종 높이로 crop
    img = img.crop((0, 0, width_px, y))
    return img
