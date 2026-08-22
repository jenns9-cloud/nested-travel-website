"""Measures hero text contrast against the actual hero photograph.

Text over a photograph is the one place WCAG contrast cannot be reasoned about
from the palette alone — it depends on the pixels. This samples the brightest
2% of pixels behind each text element, composites the page's scrim exactly as
CSS does, and reports the resulting ratio. Re-run it whenever the hero image
changes; an image swap can silently break AA.
"""
from PIL import Image
import sys, os

def srgb(c):
    c=c/255; return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def lum(r,g,b): return 0.2126*srgb(r)+0.7152*srgb(g)+0.0722*srgb(b)
def lum_hex(h):
    h=h.lstrip('#'); return lum(*(int(h[i:i+2],16) for i in (0,2,4)))
def contrast(a,b):
    hi,lo=max(a,b),min(a,b); return (hi+0.05)/(lo+0.05)

im=Image.open('assets/hero-1600.jpg').convert('RGB'); px=im.load(); IW,IH=im.size
VW,VH=1512,805; scale=VW/IW; rh=IH*scale; top=(rh-VH)*0.52

INK=lum_hex('#2D2D2D'); INKS=lum_hex('#595959'); PAPER=lum_hex('#F7F4F1'); BD=lum_hex('#8F6363')
DARK=(24,18,16); VEIL=(250,246,242)

def dark_alpha(t):
    if t<=0.30: return 0.30+(0.04-0.30)*(t/0.30)
    return 0.04+(0.26-0.04)*((t-0.30)/0.70)

# Copy block spans roughly the middle of the hero; the scrim is strongest at its centre.
COPY_TOP, COPY_BOT = 250, 640
def veil_alpha(y):
    cy=(COPY_TOP+COPY_BOT)/2; half=(COPY_BOT-COPY_TOP)/2
    d=abs(y-cy)/half
    if d<=0.46: return 0.93-(0.93-0.86)*(d/0.46)
    if d<=0.72: return 0.86-(0.86-0.55)*((d-0.46)/0.26)
    if d<=0.92: return 0.55*(1-(d-0.72)/0.20)
    return 0.0

rows=[('eyebrow',292,310,660,850,INK,4.5),
      ('wordmark',330,388,500,1010,INK,3.0),
      ('slogan',440,482,520,1000,INK,3.0),
      ('lede line 1',506,528,570,940,INKS,4.5),
      ('lede line 2',530,552,605,905,INKS,4.5),
      ('App Store label (solid)',None,None,None,None,PAPER,4.5),
      ('Google Play label (solid)',None,None,None,None,INK,4.5)]

print(f"{'element':28} {'ratio':>8}  need  verdict")
print('-'*56)
fails=0
for l,y0,y1,x0,x1,Lt,need in rows:
    if y0 is None:
        c = contrast(Lt, lum_hex('#8F6363')) if l.startswith('App') else contrast(Lt, PAPER)
        note=' (solid fill, image-independent)'
    else:
        sy0=max(0,int((y0+top)/scale)); sy1=min(IH,max(sy0+1,int((y1+top)/scale)))
        sx0=max(0,int(x0/scale));       sx1=min(IW,max(sx0+1,int(x1/scale)))
        Ls=[]
        for y in range(sy0,sy1):
            vy=y*scale-top; da=dark_alpha(min(max((y*scale)/rh,0),1)); va=veil_alpha(vy)
            for x in range(sx0,sx1):
                r,g,b=px[x,y]
                r=da*DARK[0]+(1-da)*r; g=da*DARK[1]+(1-da)*g; b=da*DARK[2]+(1-da)*b
                r=va*VEIL[0]+(1-va)*r; g=va*VEIL[1]+(1-va)*g; b=va*VEIL[2]+(1-va)*b
                Ls.append(lum(r,g,b))
        Ls.sort()
        c=contrast(Lt, Ls[int(len(Ls)*0.98)-1]); note=''
    ok=c>=need
    if not ok: fails+=1
    print(f"{l:28} {c:6.2f}:1  {need}   {'PASS' if ok else '*** FAIL ***'}{note}")
print('-'*56)
print(f"{fails} failing element(s)")
sys.exit(1 if fails else 0)
