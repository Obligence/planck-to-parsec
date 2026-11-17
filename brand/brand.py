import math, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
POP="/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
POPM="/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
import os
if not os.path.exists(POPM): POPM=POP
S=2
WHITE,CYAN,GOLD=(255,255,255),(110,225,255),(255,196,92)
def bg(w,h,nstars,seed):
    rng=np.random.default_rng(seed)
    y=np.linspace(0,1,h)[:,None,None]
    col=np.array([10,15,38])*(1-y)+np.array([2,3,10])*y
    img=Image.fromarray(np.repeat(col,w,axis=1).astype(np.uint8),"RGB")
    d=ImageDraw.Draw(img)
    for _ in range(nstars):
        x,yy=int(rng.integers(0,w)),int(rng.integers(0,h)); b=int(rng.integers(70,230)); r=int(rng.choice([1,1,2,2,3]))
        d.ellipse([x-r,yy-r,x+r,yy+r],fill=(b,b,b))
    return img
def a(c,al): return (c[0],c[1],c[2],int(255*max(0,min(1,al))))
def circ(d,x,y,r,fill=None,outline=None,width=1):
    d.ellipse([(x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S],fill=fill,outline=outline,width=max(1,int(width*S)))
def mark(d,x,y,k):
    for r,al,w in ((95,.95,13),(150,.7,10),(215,.45,8),(290,.28,6)):
        circ(d,x,y,r*k,outline=a(CYAN,al),width=w*k)
    for m,al in ((1.75,.12),(1.5,.22),(1.3,.35)):
        circ(d,x,y,52*k*m,outline=a((255,150,70),al),width=8*k)
    circ(d,x,y,58*k,fill=(0,0,0,255),outline=a((255,196,110),1),width=9*k)
    circ(d,x,y,48*k,fill=(0,0,0,255))
def finish(img,w,h,glow=.6):
    small=img.reduce(8).filter(ImageFilter.GaussianBlur(5)).resize((w,h),Image.BILINEAR)
    return ImageChops.add(img.reduce(2),small.point(lambda v:int(v*glow)))
# profile 800x800
w=h=800
img=bg(w*S,h*S,160,3); d=ImageDraw.Draw(img,"RGBA"); mark(d,400,400,1.0)
finish(img,w,h).save("profile_picture.png")
# banner 2560x1440
w,h=2560,1440
img=bg(w*S,h*S,900,5); d=ImageDraw.Draw(img,"RGBA")
mx,my=640,720
for arm in (0,1):   # faint spiral across the whole banner
    pts=[]
    for i in range(0,900):
        rho=150+i*2.6; ang=rho/190.0+arm*math.pi
        pts.append(((mx+rho*math.cos(ang))*S,(my+rho*math.sin(ang))*S))
    for i in range(0,len(pts)-12,10):
        rho=150+i*2.6
        d.line(pts[i:i+12],fill=a(CYAN,0.26*(1-rho/2600)),width=int(5*S),joint="curve")
mark(d,mx,my,0.62)
out=finish(img,w,h,.55); t=ImageDraw.Draw(out)
f=ImageFont.truetype(POP,112); x=860; yy=672
for word,colr in (("PLANCK",WHITE),("TO",GOLD),("PARSEC",WHITE)):
    t.text((x,yy),word,font=f,fill=colr,anchor="lm",stroke_width=6,stroke_fill=(3,5,14))
    x+=f.getlength(word)+34
print("title right edge",x)
t.text((864,790),"The universe, one astonishing fact at a time.",font=ImageFont.truetype(POPM,46),fill=(190,215,240),anchor="lm",stroke_width=4,stroke_fill=(3,5,14))
out.save("channel_banner.png")
# preview with safe area + circle crop
pv=out.copy(); ImageDraw.Draw(pv).rectangle([507,508,2053,931],outline=(255,0,0),width=4); pv.resize((1280,720)).save("pv_banner.jpg")
p=Image.open("profile_picture.png"); m=Image.new("L",(800,800),0); ImageDraw.Draw(m).ellipse([0,0,799,799],fill=255)
c=Image.new("RGB",(800,800),(255,255,255)); c.paste(p,(0,0),m); c.resize((400,400)).save("pv_profile.jpg")
