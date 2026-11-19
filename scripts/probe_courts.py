import requests, bs4, io
from PIL import Image
u="https://sites.google.com/view/hooplandcourts/ncaa/swac"
r=requests.get(u,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
print('STATUS',r.status_code,'LENGTH',len(r.content))
s=bs4.BeautifulSoup(r.text,'html.parser')
print('TEXT_LEN',len(s.get_text(' ',strip=True)))
print('TEXT_START',repr(s.get_text(' ',strip=True)[-6500:]))
imgs=s.find_all('img')
print('IMG_COUNT',len(imgs))
for n,im in enumerate(imgs[:12]):
 src=im.get('src','')
 ctx=im.find_parent('div')
 print('INDEX',n,'NEAR',repr(ctx.get_text(' ',strip=True)[-150:] if ctx else ''))
 try:
  d=requests.get(src,timeout=20)
  v=Image.open(io.BytesIO(d.content))
  print('DOWNLOADED',n,d.status_code,len(d.content),v.size,v.mode,v.format)
 except Exception as e: print('FAIL',n,str(e)[:180])
