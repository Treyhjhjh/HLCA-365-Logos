#!/usr/bin/env python3
"""Rebrand all 261 HLCA fictional teams using real-school color palettes.
A retro athletics redesign made from source mascot art, with safe transparent
margins. The old logo set is backed up by the accompanying workflow.
"""
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from pathlib import Path
import csv, hashlib, math, random

F="/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
S=3
WH=256

def rgb(s):
    s=s.strip().lstrip("#")
    try: return tuple(int(s[i:i+2],16) for i in (0,2,4))
    except: return (37,49,75)
def mix(a,b,x): return tuple(round(a[i]*(1-x)+b[i]*x) for i in range(3))
def rgba(c):return (*c,255)
def lum(c):return sum(x*y for x,y in zip(c,(.21,.72,.07)))
def f(size):return ImageFont.truetype(F,max(6,round(size*S)))
def seed(t):return int(hashlib.sha256((t["ncaa_school"]+t["hlca_name"]).encode()).hexdigest()[:10],16)
def star(d,x,y,r,c):
    pts=[]
    for k in range(10):
        th=-math.pi/2+k*math.pi/5
        rd=r if k%2==0 else r*.43
        pts.append((round(S*(x+rd*math.cos(th))),round(S*(y+rd*math.sin(th)))))
    d.polygon(pts,fill=rgba(c))
def txt(canvas,word,y,size,fg,inside,outside,maxw=223):
    d=ImageDraw.Draw(canvas);ff=f(size)
    while d.textbbox((0,0),word,font=ff,stroke_width=4*S)[2]>maxw*S and size>8:
        size-=.7;ff=f(size)
    bb=d.textbbox((0,0),word,font=ff)
    x=(256*S-(bb[2]-bb[0]))//2
    yy=round(y*S)
    d.text((x,yy),word,font=ff,fill=rgba(fg),stroke_width=4*S,stroke_fill=rgba(outside))
    d.text((x,yy),word,font=ff,fill=rgba(fg),stroke_width=2*S,stroke_fill=rgba(inside))
def school_letters(school):
    special={"Alabama A&M":"AM","Abilene Christian":"AC","Alabama State":"AS","Alcorn State":"AS",
             "BYU":"BY","Boston University":"BU","Michigan":"M","Indiana":"IU",
             "Clemson":"C","Cal Poly":"CP","Penn State":"PS","UAB":"UAB",
             "UTEP":"UTEP","UTSA":"UTSA","Notre Dame":"ND"}
    if school in special:return special[school]
    words=[s for s in school.upper().replace("-"," ").replace("&"," ").split() if s not in ("OF","THE","AND","STATE","UNIVERSITY","AT")]
    return ("".join(x[0] for x in words) or "HL")[:3]
def make_one(t,src_path,out_path):
    primary=rgb(t["team_primary"]);second=rgb(t["team_secondary"])
    if lum(primary)>218:primary=(44,55,73)
    accent=second if abs(lum(second)-lum(primary))>32 and lum(second)<240 else (232,168,75)
    ink=mix(primary,(9,16,27),.75);cream=(248,241,218)
    original=Image.open(src_path).convert("RGBA")
    bb=original.getchannel("A").getbbox()
    if not bb:raise ValueError("Empty source mascot")
    art=original.crop(bb)
    art=ImageEnhance.Contrast(art).enhance(1.12)
    canvas=Image.new("RGBA",(WH*S,WH*S),(0,0,0,0))
    d=ImageDraw.Draw(canvas)
    rng=random.Random(seed(t));v=seed(t)%8
    # 1970s-90s university athletic accent shapes. Never circular containers.
    if v in (0,2,4,6):
        for i in range(3):
            c=accent if i%2==0 else primary
            d.line([(20*S,(50+11*i)*S),(86*S,(26+11*i)*S)],fill=rgba(c),width=3*S)
            d.line([(180*S,(172+11*i)*S),(235*S,(153+11*i)*S)],fill=rgba(c),width=3*S)
    else:
        for i in range(4):
            x=20+14*i
            d.polygon([(x*S,84*S),((x+15)*S,43*S),((x+21)*S,43*S),((x+6)*S,84*S)],fill=rgba(accent if i%2==0 else primary))
        star(d,225,170,6,accent)
    # Semi-transparent school-inspired collegiate monogram behind the mascot.
    monogram=school_letters(t["ncaa_school"])
    back=Image.new("RGBA",canvas.size,(0,0,0,0));bd=ImageDraw.Draw(back)
    mf=f(78 if len(monogram)<3 else 52)
    bx=bd.textbbox((0,0),monogram,font=mf)
    bd.text(((256*S-(bx[2]-bx[0]))//2,60*S),monogram,font=mf,
            fill=(*mix(primary,cream,.58),100),stroke_width=2*S,stroke_fill=(*primary,125))
    canvas.alpha_composite(back)
    # Major full-sized retro mascot head. Original source retained only as raw art;
    # composition, wordmark, varsity letters and ink contours are newly designed.
    pad=15*S
    limit=(199*S,138*S)
    scale=min(limit[0]/art.width,limit[1]/art.height)
    art=art.resize((max(1,round(art.width*scale)),max(1,round(art.height*scale))),
                   Image.Resampling.NEAREST if scale>1 else Image.Resampling.LANCZOS)
    mask=art.getchannel("A")
    grow=max(3,7)
    a1=mask.filter(ImageFilter.MaxFilter(grow))
    a2=mask.filter(ImageFilter.MaxFilter(3))
    border=Image.new("RGBA",art.size,rgba(ink));border.putalpha(a1)
    keyline=Image.new("RGBA",art.size,rgba(cream));keyline.putalpha(a2)
    emblem=Image.new("RGBA",art.size,(0,0,0,0))
    emblem.alpha_composite(border);emblem.alpha_composite(keyline);emblem.alpha_composite(art)
    x=round(128*S-emblem.width/2)
    y=round(124*S-emblem.height/2)
    canvas.alpha_composite(emblem,(x,y))
    city=t["hlca_city"].upper()
    txt(canvas,city,9,16 if len(city)<13 else 13,cream,primary,ink,maxw=220)
    names=t["hlca_name"].upper().split()
    if len(names)==1:
        txt(canvas,names[0],205,34,cream,primary,ink)
    elif len(names)==2:
        txt(canvas,names[0],194,29,cream,primary,ink)
        txt(canvas,names[1],218,29,cream,primary,ink)
    else:
        txt(canvas," ".join(names[:-1]),194,22,cream,primary,ink)
        txt(canvas,names[-1],218,27,cream,primary,ink)
    d=ImageDraw.Draw(canvas)
    d.line([(23*S,247*S),(96*S,247*S)],fill=rgba(primary),width=2*S)
    d.line([(163*S,247*S),(233*S,247*S)],fill=rgba(accent),width=2*S)
    canvas=canvas.resize((256,256),Image.Resampling.LANCZOS)
    bb=canvas.getchannel("A").getbbox()
    if not bb:raise ValueError("No rendered alpha")
    crop=canvas.crop(bb)
    if crop.width>232 or crop.height>232:
        k=min(232/crop.width,232/crop.height)
        crop=crop.resize((round(crop.width*k),round(crop.height*k)),Image.Resampling.LANCZOS)
    final=Image.new("RGBA",(256,256),(0,0,0,0))
    final.alpha_composite(crop,((256-crop.width)//2,(256-crop.height)//2))
    box=final.getchannel("A").getbbox()
    if min(box[0],box[1],256-box[2],256-box[3])<11:
        raise ValueError("Unsafe image edge")
    final.save(out_path,optimize=True)

def main():
    teams=list(csv.DictReader(open("data/hlca_retro_261_teams.csv",encoding="utf-8")))
    if len(teams)!=261:raise ValueError("Expected 261 teams")
    inp=Path("logos");out=Path("retro_output")
    out.mkdir(exist_ok=True)
    count=0
    for t in teams:
        name=t["court_filename"]
        if not (inp/name).is_file():raise FileNotFoundError(name)
        make_one(t,inp/name,out/name);count+=1
    if len(list(out.glob("*.png")))!=261:raise RuntimeError("Missing outputs")
    print("RETRO_REBRAND_COMPLETE",count)
if __name__=="__main__":main()
