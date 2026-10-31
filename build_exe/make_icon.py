# -*- coding: utf-8 -*-
"""
生成应用图标 app.ico（多尺寸，零外部素材）

设计：深蓝渐变圆角方块底 + 新能源车侧面剪影
      白色车身 / 深蓝车窗 / 绿色闪电 / 深色轮胎
按 0~1000 设计坐标几何绘制，「圆角多边形」勾勒车身（分段清楚、转角圆润），
4 倍超采样后 LANCZOS 缩放，保证 256px 下有质感、16px 下仍能看出是一辆车。
"""
import math
import os
from PIL import Image, ImageDraw, ImageChops, ImageFilter

SIZE = 512           # 输出主尺寸
SS = 4               # 超采样倍数
Canvas = SIZE * SS
U = Canvas / 1000.0  # 设计坐标 -> 像素


ZOOM = 1.09          # 整车相对画布的放大倍数
CX, CY = 487.0, 492.0  # 缩放中心（车辆几何中心）


def P(x, y):
    return ((CX + (x - CX) * ZOOM) * U, (CY + (y - CY) * ZOOM) * U)


def rounded_poly(pts, seg=14):
    """圆角多边形：每个顶点带圆角半径，角上插二次贝塞尔采样点"""
    out, n = [], len(pts)
    for i in range(n):
        px, py, pr = pts[i]
        ax, ay, _ = pts[(i - 1) % n]
        bx, by, _ = pts[(i + 1) % n]
        v1 = (ax - px, ay - py)
        v2 = (bx - px, by - py)
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 < 1e-6 or l2 < 1e-6:
            out.append((px, py))
            continue
        r = min(pr, l1 * 0.45, l2 * 0.45)
        p1 = (px + v1[0] / l1 * r, py + v1[1] / l1 * r)
        p2 = (px + v2[0] / l2 * r, py + v2[1] / l2 * r)
        for k in range(seg + 1):
            t = k / seg
            u = 1 - t
            out.append((u * u * p1[0] + 2 * u * t * px + t * t * p2[0],
                        u * u * p1[1] + 2 * u * t * py + t * t * p2[1]))
    return out


def rounded_rect_mask(size, radius_ratio=0.225):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255
    )
    return m


def vertical_gradient(size, top, bottom):
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        strip.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((size, size), Image.BILINEAR)


def radial_glow(size, cx_ratio, cy_ratio, r_ratio, color, alpha=1.0):
    """柔和径向光斑：小图计算再放大，速度快"""
    s = 200
    small = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = small.load()
    cx, cy, r = cx_ratio * s, cy_ratio * s, r_ratio * s
    for y in range(s):
        for x in range(s):
            d = math.hypot(x - cx, y - cy)
            a = 1.0 - min(1.0, d / r)
            a = a * a * a
            if a > 0.002:
                px[x, y] = (color[0], color[1], color[2], int(255 * alpha * a))
    return small.resize((size, size), Image.BICUBIC)


# ---------------- 车辆几何（设计坐标 0~1000，车头朝右） ----------------
BODY = [
    (150, 592, 10),   # 底盘后
    (100, 586, 14),   # 后保险杠
    (86, 568, 16),    # 尾部下沿
    (74, 508, 24),    # 尾门最左点
    (108, 474, 44),   # 尾部上角
    (400, 356, 64),   # 溜背斜线 -> 车顶后
    (516, 348, 50),   # 车顶（微拱）
    (614, 358, 60),   # 车顶前角
    (702, 452, 70),   # A 柱底 / 风挡下沿
    (858, 464, 46),   # 引擎盖前
    (901, 509, 34),   # 车头最前点
    (884, 582, 18),   # 前脸下角
    (830, 592, 10),   # 底盘前
]

WIN_REAR = [(300, 448), (392, 378), (486, 374), (486, 448)]
WIN_FRONT = [(506, 448), (506, 374), (568, 372), (656, 448)]

WHEEL_Y = 578
WHEEL_X = (250, 755)
WHEEL_R = 58
ARCH_R = 61

WHITE = (250, 252, 255, 255)
GLASS = (13, 40, 96, 255)
GLASS_HI = (62, 112, 190, 255)
TIRE = (14, 22, 40, 255)
RIM = (203, 217, 236, 255)
RIM_HUB = (34, 52, 84, 255)
BOLT = (36, 214, 158, 255)
LAMP_DARK = (16, 44, 104, 255)
LAMP_GLOW = (128, 232, 255, 255)
BG_TOP = (40, 114, 242)
BG_BOT = (8, 30, 88)


def band_shade(y0, y1, color, alpha_max, power=1.6):
    """从 y0 到 y1 由透到实的竖向暗部（设计坐标）"""
    strip = Image.new("RGBA", (1, 256), (0, 0, 0, 0))
    for i in range(256):
        t = i / 255.0
        strip.putpixel((0, i), (color[0], color[1], color[2], int(alpha_max * (t ** power))))
    y0 = CY + (y0 - CY) * ZOOM
    y1 = CY + (y1 - CY) * ZOOM
    h = max(1, int((y1 - y0) * U))
    full = strip.resize((Canvas, h), Image.BILINEAR)
    out = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    out.paste(full, (0, int(y0 * U)))
    return out


def draw_car():
    """车辆图层（RGBA，已按轮拱开洞）"""
    layer = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))

    # 车身：顶部纯白、向下收冷色，做出钣金体积
    body_mask = Image.new("L", (Canvas, Canvas), 0)
    ImageDraw.Draw(body_mask).polygon([P(x, y) for x, y in rounded_poly(BODY)], fill=255)
    layer.paste(vertical_gradient(Canvas, (255, 255, 255), (222, 233, 249)), (0, 0), body_mask)

    # 腰线以下压一层柔和暗部，车身立刻有厚度
    shade = band_shade(446, 598, (26, 58, 120), 70, 1.7)
    shade.putalpha(ImageChops.multiply(shade.split()[3], body_mask))
    layer = Image.alpha_composite(layer, shade)

    d = ImageDraw.Draw(layer)

    # 侧窗（两块，中间留 B 柱）：上浅下深的玻璃渐变
    win_mask = Image.new("L", (Canvas, Canvas), 0)
    wd = ImageDraw.Draw(win_mask)
    for quad in (WIN_REAR, WIN_FRONT):
        wd.polygon([P(*p) for p in quad], fill=255)
    layer.paste(vertical_gradient(Canvas, (40, 82, 158), (7, 20, 58)), (0, 0), win_mask)
    d = ImageDraw.Draw(layer)
    # 玻璃上的一道反光
    d.polygon([P(522, 424), P(556, 388), P(574, 388), P(540, 428)], fill=GLASS_HI)
    d.polygon([P(336, 418), P(378, 386), P(392, 386), P(350, 422)], fill=GLASS_HI)
    # 车窗下沿一条细亮线，模拟窗框
    d.line([P(506, 449), P(658, 451)], fill=(255, 255, 255, 120), width=max(1, int(2.4 * U)))

    # 车灯：前大灯斜置，尾灯带红光
    d.polygon([P(846, 500), P(896, 514), P(886, 556), P(834, 542)], fill=LAMP_DARK)
    d.polygon([P(854, 511), P(890, 522), P(886, 533), P(850, 522)], fill=LAMP_GLOW)
    d.polygon([P(78, 494), P(126, 486), P(126, 520), P(78, 528)], fill=LAMP_DARK)
    d.polygon([P(86, 498), P(118, 492), P(118, 501), P(86, 507)], fill=(255, 122, 122, 255))

    # 车门分缝 + 门把手
    seam = (168, 189, 218, 190)
    d.line([P(496, 454), P(496, 584)], fill=seam, width=max(1, int(4.0 * U)))
    d.line([P(686, 456), P(700, 584)], fill=seam, width=max(1, int(4.0 * U)))
    for x0 in (392, 600):
        d.rounded_rectangle([P(x0, 508)[0], P(x0, 508)[1], P(x0 + 48, 526)[0], P(x0 + 48, 526)[1]],
                            radius=int(7 * U), fill=(196, 211, 234, 235))

    # 绿色闪电（新能源标识），落在前门上
    bolt = [(-0.20, -1.00), (0.44, -1.00), (0.02, -0.10),
            (0.40, -0.10), (-0.32, 1.00), (-0.04, 0.10), (-0.44, 0.10)]
    cx, cy, h = 580, 532, 92
    bolt_pts = [P(cx + x * h * 0.62, cy + y * h * 0.5) for x, y in bolt]
    glow = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(bolt_pts, fill=(36, 214, 158, 130))
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(9 * U)))
    d = ImageDraw.Draw(layer)
    d.polygon(bolt_pts, fill=BOLT)

    # 轮拱开洞：透出底色，车身在轮子上方留出弧度
    holes = Image.new("L", (Canvas, Canvas), 255)
    hd = ImageDraw.Draw(holes)
    for wx in WHEEL_X:
        r = ARCH_R * ZOOM * U
        x, y = P(wx, WHEEL_Y)
        hd.ellipse([x - r, y - r, x + r, y + r], fill=0)
    layer.putalpha(ImageChops.multiply(layer.split()[3], holes))
    return layer


def draw_wheels(img):
    """在给定图层上画轮胎 + 五辐轮毂（就地绘制）"""
    d = ImageDraw.Draw(img)
    for wx in WHEEL_X:
        x, y = P(wx, WHEEL_Y)
        r = WHEEL_R * ZOOM * U
        d.ellipse([x - r, y - r, x + r, y + r], fill=TIRE)
        rs = WHEEL_R * 0.88 * ZOOM * U
        d.ellipse([x - rs, y - rs, x + rs, y + rs], fill=(38, 52, 78, 255))
        r2 = WHEEL_R * 0.70 * ZOOM * U
        d.ellipse([x - r2, y - r2, x + r2, y + r2], fill=(198, 212, 234, 255))
        for i in range(5):
            a = math.radians(-90 + i * 72)
            d.line([(x + r2 * 0.24 * math.cos(a), y + r2 * 0.24 * math.sin(a)),
                    (x + r2 * 0.92 * math.cos(a), y + r2 * 0.92 * math.sin(a))],
                   fill=(36, 51, 78, 255), width=max(1, int(11 * U)))
        r3 = WHEEL_R * 0.20 * ZOOM * U
        d.ellipse([x - r3, y - r3, x + r3, y + r3], fill=(198, 212, 234, 255))
        r4 = WHEEL_R * 0.09 * ZOOM * U
        d.ellipse([x - r4, y - r4, x + r4, y + r4], fill=(36, 51, 78, 255))


def build_icon(size=SIZE, rounded=True):
    """圆角方块图标。rounded=False 时铺满整个方形（iOS 图标要求，系统自己切圆角）"""
    base = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    mask = rounded_rect_mask(Canvas, 0.225) if rounded else Image.new("L", (Canvas, Canvas), 255)

    # 底：竖向渐变 + 左上高光 + 右下压暗
    base.paste(vertical_gradient(Canvas, BG_TOP, BG_BOT).convert("RGBA"), (0, 0), mask)
    empty = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    for cx, cy, r, col, a in ((0.30, 0.10, 0.95, (130, 196, 255), 0.40),
                              (0.86, 0.94, 0.75, (2, 18, 66), 0.45)):
        base = Image.alpha_composite(base, Image.composite(radial_glow(Canvas, cx, cy, r, col, a), empty, mask))

    # 底部压一层"地面"，画面才有上下的空间分层
    ground = band_shade(688, 1010, (2, 14, 46), 118, 1.25)
    ground.putalpha(ImageChops.multiply(ground.split()[3], mask))
    base = Image.alpha_composite(base, ground)

    # 车辆落地柔影
    shadow = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [P(100, 598), P(900, 700)], fill=(2, 16, 52, 130))
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(9 * U)))

    # 车辆
    base = Image.alpha_composite(base, draw_car())
    draw_wheels(base)

    # 内描边高光，做出一点玻璃质感（仅圆角版；铺满版没有边缘，描了会出现一圈亮边）
    if rounded:
        d = ImageDraw.Draw(base)
        d.rounded_rectangle([0, 0, Canvas - 1, Canvas - 1], radius=int(Canvas * 0.225),
                            outline=(255, 255, 255, 46), width=max(1, int(6 * U)))

    return base.resize((size, size), Image.LANCZOS)


def build_foreground():
    """自适应图标的「前景层」：透明底、只有车本身，裁到包围盒"""
    layer = Image.new("RGBA", (Canvas, Canvas), (0, 0, 0, 0))
    layer = Image.alpha_composite(layer, draw_car())
    draw_wheels(layer)
    icon = layer.resize((SIZE, SIZE), Image.LANCZOS)
    bbox = icon.split()[3].getbbox()
    return icon.crop(bbox) if bbox else icon


DENSITIES = [("mdpi", 1.0), ("hdpi", 1.5), ("xhdpi", 2.0), ("xxhdpi", 3.0), ("xxxhdpi", 4.0)]


def export_android(res_dir):
    """导出 Android 需要的两套图标：
       - mipmap-*/ic_launcher.png            传统图标（Android 7 及以下），48dp
       - mipmap-*/ic_launcher_foreground.png 自适应前景层（Android 8+），108dp 画布
    """
    icon = build_icon()
    fg = build_foreground()
    for name, mult in DENSITIES:
        d = os.path.join(res_dir, "mipmap-" + name)
        os.makedirs(d, exist_ok=True)

        size = int(round(48 * mult))
        legacy = icon.resize((size, size), Image.LANCZOS)
        legacy.save(os.path.join(d, "ic_launcher.png"))
        legacy.save(os.path.join(d, "ic_launcher_round.png"))

        fgsz = int(round(108 * mult))
        target_w = int(round(fgsz * 0.76))          # 车宽占 108dp 画布的 76%，圆形遮罩下不出血
        target_h = max(1, int(round(fg.height * target_w / fg.width)))
        car = fg.resize((target_w, target_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (fgsz, fgsz), (0, 0, 0, 0))
        canvas.paste(car, ((fgsz - target_w) // 2, (fgsz - target_h) // 2), car)
        canvas.save(os.path.join(d, "ic_launcher_foreground.png"))
    print("android icons ->", res_dir)


IOS_ICONS = [
    ("Icon-20@2x.png", 40, "20x20", "2x"),
    ("Icon-20@3x.png", 60, "20x20", "3x"),
    ("Icon-29@2x.png", 58, "29x29", "2x"),
    ("Icon-29@3x.png", 87, "29x29", "3x"),
    ("Icon-40@2x.png", 80, "40x40", "2x"),
    ("Icon-40@3x.png", 120, "40x40", "3x"),
    ("Icon-60@2x.png", 120, "60x60", "2x"),
    ("Icon-60@3x.png", 180, "60x60", "3x"),
    ("Icon-1024.png", 1024, "1024x1024", "1x"),
]


def export_ios(assets_dir):
    """导出 iOS 的 AppIcon 资源：
       - 全幅方形、无 alpha 通道（iOS 自己裁圆角，带透明会被 App Store 拒）
       - 只列 iPhone 尺寸，TARGETED_DEVICE_FAMILY=1
    """
    import json

    appicon = os.path.join(assets_dir, "AppIcon.appiconset")
    os.makedirs(appicon, exist_ok=True)

    master = build_icon(1024, rounded=False).convert("RGB")
    images = []
    for name, px, pt, scale in IOS_ICONS:
        master.resize((px, px), Image.LANCZOS).save(os.path.join(appicon, name), "PNG")
        images.append({
            "filename": name,
            "idiom": "ios-marketing" if px == 1024 else "iphone",
            "scale": scale,
            "size": pt,
        })
    with open(os.path.join(appicon, "Contents.json"), "w", encoding="utf-8") as f:
        json.dump({"images": images, "info": {"author": "xcode", "version": 1}},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(assets_dir, "Contents.json"), "w", encoding="utf-8") as f:
        json.dump({"info": {"author": "xcode", "version": 1}}, f, indent=2)
    print("ios icons ->", appicon)


def main():
    icon = build_icon()
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "app.ico")
    icon.save(out, format="ICO",
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (40, 40), (32, 32), (24, 24), (16, 16)])
    icon.save(os.path.join(here, "app.png"))
    print("icon ->", out, os.path.getsize(out), "bytes")

    # 顺带导出 Android 工程用的图标
    android_res = os.path.join(here, "..", "android", "app", "res")
    if os.path.isdir(os.path.join(here, "..", "android", "app")):
        export_android(os.path.normpath(android_res))

    # 顺带导出 iOS 工程用的图标
    ios_assets = os.path.join(here, "..", "ios", "Resources", "Assets.xcassets")
    if os.path.isdir(os.path.join(here, "..", "ios")):
        export_ios(os.path.normpath(ios_assets))


if __name__ == "__main__":
    main()
