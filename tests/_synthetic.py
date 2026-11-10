"""Synthetic logos and ad scenes used by the logo tests. Generated in code: no binary fixtures, no network."""
import io, base64, random, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
F=lambda s: ImageFont.load_default(size=s)
def logo_nova(w=300,h=300,bg="white",hue=None):
    im=Image.new("RGB",(w,h),bg); d=ImageDraw.Draw(im)
    c1,c2=("#1f4fd8","#ff7a00") if hue is None else hue
    d.ellipse((20,20,w-20,h-20),fill=c1)
    d.polygon([(w//2,50),(w//2+30,w//2-10),(w-60,w//2-5),(w//2+45,w//2+30),(w//2+60,h-80),(w//2,w//2+60),(w//2-60,h-80),(w//2-45,w//2+30),(60,w//2-5),(w//2-30,w//2-10)],fill=c2)
    d.text((w//2-70,h-85),"NOVA",fill="white",font=F(54)); return im
def logo_zeta(w=300,h=300):
    im=Image.new("RGB",(w,h),"white"); d=ImageDraw.Draw(im)
    d.rectangle((15,15,w-15,h-15),fill="#0a8f4d"); d.polygon([(40,260),(150,40),(260,260)],fill="#ffe14d"); d.line((60,100,240,100,60,230,240,230),fill="black",width=14)
    d.text((95,125),"ZETA",fill="#0a3d20",font=F(52)); return im
def logo_flat(w=300,h=300):
    im=Image.new("RGB",(w,h),"white"); d=ImageDraw.Draw(im); d.rectangle((10,10,w-10,h-10),fill="#d00000"); d.ellipse((90,90,210,210),fill="white"); return im
def ad_bg(w=1200,h=700,seed=0):
    r=random.Random(seed); im=Image.new("RGB",(w,h),"#e9eef7"); d=ImageDraw.Draw(im)
    for i in range(h): d.line((0,i,w,i),fill=(230-i//12,236-i//14,250-i//20))
    for _ in range(25):
        x,y=r.randint(0,w),r.randint(0,h); s=r.randint(30,140); col=tuple(r.randint(90,230) for _ in range(3))
        (d.ellipse if r.random()<.5 else d.rectangle)((x,y,x+s,y+s),fill=col)
    d.text((60,60),"SUMMER SALE 80% OFF",fill="black",font=F(64)); d.text((60,150),"shop at nova-deals.xyz",fill="#222",font=F(40)); return im
def place(bg,logo,scale,pos,rot=0,blur=0,jpeg=None,noise=0):
    bg=bg.copy(); lg=logo.resize((int(logo.width*scale),int(logo.height*scale)),Image.LANCZOS)
    if rot: lg=lg.rotate(rot,expand=True,fillcolor="white")
    bg.paste(lg,pos)
    if blur: bg=bg.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        a=np.array(bg).astype(np.int16)+np.random.RandomState(1).normal(0,noise,(bg.height,bg.width,3)).astype(np.int16); bg=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    b=io.BytesIO()
    if jpeg: bg.save(b,"JPEG",quality=jpeg)
    else: bg.save(b,"PNG")
    return b.getvalue()
def ref_entry(im,id,name):
    b=io.BytesIO(); im.save(b,"PNG"); return {"id":id,"name":name,"png_b64":base64.b64encode(b.getvalue()).decode()}
