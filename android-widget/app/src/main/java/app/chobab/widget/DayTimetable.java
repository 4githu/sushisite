package app.chobab.widget;

import android.content.Context;
import android.widget.RemoteViews;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.*;
import java.util.*;

/** A compact, minute-proportional timetable rendered with launcher-supported RemoteViews. */
final class DayTimetable {
 static final class Entry extends TimelineLayout.Span {
  final JSONObject event;
  Entry(JSONObject event,int start,int end){super(start,end);this.event=event;}
 }
 static void render(Context c,RemoteViews target,JSONArray events,String origin,int id,LocalDate day,int height)throws Exception{
  int from=8*60,to=26*60;LocalDateTime midnight=day.atStartOfDay();
  List<Entry> timed=new ArrayList<>();List<JSONObject> allDay=new ArrayList<>();
  for(int i=0;i<events.length();i++){
   JSONObject e=events.getJSONObject(i);
   if(e.optBoolean("isAllDay")||e.optBoolean("timeUnspecified")){allDay.add(e);continue;}
   LocalDateTime start=CalendarWidget.local(e,"startTime"),end=e.isNull("endTime")?start.plusMinutes(30):CalendarWidget.local(e,"endTime");
   if(!end.isAfter(start))end=start.plusMinutes(30);
   int a=(int)Duration.between(midnight,start).toMinutes(),b=(int)Duration.between(midnight,end).toMinutes();
   if(b>from&&a<to)timed.add(new Entry(e,Math.max(from,a),Math.min(to,b)));
  }
  timed.sort(Comparator.comparingInt(e->e.start));
  // Use the available height for the scheduled hours while retaining a useful empty-day view.
  if(!timed.isEmpty()){
   int earliest=timed.stream().mapToInt(e->e.start).min().orElse(from),latest=timed.stream().mapToInt(e->e.end).max().orElse(to);
   from=Math.max(8*60,(earliest/60)*60);to=Math.min(26*60,Math.max(from+6*60,((latest+59)/60)*60));
  }else to=18*60;
  // Keep the current hour visible on today's timetable even if the last
  // scheduled event finished earlier or the day has no timed events.
  LocalDateTime now=LocalDateTime.now(ZoneId.of("Asia/Seoul"));
  if(day.equals(now.toLocalDate())){
   int current=now.getHour()*60+now.getMinute();
   if(current>=8*60&&current<24*60){from=Math.min(from,(current/60)*60);to=Math.min(26*60,Math.max(to,((current/60)+1)*60));}
  }
  int gridPx=WeekTimetable.px(c,Math.max(72,height-88-(allDay.isEmpty()?0:26)));
  RemoteViews grid=new RemoteViews(c.getPackageName(),R.layout.day_timetable);
  if(!allDay.isEmpty()){
   JSONObject e=allDay.get(0);grid.setTextViewText(R.id.daily_all_day,e.optString("title","")+(allDay.size()>1?" +"+(allDay.size()-1):""));
   grid.setOnClickPendingIntent(R.id.daily_all_day,CalendarWidget.open(c,origin+"/personal-project/calendar/day?date="+day,day.hashCode()));
  }else grid.setViewVisibility(R.id.daily_all_day,android.view.View.GONE);
  for(int m=from;m<to;m+=60){int a=TimelineLayout.pixelAt(m,from,to,gridPx),b=TimelineLayout.pixelAt(Math.min(m+60,to),from,to,gridPx);grid.addView(R.id.daily_axis,WeekTimetable.block(c,b-a,String.format(Locale.KOREA,"%02d",(m/60)%24),0));}
  int lanes=TimelineLayout.assignLanes(timed);
  for(int lane=0;lane<lanes;lane++){
   RemoteViews column=new RemoteViews(c.getPackageName(),R.layout.week_lane);int cursor=0;
   for(Entry e:timed){if(e.lane!=lane)continue;int top=TimelineLayout.pixelAt(e.start,from,to,gridPx),bottom=TimelineLayout.pixelAt(e.end,from,to,gridPx);
    if(top>cursor)column.addView(R.id.lane,WeekTimetable.block(c,top-cursor,"",0));
    RemoteViews block=WeekTimetable.block(c,Math.max(1,bottom-top),e.event.optString("title",""),0xffeaf3ee);
    block.setTextViewTextSize(R.id.block,android.util.TypedValue.COMPLEX_UNIT_SP,12);
    block.setContentDescription(R.id.block,e.event.optString("title","")+String.format(Locale.KOREA," %02d:%02d–%02d:%02d",(e.start/60)%24,e.start%60,(e.end/60)%24,e.end%60));
    block.setOnClickPendingIntent(R.id.block,CalendarWidget.open(c,origin+"/personal-project/calendar/day?date="+day+"&event="+e.event.getInt("id"),e.event.getInt("id")));
    column.addView(R.id.lane,block);cursor=bottom;
   }
   grid.addView(R.id.daily_lanes,column);
  }
  target.addView(R.id.plan_agenda,grid);
 }
}
