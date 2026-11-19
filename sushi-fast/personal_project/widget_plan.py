"""Private day-plan preview in the same 420×760 coordinates as the ink editor."""
import base64,json,re
from datetime import datetime,timedelta
import fitz
from .db import connection

def render(uid,start,events):
 doc=fitz.open();page=doc.new_page(width=420,height=760)
 for i in range(19):
  y=22+i*40;page.draw_line((42,y),(410,y),color=(.82,.83,.85),width=.4)
  if i<18:page.insert_text((5,y+12),f'{(8+i)%24:02}:00',fontsize=9,color=(.4,.4,.45))
 window=start+timedelta(hours=8);end=start+timedelta(hours=26)
 spans=[];all_day=[]
 for e in events:
  if e.get('isAllDay'):all_day.append(e['title']);continue
  a=datetime.fromisoformat(e['startTime'].replace('Z','+00:00'));b=datetime.fromisoformat(e['endTime'].replace('Z','+00:00')) if e.get('endTime') else a+timedelta(minutes=30)
  if a.tzinfo is None:a=a.replace(tzinfo=start.tzinfo)
  if b.tzinfo is None:b=b.replace(tzinfo=start.tzinfo)
  if a>=end or b<=window:continue
  spans.append([max(0,(a-window).total_seconds()/60),min(1080,(b-window).total_seconds()/60),e])
 # Use one lane per simultaneous event, reclaiming lanes when an event ends.
 spans.sort(key=lambda s:s[0]);groups=[]
 for span in spans:
  if not groups or span[0]>=max(s[1] for s in groups[-1]):groups.append([])
  groups[-1].append(span)
 for group in groups:
  ends=[]
  for span in group:
   lane=next((i for i,e in enumerate(ends) if e<=span[0]),len(ends))
   if lane==len(ends):ends.append(span[1])
   else:ends[lane]=span[1]
   span.append(lane)
  width=364/max(1,len(ends))
  for a,b,e,lane in group:
   x=44+lane*width;y=22+a*2/3;h=max(10,(b-a)*2/3)
   page.draw_rect(fitz.Rect(x,y,x+width-2,y+h),color=None,fill=(.84,.90,.95),fill_opacity=.6)
   page.insert_textbox(fitz.Rect(x+3,y+1,x+width-4,y+min(h,36)),e['title']+(' · '+e['location'] if e.get('location') else ''),fontname='korea',fontsize=8,color=(.2,.3,.4))
 if all_day:page.insert_textbox(fitz.Rect(44,2,410,21),'종일 · '+' · '.join(all_day),fontname='korea',fontsize=8)
 with connection() as db:row=db.execute('SELECT data FROM personal_documents WHERE user_id=? AND document_key=?',(uid,'pdf:day-ink:'+start.date().isoformat())).fetchone()
 if row:
  notebook=json.loads(row['data']);p=next(iter(notebook.get('pages',[])),{})
  for s in p.get('strokes',[]):
   color=s.get('color','#222222').lstrip('#');color=color if re.fullmatch('[0-9a-fA-F]{6}',color) else '222222'
   rgb=tuple(int(color[i:i+2],16)/255 for i in (0,2,4));pts=s.get('points',[])
   for i,b in enumerate(pts):
    a=pts[max(0,i-1)];w=max(.2,min(30,s.get('width',3)*(max(.25,b.get('pressure',.5)) if s.get('kind')=='pen' else 1)))
    page.draw_line((a['x'],760-a['y']),(b['x']+.001,760-b['y']),color=rgb,width=w,stroke_opacity=.25 if s.get('kind')=='highlight' else 1)
  for n in p.get('notes',[]):page.insert_text((n['x'],760-n['y']),n.get('text',''),fontname='korea',fontsize=max(6,min(40,n.get('size',12))))
 result=base64.b64encode(page.get_pixmap().tobytes('png')).decode();doc.close();return result
