import requests,bs4
u="https://sites.google.com/view/hooplandcourts/ncaa/swac"
r=requests.get(u,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
print('STATUS',r.status_code,'LENGTH',len(r.content))
s=bs4.BeautifulSoup(r.text,'html.parser')
imgs=s.find_all('img')
print('IMG_COUNT',len(imgs))
for im in imgs[:14]:
 print('IMG',repr({k:str(v)[:280] for k,v in im.attrs.items()}))
for key in ['sitesv-images-rt','ALABAMA A&M','Alabama','sites.google.com/sitesv-images-rt']:
 print('TOKEN',repr(key),r.text.find(key))
