"""Generate the LockBox app icon (lock icon in Tokyo Night palette)."""

from PIL import Image, ImageDraw


def create_icon():
    """Create a modern lock icon and save as .ico and .png."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors (Tokyo Night palette)
    bg = (26, 27, 38)          # #1a1b26
    shackle = (122, 162, 247)  # #7aa2f7 - blue
    body = (192, 202, 245)     # #c0caf5 - light
    keyhole_bg = (36, 40, 59)  # #24283b - dark
    accent = (158, 206, 106)   # #9ece6a - green

    # Background: rounded rectangle
    pad = 16
    r = 40
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=r,
        fill=bg,
    )

    # Subtle border
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=r,
        outline=(59, 66, 97),  # #3b4261
        width=3,
    )

    # Shackle (the U-shaped top part of the lock)
    cx = size // 2
    shackle_top = 52
    shackle_bottom = 120
    shackle_outer_r = 52
    shackle_width = 16

    # Draw shackle as a thick arc
    bbox_outer = [
        cx - shackle_outer_r,
        shackle_top,
        cx + shackle_outer_r,
        shackle_top + shackle_outer_r * 2,
    ]
    # Outer arc
    draw.arc(bbox_outer, 180, 360, fill=shackle, width=shackle_width)
    # Left leg
    draw.rectangle(
        [cx - shackle_outer_r, shackle_top + shackle_outer_r - 2,
         cx - shackle_outer_r + shackle_width, shackle_bottom + 8],
        fill=shackle,
    )
    # Right leg
    draw.rectangle(
        [cx + shackle_outer_r - shackle_width, shackle_top + shackle_outer_r - 2,
         cx + shackle_outer_r, shackle_bottom + 8],
        fill=shackle,
    )

    # Lock body (rounded rectangle)
    body_left = cx - 64
    body_right = cx + 64
    body_top = shackle_bottom
    body_bottom = size - 44
    draw.rounded_rectangle(
        [body_left, body_top, body_right, body_bottom],
        radius=16,
        fill=body,
    )

    # Keyhole circle
    kh_cx = cx
    kh_cy = body_top + (body_bottom - body_top) * 2 // 5
    kh_r = 16
    draw.ellipse(
        [kh_cx - kh_r, kh_cy - kh_r, kh_cx + kh_r, kh_cy + kh_r],
        fill=keyhole_bg,
    )

    # Keyhole slot (small rectangle below circle)
    slot_w = 10
    slot_h = 24
    draw.rectangle(
        [kh_cx - slot_w // 2, kh_cy + 4,
         kh_cx + slot_w // 2, kh_cy + 4 + slot_h],
        fill=keyhole_bg,
    )

    # Small green accent dot (top-right of lock body, like a status LED)
    led_r = 6
    led_cx = body_right - 18
    led_cy = body_top + 18
    draw.ellipse(
        [led_cx - led_r, led_cy - led_r, led_cx + led_r, led_cy + led_r],
        fill=accent,
    )

    # Save as .ico (multiple sizes for Windows) and .png
    img.save("lockbox.png", "PNG")

    # Create multiple sizes for the .ico
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images = []
    for s in sizes:
        resized = img.resize((s, s), Image.Resampling.LANCZOS)
        ico_images.append(resized)

    ico_images[0].save(
        "lockbox.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=ico_images[1:],
    )

    print("Created lockbox.ico and lockbox.png")


if __name__ == "__main__":
    create_icon()
