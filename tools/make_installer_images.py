"""Creates the Windows installer images (Inno Setup) from installer/KatieCAD_Setup_Banner.png.

Run:  python tools/make_installer_images.py
Writes installer/wizard_large_<w>.bmp (welcome / finish page, tall) and
installer/wizard_small_<w>.bmp (header image of the inner pages) in several sizes for
the Windows scaling steps 100 % ... 250 %. The generated .bmp files are committed.
"""
import os
from PIL import Image, ImageDraw

HIER = os.path.dirname(os.path.abspath(__file__))
INST = os.path.join(os.path.dirname(HIER), "installer")
QUELLE = os.path.join(INST, "KatieCAD_Setup_Banner.png")

GROSS = [(164, 314), (192, 386), (246, 459), (328, 604), (410, 797)]
KLEIN = [(55, 55), (64, 68), (83, 80), (110, 106), (138, 140)]


def hintergrund(banner):
    return banner.getpixel((1000, 8))[:3]


def gross(banner, w, h):
    bg = hintergrund(banner)
    f = w / 164.0
    bild = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(bild)
    maskottchen = banner.crop((0, 0, 440, 450)).convert("RGB")
    mw = int(150 * f)
    maskottchen = maskottchen.resize((mw, int(mw * 450 / 440)), Image.LANCZOS)
    bild.paste(maskottchen, ((w - mw) // 2, int(34 * f)))
    schrift = banner.crop((440, 110, 1900, 350)).convert("RGB")
    sw = int(146 * f)
    schrift = schrift.resize((sw, int(sw * 240 / 1460)), Image.LANCZOS)
    y_s = int(34 * f) + int(mw * 450 / 440) + int(22 * f)
    bild.paste(schrift, ((w - sw) // 2, y_s))
    d.line([(int(22 * f), y_s + schrift.size[1] + int(14 * f)),
            (w - int(22 * f), y_s + schrift.size[1] + int(14 * f))],
           fill=(186, 130, 255), width=max(1, int(round(f))))
    return bild


def klein(banner, w, h):
    bg = hintergrund(banner)
    bild = Image.new("RGB", (w, h), bg)
    m = banner.crop((0, 10, 440, 450)).convert("RGB")
    s = min(w / 440.0, h / 440.0) * 0.96
    m = m.resize((int(440 * s), int(440 * s)), Image.LANCZOS)
    bild.paste(m, ((w - m.size[0]) // 2, (h - m.size[1]) // 2))
    return bild


def main():
    banner = Image.open(QUELLE).convert("RGBA")
    flach = Image.new("RGBA", banner.size, hintergrund(banner) + (255,))
    flach.alpha_composite(banner)
    banner = flach
    for w, h in GROSS:
        gross(banner, w, h).save(os.path.join(INST, f"wizard_large_{w}.bmp"), "BMP")
    for w, h in KLEIN:
        klein(banner, w, h).save(os.path.join(INST, f"wizard_small_{w}.bmp"), "BMP")
    print("Installer images written to", INST)


if __name__ == "__main__":
    main()
