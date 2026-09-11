#!/usr/bin/env python3
"""公开题录采集器；Python 3 标准库，无需安装依赖。"""
import argparse, datetime, hashlib, html, json, re, time, urllib.request
from pathlib import Path
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parent
TODAY=datetime.date.today().isoformat()
RULES={'民法':['民法','合同','契约','侵权','人格','个人信息','家庭','养老','清偿','三权分置'], '商法':['公司','股份','股东','资本市场','对赌','证券','破产','董事'], '网络治理':['数字经济','平台','个人信息','数据','算法','数字司法'], 'AI治理':['人工智能','深度伪造','生成式','大模型']}
def text(s):
 s=re.sub(r'<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>','',s,flags=re.S|re.I)
 return '\n'.join(x.strip() for x in html.unescape(re.sub('<[^>]+>','\n',s)).splitlines() if x.strip())
def links(s):return [(html.unescape(u),text(t)) for u,t in re.findall(r'<a\b[^>]*href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>',s,re.S|re.I)]
def get(u):
 time.sleep(.6)
 r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'PersonalLawReadingLibrary/1.0'}),timeout=18)
 s=r.read().decode('utf-8-sig',errors='replace')
 if 'wzws-waf-cgi' in s or 'Please enable JavaScript' in s:raise ValueError('网站要求浏览器验证；本次不提取')
 return s

def record(journal,year,issue,title,author,url,**kw):
 key='|'.join([journal,str(year),str(issue),re.sub(r'\s','',title)])
 d=dict(id=hashlib.sha256(key.encode()).hexdigest()[:12],journal=journal,year=year,issue=issue,title=title,author=author,source_url=url,abstract=None,keywords=None,pages=None,pdf_url=None,published_date=None,web_date=None,first_seen=TODAY,last_checked=TODAY,collection_method='公开网页提取',notes='')
 d.update(kw);d['topics']=[k for k,ws in RULES.items() if any(w in title for w in ws)];d['classification_basis']='题名关键词初筛，非作者分类';return d

def china(s,u):
 t=text(s);m=re.search(r'《中国法学》\s*(\d{4})年\s*(\d+)期',t)
 if not m:raise ValueError('未识别期次')
 year,issue=map(int,m.groups());out=[]
 for block in re.findall(r'<li\b[^>]*>(.*?)</li>',s,re.S):
  ls=links(block);a=next(((h,t) for h,t in ls if '/portal/article/' in h),None)
  if not a:continue
  spans=re.findall(r'<span[^>]*>(.*?)</span>',block,re.S);author=text(spans[0]) if spans else ''
  d=record('中国法学',year,issue,a[1],author.split(',')[0].strip(),urljoin(u,a[0]),author_info=author)
  if not d['topics']:continue
  d['pdf_url']=next((urljoin(u,h) for h,t in ls if '.pdf' in h.lower()),None)
  try:
   dt=text(get(d['source_url']))
   ab=re.search(r'内容提要\s*(.*?)(?:关键词|Abstract[:：]|友情链接)',dt,re.S)
   d['abstract']=re.sub(r'\s+',' ',ab.group(1)).strip() if ab else None
   km=re.search(r'关键词\s*(.*?)(?:Abstract[:：]|友情链接)',dt,re.S);d['keywords']=km.group(1).strip() if km else None
   for label,key,pattern in [('时间','web_date',r'(\d{4}-\d{2}-\d{2})'),('出版日期','published_date',r'(\d{4}年\d+月\d+日)')]:
    dm=re.search(label+r'[:：]\s*'+pattern,dt);d[key]=dm.group(1) if dm else None
  except Exception as e:d['notes']='摘要暂未获取：'+str(e)
  out.append(d)
 return out

def faxue(s,u):
 out=[]
 for block in re.findall(r'<ul\b[^>]*>(.*?)</ul>',s,re.S):
  if 'name="file_no"' not in block:continue
  ls=links(block);a=next(((h,t) for h,t in ls if '/Magazine/Show?' in h and t!='[摘要]'),None)
  if not a:continue
  lis=re.findall(r'<li[^>]*>(.*?)</li>',block,re.S);t=' '.join(text(block).split());m=re.search(r'(\d{4})\s*\.\((\d+)\)(\d+):(\d+-\d+)',t)
  if not m:raise ValueError('未识别法学研究期次')
  y,v,i,p=m.groups();d=record('法学研究',int(y),int(i),a[1],text(lis[1]),urljoin(u,a[0]),pages=p,volume=v,notes='本次依据官网目录核验题录；摘要详情页要求浏览器验证，未获取摘要。')
  if not d['topics']:continue
  d['pdf_url']=next((urljoin(u,h) for h,t in ls if '.pdf' in h.lower()),None);out.append(d)
 return out

def save(rows,errors):
 old=json.loads((ROOT/'papers.json').read_text()) if (ROOT/'papers.json').exists() else []
 db={d['id']:d for d in old};new=0
 for d in rows:
  if d['id'] in db:
   prev=db[d['id']];d['first_seen']=prev['first_seen']
   for k in ['abstract','keywords','pdf_url','pages']:
    if d.get(k) is None and prev.get(k):d[k]=prev[k]
  else:new+=1
  db[d['id']]=d
 data=sorted(db.values(),key=lambda d:(-d['year'],-d['issue'],d['journal'],d['title']))
 (ROOT/'papers.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
 cards=ROOT/'papers';cards.mkdir(exist_ok=True)
 for d in data:
  meta='\n'.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in d.items() if k not in ['abstract','notes'])
  body=f"---\n{meta}\n---\n\n# {d['title']}\n\n{d['author']}｜《{d['journal']}》{d['year']}年第{d['issue']}期｜页码：{d['pages'] or '未获取'}\n\n主题：{'、'.join(d['topics'])}（题名初筛）\n\n[原始来源]({d['source_url']})\n"
  if d['pdf_url']:body+=f"\n[期刊提供的全文入口]({d['pdf_url']})（链接已从页面提取，未逐一验证下载）\n"
  body+='\n## 原文摘要\n\n'+(d['abstract'] or '暂未获取；请通过原始来源查看。')+'\n\n'+d['notes']+'\n'
  (cards/(d['id']+'.md')).write_text(body)
 index='# 法学论文阅读库\n\n关注民法、商法、网络治理与 AI 治理。保留作者信息，摘要不改写。\n\n本次采集日期：'+TODAY+'。这是已核验来源范围内的选题索引，不保证三刊最新论文完整覆盖。\n\n'
 index+='|期刊|本版覆盖|获取状态|\n|---|---|---|\n|中国法学|2026年第3、4期|相关论文题录、摘要及全文入口|\n|法学研究|2026年第4期|相关题录及页面提供的全文入口；摘要未获取|\n|中外法学|2026年第3期|文献中心目录核验的相关题录；官网访问异常，最新期未确认|\n\n'
 for topic in RULES:
  index+='## '+topic+'\n\n'
  for d in data:
   if topic in d['topics']:index+=f"- [{d['title']}](papers/{d['id']}.md) — {d['author']}，《{d['journal']}》{d['year']}年第{d['issue']}期；"+('有摘要' if d['abstract'] else '题录')+'\n'
  index+='\n'
 (ROOT/'阅读目录.md').write_text(index)
 (ROOT/'last_run.json').write_text(json.dumps({'checked_at':TODAY,'new':new,'total':len(data),'errors':errors},ensure_ascii=False,indent=2))
 print(json.dumps({'new':new,'total':len(data),'abstracts':sum(bool(d['abstract']) for d in data),'errors':errors},ensure_ascii=False))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true',help='只从已有数据重建卡片');a=ap.parse_args();rows=[];errors=[]
 if not a.offline:
  urls=['https://clsjp.chinalaw.org.cn/portal/list/index.html?id=1934','https://clsjp.chinalaw.org.cn/portal/list/index.html?id=1926']
  try:
   home='https://clsjp.chinalaw.org.cn/portal/index/index.html'
   for h,t in links(get(home)):
    if re.fullmatch(r'《中国法学》\s*\d{4}年第\d+期',t):
     dest=urljoin(home,h)
     if dest not in urls:urls.insert(0,dest)
  except Exception as e:errors.append({'url':'中国法学首页新期发现','error':str(e)})
  for u in urls:
   try:rows.extend(china(get(u),u))
   except Exception as e:errors.append({'url':u,'error':str(e)})
  u='https://faxueyanjiu.ajcass.com/'
  try:rows.extend(faxue(get(u),u))
  except Exception as e:errors.append({'url':u,'error':str(e)})
 seed=ROOT/'verified_import.json'
 if seed.exists():rows.extend(json.loads(seed.read_text()))
 save(rows,errors)
if __name__=='__main__':main()
