"""Measures hero text contrast against the actual hero photograph.

Text over a photograph is the one place WCAG contrast cannot be reasoned about
from the palette alone — it depends on the pixels. This reproduces the hero's
real compositing stack (photo frame -> scrim gradient -> text), samples the
BRIGHTEST 2% of pixels behind each element (the worst case for light text) and
reports the resulting ratio. Re-run it whenever the hero image, the crop, or the
scrim changes; any of the three can silently break AA.

Geometry and colours below mirror index.html exactly. If you change the hero
there, change it here too.
"""
from PIL import Image
import sys

# ── viewport / hero geometry (index.html: .hero, .hero::before) ──────────────
VW, VH   = 1512, 744          # laptop viewport: the tightest common case
HERO_H   = VH                 # .hero { min-height: 100svh }
FRAME_T  = -0.22 * HERO_H     # .hero::before { top: -22% }
FRAME_H  =  1.22 * HERO_H     # .hero::before { height: 122% }
BG_POS_Y =  0.55              # background-position: center 55%
IMG      = 'assets/hero-1600.jpg'

# ── the scrim (index.html: .hero::after) ────────────────────────────────────
SCRIM_RGB = (13, 24, 38)
STOPS = [(0.00,0.58),(0.09,0.24),(0.24,0.02),(0.33,0.00),
         (0.43,0.34),(0.55,0.66),(0.72,0.82),(1.00,0.88)]

def scrim_alpha(t):
    t = min(max(t, 0.0), 1.0)
    for (t0,a0),(t1,a1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            return a0 if t1 == t0 else a0 + (a1-a0)*((t-t0)/(t1-t0))
    return STOPS[-1][1]

# ── colour maths ────────────────────────────────────────────────────────────
def srgb(c):
    c = c/255
    return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
def lum(r,g,b): return 0.2126*srgb(r)+0.7152*srgb(g)+0.0722*srgb(b)
def lum_hex(h):
    h = h.lstrip('#'); return lum(*(int(h[i:i+2],16) for i in (0,2,4)))
def contrast(a,b):
    hi,lo = max(a,b),min(a,b); return (hi+0.05)/(lo+0.05)

PAPER, INK, BLUSH = lum_hex('#F7F4F1'), lum_hex('#2D2D2D'), lum_hex('#8F6363')

# ── map hero-space (x,y) -> source-image pixel, as `cover` does ─────────────
im = Image.open(IMG).convert('RGB'); px = im.load(); IW, IH = im.size
s  = max(VW/IW, FRAME_H/IH)
off_x = (IW*s - VW)/2
off_y = (IH*s - FRAME_H)*BG_POS_Y

def sample_rgb(x, y):
    """Composite the photo + hero scrim at hero-space (x,y); return RGB."""
    sx = int((x + off_x)/s); sy = int((y - FRAME_T + off_y)/s)
    sx = min(max(sx,0), IW-1); sy = min(max(sy,0), IH-1)
    r,g,b = px[sx,sy]
    a = scrim_alpha(y/HERO_H)
    return (a*SCRIM_RGB[0]+(1-a)*r, a*SCRIM_RGB[1]+(1-a)*g, a*SCRIM_RGB[2]+(1-a)*b)

def sample(x, y):
    return lum(*sample_rgb(x, y))

# ── the elements, as measured from the rendered page at 1512x744 ───────────
#    name,                    top, bot, left, right, colour,    AA threshold
ROWS = [
 ('eyebrow',                   328, 347,  667,  850, '#FFFFFF', 4.5),
 ('wordmark (large)',          365, 433,  418, 1108, '#FFFCFA', 3.0),
 ('slogan (large)',            472, 524,  426, 1086, '#FFFCFA', 3.0),
 ('lede line 1',               542, 563,  536,  976, '#EBE0DC', 4.5),
 ('lede line 2',               572, 592,  511, 1001, '#EBE0DC', 4.5),
 ('App Store label (solid)',  None,None, None, None, '#F7F4F1', 4.5),
 ('Google Play label (solid)',None,None, None, None, '#2D2D2D', 4.5),
]

# The scrolled header swaps to a paper bar. Its mark and CTA must swap with it —
# they shipped white-on-paper (invisible) until 2026-08-22. Image-independent.
def over_paper(rgb, a):
    return lum(*(a*rgb[i] + (1-a)*(247,244,241)[i] for i in range(3)))

# The bar now stays clear for the WHOLE hero, so the worst background for the
# white mark is not the top of the photo — it is whatever passes under the bar
# as you scroll (the bright horizon band). Sweep the scroll range and take the
# worst case. The header goes to paper at heroH - headerH.
HEADER_H = 78
HEADER_STOPS = [(0.00,0.68),(0.60,0.58),(0.85,0.28),(1.00,0.00)]

def header_alpha(y):
    t = min(max(y/HEADER_H, 0.0), 1.0)
    for (t0,a0),(t1,a1) in zip(HEADER_STOPS, HEADER_STOPS[1:]):
        if t <= t1:
            return a0 if t1 == t0 else a0 + (a1-a0)*((t-t0)/(t1-t0))
    return HEADER_STOPS[-1][1]
SWEEP = [('header mark (scrolling)',   27, 50,   32,  203, '#FFFCFA', 4.5),
         ('header CTA (scrolling)',    20, 58, 1358, 1480, '#FFFCFA', 4.5)]

def worst_over_scroll(y0, y1, x0, x1):
    worst, at = 0.0, 0
    for sy in range(0, int(HERO_H - HEADER_H) + 1, 8):
        Ls = []
        for y in range(y0, y1, 2):
            ha = header_alpha(y)
            for x in range(x0, x1, 3):
                r,g,b = sample_rgb(x, y+sy)
                Ls.append(lum(ha*SCRIM_RGB[0]+(1-ha)*r,
                              ha*SCRIM_RGB[1]+(1-ha)*g,
                              ha*SCRIM_RGB[2]+(1-ha)*b))
        Ls.sort()
        L = Ls[int(len(Ls)*0.98)-1]
        if L > worst: worst, at = L, sy
    return worst, at

HEADER = [
 ('scrolled mark',        lum_hex('#2D2D2D'), PAPER,                       4.5),
 ('scrolled CTA label',   lum_hex('#2D2D2D'), PAPER,                       4.5),
 ('scrolled CTA border',  PAPER,              over_paper((45,45,45),0.55), 3.0),  # non-text, 1.4.11
]

print(f"hero {VW}x{HERO_H}   photo frame top {FRAME_T:.0f}px height {FRAME_H:.0f}px")
print(f"{'element':28} {'ratio':>8}  need  verdict")
print('-'*60)
fails = 0
for name, y0, y1, x0, x1, hexc, need in ROWS:
    Lt = lum_hex(hexc)
    if y0 is None:                       # solid button fills: image-independent
        c = contrast(Lt, BLUSH if name.startswith('App') else PAPER)
        note = '  (solid fill)'
    else:
        Ls = sorted(sample(x,y) for y in range(y0,y1) for x in range(x0,x1,2))
        c  = contrast(Lt, Ls[int(len(Ls)*0.98)-1])   # brightest 2% = worst case
        note = ''
    ok = c >= need
    fails += not ok
    print(f"{name:28} {c:6.2f}:1  {need}   {'PASS' if ok else '*** FAIL ***'}{note}")
for name, y0, y1, x0, x1, hexc, need in SWEEP:
    L, at = worst_over_scroll(y0, y1, x0, x1)
    c = contrast(lum_hex(hexc), L); ok = c >= need; fails += not ok
    print(f"{name:28} {c:6.2f}:1  {need}   {'PASS' if ok else '*** FAIL ***'}  (worst at scrollY {at})")
for name, La, Lb, need in HEADER:
    c = contrast(La, Lb); ok = c >= need; fails += not ok
    print(f"{name:28} {c:6.2f}:1  {need}   {'PASS' if ok else '*** FAIL ***'}  (paper bar)")
print('-'*60)
print(f"{fails} failing element(s)")
sys.exit(1 if fails else 0)
