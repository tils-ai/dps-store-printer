import logging
import os

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 폰트 경로 후보
_FONT_PATHS = [
    "C:/Windows/Fonts/malgun.ttf",    # 맑은 고딕
    "C:/Windows/Fonts/malgunbd.ttf",  # 맑은 고딕 Bold
    "C:/Windows/Fonts/gulim.ttc",     # 굴림
]

_font_cache = {}


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


def build_receipt_images(
    receipt: dict,
    printer_dpi: int = 203,
) -> list[Image.Image]:
    """접수증 이미지를 생성한다.
    dualCopy=True이면 [매장용, 고객용] 2장, False이면 1장 반환.
    """
    dual_copy = receipt.get("dualCopy", False)

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

    # DPI 비례 폰트 크기
    scale = printer_dpi / 203
    font_brand = _load_font(int(24 * scale), bold=True)
    font_body = _load_font(int(16 * scale))
    font_bold = _load_font(int(18 * scale), bold=True)
    font_small = _load_font(int(14 * scale))

    margin = int(16 * scale)
    line_gap = int(6 * scale)
    section_gap = int(12 * scale)

    # 임시 캔버스 (높이는 넉넉하게)
    canvas_height = int(2000 * scale)
    img = Image.new("RGB", (width_px, canvas_height), "white")
    draw = ImageDraw.Draw(img)

    y = margin
    content_width = width_px - margin * 2

    def draw_center(text, font, y_pos):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (width_px - tw) // 2
        draw.text((x, y_pos), text, fill="black", font=font)
        return y_pos + bbox[3] - bbox[1] + line_gap

    def draw_left(text, font, y_pos, x_offset=0):
        draw.text((margin + x_offset, y_pos), text, fill="black", font=font)
        bbox = draw.textbbox((0, 0), text, font=font)
        return y_pos + bbox[3] - bbox[1] + line_gap

    def draw_lr(left_text, right_text, font, y_pos):
        draw.text((margin, y_pos), left_text, fill="black", font=font)
        bbox_r = draw.textbbox((0, 0), right_text, font=font)
        rw = bbox_r[2] - bbox_r[0]
        draw.text((width_px - margin - rw, y_pos), right_text, fill="black", font=font)
        bbox_l = draw.textbbox((0, 0), left_text, font=font)
        return y_pos + max(bbox_l[3] - bbox_l[1], bbox_r[3] - bbox_r[1]) + line_gap

    def draw_separator(y_pos):
        sep_y = y_pos + line_gap // 2
        draw.line([(margin, sep_y), (width_px - margin, sep_y)], fill="black", width=1)
        return sep_y + line_gap

    # --- 레이아웃 ---

    # 복사 라벨 (매장용/고객용)
    if copy_label:
        y = draw_center(f"[{copy_label}]", font_body, y)
        y += line_gap

    # 브랜드명
    brand_name = receipt.get("brandName", "")
    if brand_name:
        y = draw_center(f"★ {brand_name} ★", font_brand, y)
    y += section_gap

    # 구분선
    y = draw_separator(y)

    # 주문 정보
    order_number = receipt.get("orderNumber", "")
    created_at = receipt.get("createdAt", "")
    # ISO → 보기 좋은 형식
    if created_at and "T" in created_at:
        date_part = created_at[:10].replace("-", ".")
        time_part = created_at[11:16]
        created_at = f"{date_part} {time_part}"

    recipient = receipt.get("recipientName", "")
    contact = receipt.get("contact", "")

    info_items = [
        ("주문번호", order_number),
        ("일시", created_at),
        ("수령인", recipient),
        ("연락처", contact),
    ]
    label_width = int(80 * scale)
    for label, value in info_items:
        if value:
            draw.text((margin, y), label, fill="black", font=font_body)
            draw.text((margin + label_width, y), value, fill="black", font=font_body)
            bbox = draw.textbbox((0, 0), label, font=font_body)
            y += bbox[3] - bbox[1] + line_gap

    y += section_gap
    y = draw_separator(y)

    # 상품 목록
    items = receipt.get("items", [])
    for item in items:
        product_name = item.get("productName", "")
        y = draw_left(product_name, font_body, y)

        option = item.get("optionName", "")
        qty = item.get("quantity", 1)
        price = item.get("totalPrice", 0)
        detail = f"  {option} × {qty}" if option else f"  × {qty}"
        y = draw_lr(detail, format_price(price), font_small, y)

    y += section_gap
    y = draw_separator(y)

    # 금액
    items_total = receipt.get("itemsTotal", 0)
    shipping = receipt.get("shippingAmount", 0)
    discount = receipt.get("discountAmount", 0)
    total = receipt.get("totalAmount", 0)

    y = draw_lr("상품금액", format_price(items_total), font_body, y)
    if shipping:
        y = draw_lr("배송비", format_price(shipping), font_body, y)
    if discount:
        y = draw_lr("할인", f"-{format_price(discount)}", font_body, y)
    y = draw_lr("총 결제금액", format_price(total), font_bold, y)

    y += section_gap
    y = draw_separator(y)

    # 결제 정보
    payment_method = receipt.get("paymentMethod", "")
    payment_status = receipt.get("paymentStatus", "")
    if payment_method or payment_status:
        payment_text = " / ".join(filter(None, [payment_method, payment_status]))
        y = draw_left(payment_text, font_body, y)

    y += margin

    # 최종 높이로 crop
    img = img.crop((0, 0, width_px, y))
    return img
