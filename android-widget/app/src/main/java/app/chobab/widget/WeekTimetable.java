package app.chobab.widget;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.widget.RemoteViews;
import org.json.*;
import java.time.*;
import java.util.*;

/** Minute-proportional columns with separate lanes for overlapping events. */
final class WeekTimetable {
 static final ZoneId SEOUL=ZoneId.of("Asia/Seoul");
 static class Entry extends TimelineLayout.Span {JSONObject event;Entry(JSONObject e,int s,int n){super(s,n);event=e;}}
 static int px(Context c,float dp){return Math.round(dp*c.getResources().getDisplayMetrics().density);}
 static RemoteViews block(Context c,int height,String text,int color){
  RemoteViews v=new RemoteViews(c.getPackageName(),R.layout.week_block);
  v.setInt(R.id.block,"setHeight",height);v.setTextViewText(R.id.block,text);v.setInt(R.id.block,"setBackgroundColor",color);return v;
 }
 static void render(Context c,RemoteViews root,JSONArray events,String origin,int widgetId)throws Exception{
  LocalDate today=LocalDate.now(SEOUL),first=today.minusDays(today.getDayOfWeek().getValue()%7);
  List<List<Entry>> days=new ArrayList<>();List<List<JSONObject>> all=new ArrayList<>();
  int from=8*60,to=22*60;
  for(int d=0;d<7;d++){
   LocalDate day=first.plusDays(d);List<Entry> entries=new ArrayList<>();List<JSONObject> allday=new ArrayList<>();
   for(int i=0;i<events.length();i++){
    JSONObject e=events.getJSONObject(i);LocalDateTime s=CalendarWidget.local(e,"startTime"),n=e.isNull("endTime")?s.plusMinutes(30):CalendarWidget.local(e,"endTime");
    if(!n.isAfter(s))n=s.plusMinutes(30);
    if(!s.isBefore(day.plusDays(1).atStartOfDay())||!n.isAfter(day.atStartOfDay()))continue;
    if(e.optBoolean("isAllDay")){allday.add(e);continue;}
    int start=s.isBefore(day.atStartOfDay())?0:s.getHour()*60+s.getMinute();
    int end=!n.isBefore(day.plusDays(1).atStartOfDay())?1440:n.getHour()*60+n.getMinute();
    entries.add(new Entry(e,start,end));from=Math.min(from,(start/60)*60);to=Math.max(to,((end+59)/60)*60);
   }
   entries.sort(Comparator.comparingInt(e->e.start));days.add(entries);all.add(allday);
  }
  int height=AppWidgetManager.getInstance(c).getAppWidgetOptions(widgetId).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT,360);
  int gridPx=px(c,Math.max(100,height-144));
  RemoteViews grid=new RemoteViews(c.getPackageName(),R.layout.week_grid);
  grid.addView(R.id.time_axis,block(c,px(c,30),"",0));grid.addView(R.id.time_axis,block(c,px(c,26),"종일",0));
  for(int minute=from;minute<to;minute+=60){int a=Math.round((minute-from)*(float)gridPx/(to-from)),b=Math.round((minute+60-from)*(float)gridPx/(to-from));grid.addView(R.id.time_axis,block(c,b-a,String.format(Locale.KOREA,"%02d",minute/60),0));}
  String[] names={"일","월","화","수","목","금","토"};
  for(int d=0;d<7;d++){
   LocalDate day=first.plusDays(d);RemoteViews column=new RemoteViews(c.getPackageName(),R.layout.week_day);
   column.setTextViewText(R.id.day_name,names[d]+" "+day.getDayOfMonth());
   if(day.equals(today))column.setInt(R.id.day_name,"setBackgroundColor",0xffFBDDD6);
   String dayUrl=origin+"/personal-project/calendar/day?date="+day;
   column.setOnClickPendingIntent(R.id.day_name,CalendarWidget.open(c,dayUrl,day.hashCode()));
   List<JSONObject> allday=all.get(d);column.setTextViewText(R.id.all_day,allday.isEmpty()?"":allday.get(0).getString("title")+(allday.size()>1?" +"+(allday.size()-1):""));
   column.setOnClickPendingIntent(R.id.all_day,CalendarWidget.open(c,allday.size()==1?dayUrl+"&event="+allday.get(0).getInt("id"):dayUrl,day.hashCode()));
   List<Entry> entries=days.get(d);int lanes=TimelineLayout.assignLanes(entries);
   for(int lane=0;lane<lanes;lane++){
    RemoteViews laneView=new RemoteViews(c.getPackageName(),R.layout.week_lane);int cursor=0;
    for(Entry e:entries){if(e.lane!=lane)continue;
     int top=TimelineLayout.pixelAt(e.start,from,to,gridPx),bottom=TimelineLayout.pixelAt(e.end,from,to,gridPx);
     if(top>cursor)laneView.addView(R.id.lane,block(c,top-cursor,"",0));
     RemoteViews event=block(c,Math.max(1,bottom-top),e.event.getString("title")+String.format(Locale.KOREA,"\n%02d:%02d",e.start/60,e.start%60),0xffDBE8F4);
     event.setContentDescription(R.id.block,e.event.getString("title")+" "+String.format(Locale.KOREA,"%02d:%02d",e.start/60,e.start%60));
     event.setOnClickPendingIntent(R.id.block,CalendarWidget.open(c,dayUrl+"&event="+e.event.getInt("id"),e.event.getInt("id")));
     laneView.addView(R.id.lane,event);cursor=bottom;
    }
    column.addView(R.id.day_lanes,laneView);
   }
   grid.addView(R.id.week_days,column);
  }
  root.setTextViewText(R.id.title,(first.getMonthValue())+"/"+first.getDayOfMonth()+" – "+first.plusDays(6).getMonthValue()+"/"+first.plusDays(6).getDayOfMonth()+" 시간표");
  root.addView(R.id.events,grid);
 }
}
