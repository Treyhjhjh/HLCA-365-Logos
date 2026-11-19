#!/usr/bin/env python3
"""Build 261 original/fan-reference-derived Hoop Land 1024x512 court overlays.

Reference-source preservation: found community work is used as the starting
court floor, rebranded to the fictional HLCA teams; any unmatched school gets an
original 1024x512 pixel court. Does not create or change user player data.
"""
import argparse
import csv
import io
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urljoin

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = Path(__file__).resolve().parent
SCHOOL_CSV = ROOT / 'court_teams.csv'
OUT = ROOT / 'courts'
REPO = 'Treyhjhjh/HLCA-365-Logos'
LOCAL_LOGOS = Path('/mnt/data/HLCA_365_NEW_TEAM_LOGOS')
SOURCE_ROOT = 'https://sites.google.com/view/hooplandcourts/ncaa'
SCHOOL_SITE = 'https://sites.google.com/view/hooplandcourts/ncaa/conference-usa'
BASE_CSS = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT = BASE_CSS if os.path.exists(BASE_CSS) else '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

# Matching names used by the school-specific public art galleries and by our NCAA
# mapping. This does NOT mean rights to the original art were transferred.
ALIASES = {
    'Cal Baptist':['California Baptist','CBU','Cal Baptist'],
    'Bakersfield':['Cal State Bakersfield','CSU Bakersfield','CSUB'],
    'Albany':['UAlbany','Albany'],
    'FIU':['Florida International','FIU'],
    'ETSU':['East Tennessee State','ETSU'],
    'FDU':['Fairleigh Dickinson','FDU'],
    'Purdue Fort Wayne':['Fort Wayne','Purdue Fort Wayne'],
    'Middle Tennessee':['Middle Tennessee State','MTSU'],
    'Northern Kentucky':['NKU','Northern Kentucky'],
    'UT Martin':['Tennessee Martin','UT Martin'],
    'UT Arlington':['Texas Arlington','UT Arlington'],
    'UTRGV':['Rio Grande Valley','UTRGV'],
    'USC Upstate':['South Carolina Upstate','USC Upstate'],
    'UCSB':['UC Santa Barbara','Santa Barbara'],
    'Southeast Missouri State':['SEMO','Southeast Missouri'],
    'Arkansas-Pine Bluff':['UAPB','Arkansas Pine Bluff'],
    'Alcorn State':['Alcorn State','Al Corn State'],
    'Louisiana Tech':['La Tech','Louisiana Tech'],
    'A&M-Corpus Christi':['Texas A&M-Corpus Christi','TAMU-CC','Corpus Christi'],
    'Houston Christian':['Houston Baptist','Houston Christian'],
    'East Texas A&M':['Texas A&M Commerce','East Texas A&M','A&M-Commerce'],
    'Gardner-Webb':['Gardner-Webb'],
    'New Haven':['New Haven'],
}

def normalize(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode('ascii')
    return ''.join(ch for ch in s.lower() if ch.isalnum())

def color(hex6, fallback='#243c52'):
    try:
        if len(hex6)==6:return '#'+hex6
    except Exception:pass
    return fallback

def rgba(hex6, alpha=255):
    s=color(hex6).lstrip('#')
    return (int(s[:2],16),int(s[2:4],16),int(s[4:],16),alpha)

def mix(a,b,k):
    A=rgba(a)[:3] if isinstance(a,str) else a[:3]
    B=rgba(b)[:3] if isinstance(b,str) else b[:3]
    return (*tuple(max(0,min(255,round(A[i]*(1-k)+B[i]*k))) for i in range(3)),255)

def txtfit(draw, text, maxwidth, initial=20, minimum=9):
    for n in range(initial,minimum-1,-1):
        ft=ImageFont.truetype(FONT,n)
        if draw.textbbox((0,0),text,font=ft)[2] <= maxwidth:return ft
    return ImageFont.truetype(FONT,minimum)

def vtext(img, text, mid, invert=False, fill='white', maxheight=310):
    text=text.upper();big=Image.new('RGBA',(390,45),(0,0,0,0));d=ImageDraw.Draw(big)
    ft=txtfit(d,text,maxheight,initial=26,minimum=12)
    bb=d.textbbox((0,0),text,font=ft,stroke_width=0)
    x=max(0,(390-(bb[2]-bb[0]))//2)
    d.text((x,5),text,font=ft,fill=fill,stroke_width=0)
    rotated=big.rotate(270 if invert else 90,expand=True)
    alpha=rotated.getchannel('A')
    crop=rotated.getbbox()
    if crop:rotated=rotated.crop(crop)
    img.alpha_composite(rotated,(mid[0]-rotated.width//2, mid[1]-rotated.height//2))

def safe_logo(team, local=False, sess=None):
    name=team['court_filename']
    if local:
        p=LOCAL_LOGOS/name
        if p.exists():return Image.open(p).convert('RGBA')
        return None
    if sess is not None:
        try:
            r=sess.get(team['logo_url'],timeout=20);r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert('RGBA')
        except Exception as e: print('Logo download failed',name,str(e)[:120])
    return None

def paste_logo(img,logo,x,y,w,h):
    if logo is None:return
    logo=logo.copy();logo.thumbnail((w,h),Image.Resampling.LANCZOS)
    img.alpha_composite(logo,(int(x-logo.width//2),int(y-logo.height//2)))

def floor_color(team):
    primary=team['team_primary']
    # Variety is deterministic and tied to the actual school, not random noise.
    palettes=[('E6C99C','EDCFAB'),('CFA97C','DDBD92'),('DFC19B','F1D4B0'),('DCC5A6','EBD6BB'),('D4B38F','E6C6A6'),('E2BA89','EFCE9D')]
    idx=sum(ord(x) for x in team['ncaa_school'])%len(palettes)
    return palettes[idx]

def draw_base(team,logo,variant=None):
    im=Image.new('RGBA',(1024,512),(0,0,0,0));d=ImageDraw.Draw(im)
    pri=rgba(team['team_primary']);sec=rgba(team['team_secondary']);white=(245,245,240,255)
    hardwood,highlight=floor_color(team);wood=rgba(hardwood);wood2=rgba(highlight)
    name=team['hlca_name'].upper();city=team['hlca_city'].upper()
    n=int(team['team_id']);style=n%8 if variant is None else variant
    # Exact Hoop Land overlay footprint from official-like 1024x512 community templates.
    d.rectangle((111,55,912,456),fill=mix(pri,(11,19,33),.20))
    d.rectangle((111,55,912,94),fill=mix(pri,(0,0,0),.28))
    d.rectangle((111,419,912,456),fill=mix(pri,(0,0,0),.30))
    d.rectangle((111,94,191,419),fill=pri)
    d.rectangle((832,94,912,419),fill=pri)
    d.rectangle((191,94,832,419),fill=wood)
    if style%4==0:
        for x in range(192,832,16):
            d.rectangle((x,95,x+8,418),fill=wood2 if (x//16)%2==0 else mix(wood,wood2,.40))
            d.line((x,95,x,418),fill=mix(wood,(90,60,43),.18),width=1)
        for y in range(95,419,23):d.line((191,y,832,y),fill=mix(wood,(105,75,52),.16),width=1)
    elif style%4==1:
        for y in range(95,419,19):
            d.rectangle((191,y,832,y+8),fill=wood2)
            for x in range(192+((y//19)%2)*16,831,64):d.line((x,y,x,y+19),fill=mix(wood,(75,45,25),.2),width=1)
    elif style%4==2:
        for x in range(192,832,32):
            for y in range(96,419,32):
                d.rectangle((x,y,min(x+31,831),min(y+31,418)),fill=wood2 if ((x//32)+(y//32))%2==0 else wood)
                d.line((x,y,x,min(y+31,418)),fill=mix(wood,(80,45,20),.16),width=1)
    else:
        for x in range(192,832,20):d.rectangle((x,95,x+10,418),fill=wood2)
        for y in range(95,419,11):d.line((192,y,831,y),fill=mix(wood,(70,50,30),.10),width=1)
    # Unique apron accent bands reflect real college design variety.
    if style in (1,5):
        for x in range(192,832,42):
            d.rectangle((x,95,x+21,101),fill=mix(pri,sec,.25))
            d.rectangle((x,412,x+21,418),fill=mix(pri,sec,.25))
    if style in (2,6):
        for x in range(192,832,46):
            d.polygon([(x,95),(x+13,95),(x+6,108)],fill=mix(sec,pri,.5))
            d.polygon([(x,419),(x+13,419),(x+6,406)],fill=mix(sec,pri,.5))
    # Court markings consistent with actual Hoop Land screen overlay geometry.
    line=mix(pri,(10,14,30),.14)
    thin=mix(pri,white,.16)
    d.rectangle((191,94,832,419),outline=line,width=2)
    d.line((512,95,512,418),fill=line,width=2)
    d.ellipse((464,207,560,306),outline=line,width=2)
    d.rectangle((192,208,319,305),fill=mix(pri,wood,.13),outline=white,width=2)
    d.rectangle((705,208,831,305),fill=mix(pri,wood,.13),outline=white,width=2)
    d.ellipse((276,224,348,289),outline=line,width=2)
    d.ellipse((676,224,748,289),outline=line,width=2)
    d.arc((213,118,387,394),start=-90,end=90,fill=line,width=2)
    d.arc((637,118,811,394),start=90,end=270,fill=line,width=2)
    d.line((192,119,300,119),fill=line,width=2);d.line((192,393,300,393),fill=line,width=2)
    d.line((724,119,832,119),fill=line,width=2);d.line((724,393,832,393),fill=line,width=2)
    d.ellipse((212,235,250,275),outline=white,width=2)
    d.ellipse((775,235,813,275),outline=white,width=2)
    d.line((192,255,221,255),fill=white,width=2);d.line((803,255,832,255),fill=white,width=2)
    # Side court team end zones carry user's fictional team branding.
    contrast=white if sum(pri[:3])<490 else (26,32,43,255)
    vtext(im,name,(149,255),invert=False,fill=contrast)
    vtext(im,city,(873,255),invert=True,fill=contrast)
    draw=ImageDraw.Draw(im)
    # Site-inspired scoreboard / sponsor ribbon, no unlicensed sponsor trademarks.
    lbl=f'{city}  •  {name}'
    ft=txtfit(draw,lbl,360,initial=16,minimum=10)
    draw.text((512,74),lbl,font=ft,anchor='mm',fill=contrast)
    motto=f'{city} FIELDHOUSE  •  HLCA COLLEGE BASKETBALL'
    ft2=txtfit(draw,motto,380,initial=14,minimum=9)
    draw.text((512,438),motto,font=ft2,anchor='mm',fill=contrast)
    for x in [223,803]:
        # Small school/mascot crest; center logo is the user's verified original.
        paste_logo(im,logo,x,155,74,74)
    paste_logo(im,logo,512,256,148,128)
    return im

def adapt_community(team, src, logo):
    """Retain original NCAA court's wood/paint layout, replace identifiable team branding.

    The outer overlay footprint, art styles and lane patterns survive. Existing
    real-world logo & endzone team text are cleared and rebranded for HLCA.
    """
    try:
        im=src.convert('RGBA')
        if im.size!=(1024,512):
            w,h=im.size
            if abs(w/h-2.0)>.065:return None
            im=im.resize((1024,512),Image.Resampling.NEAREST)
        # Need the game court region to be present; reject small previews/logos.
        if im.getbbox() is None:return None
        # Keep the community floor patterns and markings. Redraw only team
        # identity zones, not full floor. If image has a different footprint,
        # fall back to the original pixel court generator.
        pri=rgba(team['team_primary']);sec=rgba(team['team_secondary'])
        wood,light=floor_color(team);wood=rgba(wood)
        d=ImageDraw.Draw(im)
        d.rectangle((111,94,190,418),fill=pri)
        d.rectangle((833,94,912,418),fill=pri)
        # Center overlay identity patch: retain community wood tone from the
        # adjacent in-bounds plank, then replace the real college center logo.
        # This is a purposeful composite, not AI enlargement.
        center=(438,186,586,322)
        source=im.crop((335,186,483,322))
        # Sample where there is no existing midcourt art. If not usable, use
        # average natural-wood fallback to avoid copying stale NCAA lettering.
        for yy in range(186,323):
            for xx in range(438,587):
                sx=335 + ((xx-438)%148)
                sy=186 + ((yy-186)%137)
                im.putpixel((xx,yy),source.getpixel((sx-335,sy-186)))
        d=ImageDraw.Draw(im)
        line=rgba(team['team_primary'])
        d.line((512,95,512,418),fill=line,width=2)
        contrast=(255,255,255,255) if sum(pri[:3])<490 else (20,30,45,255)
        vtext(im,team['hlca_name'],(149,255),fill=contrast)
        vtext(im,team['hlca_city'],(873,255),invert=True,fill=contrast)
        paste_logo(im,logo,512,255,150,124)
        # Keep floor & remaining community design intact.
        return im
    except Exception as exc:
        print('adapt failure',team['ncaa_school'],exc)
        return None

def session():
    import requests
    s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; HLCA-college-court-reference/1.0)'})
    return s

def pages(session):
    try:
        from bs4 import BeautifulSoup
        h=BeautifulSoup(session.get(SCHOOL_SITE,timeout=25).text,'html.parser')
        links=set()
        for a in h.find_all('a',href=True):
            u=urljoin(SCHOOL_SITE,a['href'])
            if u.startswith(SOURCE_ROOT+'/') and u.split('?')[0].rstrip('/') != SOURCE_ROOT:
                links.add(u.split('?')[0])
        links={u for u in links if len(u[len(SOURCE_ROOT)+1:].split('/'))==1 and u.count('/')>=5}
        # Also handle pages linked but omitted from nav.
        links.update([SOURCE_ROOT+'/swac',SOURCE_ROOT+'/big-ten',SOURCE_ROOT+'/caa',SOURCE_ROOT+'/sec'])
        print('College conference reference pages:',len(links),flush=True)
        return sorted(links)
    except Exception as e:
        print('Cannot list community pages:',e,flush=True)
        return [SOURCE_ROOT+'/swac',SOURCE_ROOT+'/big-ten',SOURCE_ROOT+'/caa']

def collect_reference_candidates(all_teams):
    from bs4 import BeautifulSoup, NavigableString
    sess=session()
    alias=[]
    for t in all_teams:
        names=[t['ncaa_school']]+ALIASES.get(t['ncaa_school'],[])
        for name in names:
            alias.append((normalize(name),t['team_id']))
    alias=sorted(set(alias),key=lambda x:len(x[0]),reverse=True)
    def get_page(url):
        try:
            res=sess.get(url,timeout=30)
            if res.status_code!=200:return url,[]
            soup=BeautifulSoup(res.text,'html.parser')
            heading=None;result=[]
            # Start from actual page main body after navigation if possible.
            for el in soup.body.descendants:
                if isinstance(el,NavigableString):
                    val=str(el).strip()
                    if not val or len(val)>150:continue
                    n=normalize(val)
                    if not n or len(n)>90:continue
                    for key,team_id in alias:
                        # The official school title is usually first in each
                        # heading e.g. 'ALABAMA A&M BULLDOGS'.
                        if len(key)>=6 and (n.startswith(key) or n.startswith('universityof'+key)):
                            heading=team_id;break
                elif getattr(el,'name',None)=='img':
                    src=el.get('src','')
                    if heading is not None and src.startswith('https://sites.google.com/sitesv-images-rt/'):
                        result.append((heading,src,url))
            return url,result
        except Exception as exc:
            return url,[]
    links=pages(sess)
    allref=[]
    with ThreadPoolExecutor(max_workers=10) as pool:
        for url,items in pool.map(get_page,links):
            allref.extend(items)
    ref=defaultdict(list)
    for tid,src,page in allref:ref[tid].append((src,page))
    print('School headings with candidate community imagery:',len(ref),'candidate images:',len(allref),flush=True)
    return ref

def download_reference_images(all_teams):
    ref=collect_reference_candidates(all_teams)
    sess=session();opts={}
    def choose(team):
        tid=team['team_id'];urls=ref.get(tid,[])
        options=[]
        for src,page in urls:
            try:
                r=sess.get(src,timeout=20);r.raise_for_status()
                img=Image.open(io.BytesIO(r.content))
                w,h=img.size
                if (w>=550 and h>=250 and abs(w/h-2.0)<0.09):
                    options.append((w*h,img.copy(),src,page))
            except Exception:continue
        if options:
            options.sort(key=lambda x:x[0],reverse=True)
            return tid,options[0][1:]
        return tid,None
    # Only try at most five candidate images per school (mostly logos/jerseys + 1-3 courts).
    for tid,arr in ref.items():ref[tid]=arr[:8]
    with ThreadPoolExecutor(max_workers=12) as pool:
        tasks=[pool.submit(choose,team) for team in all_teams if team['team_id'] in ref]
        for fut in as_completed(tasks):
            try:
                tid,ans=fut.result()
                if ans: opts[tid]=ans
            except Exception:continue
    print('Downloaded usable 2:1 public NCAA court images:',len(opts),flush=True)
    return opts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--local',action='store_true',help='local fallback only; no network')
    ap.add_argument('--community',action='store_true',help='use public NCAA courts if found')
    ap.add_argument('--limit',type=int,default=0)
    args=ap.parse_args()
    rows=list(csv.DictReader(SCHOOL_CSV.open(encoding='utf-8')))
    for t in rows:t['team_id']=int(t['team_id'])
    assert len(rows)==261 and len(set(t['team_id'] for t in rows))==261
    if args.limit:rows=rows[:args.limit]
    communities=download_reference_images(rows) if args.community and not args.local else {}
    sess=None if args.local else session()
    OUT.mkdir(exist_ok=True)
    audit=[]
    for i,team in enumerate(rows):
        logo=safe_logo(team,args.local,sess)
        source=communities.get(team['team_id'])
        if source:
            img,source_url,page=source
            court=adapt_community(team,img,logo)
        else:
            court=None
        if court is None:
            court=draw_base(team,logo)
            source_url='';page='';kind='Original fictional team design'
        else:
            kind='Adapted publicly credited NCAA community reference'
        assert court.size==(1024,512)
        target=OUT/team['court_filename']
        court.save(target,format='PNG',optimize=True)
        audit.append({'team_id':team['team_id'],'ncaa_school':team['ncaa_school'],
                      'hlca_team':team['hlca_city']+' '+team['hlca_name'],
                      'filename':target.name,'source_category':kind,
                      'community_page':page,'community_image_url':source_url,
                      'public_court_url':f'https://raw.githubusercontent.com/{REPO}/main/courts/{quote(target.name)}'})
        if (i+1)%40==0:print('Rendered',i+1,'of',len(rows),flush=True)
    with (ROOT/'court_sources.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=audit[0].keys());w.writeheader();w.writerows(audit)
    import collections
    cnt=collections.Counter(a['source_category'] for a in audit)
    print('Finished courts:',len(audit),'source methods:',dict(cnt),flush=True)

if __name__=='__main__':main()
