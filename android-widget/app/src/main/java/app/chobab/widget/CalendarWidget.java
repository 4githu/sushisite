package app.chobab.widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.*;
import android.net.Uri;
import android.widget.RemoteViews;
import org.json.*;
import java.time.*;
import java.time.format.DateTimeFormatter;

public class CalendarWidget extends AppWidgetProvider {
 static final String REFRESH="app.chobab.widget.REFRESH";
 static final Class<?>[] PROVIDERS={CalendarWidget.class,DayWidget.class,WeekWidget.class,MonthWidget.class,TodoWidget.class};
 protected String mode(){return "week";}
 static void refresh(Context context){for(Class<?> cls:PROVIDERS)context.sendBroadcast(new Intent(context,cls).setAction(REFRESH));}
 @Override public void onReceive(Context context,Intent intent){String action=intent.getAction();if(REFRESH.equals(action)||AppWidgetManager.ACTION_APPWIDGET_UPDATE.equals(action)){PendingResult pending=goAsync();new Thread(()->{try{update(context);}finally{pending.finish();}}).start();}else super.onReceive(context,intent);}
 static PendingIntent open(Context c,String url,int id){return PendingIntent.getActivity(c,id,WebAppLink.intent(c,url),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
 static LocalDateTime local(JSONObject e,String key)throws Exception{String raw=e.getString(key);try{return OffsetDateTime.parse(raw).atZoneSameInstant(ZoneId.of("Asia/Seoul")).toLocalDateTime();}catch(Exception ignored){return LocalDateTime.parse(raw);}}
 @Override public void onAppWidgetOptionsChanged(Context c,AppWidgetManager m,int id,android.os.Bundle options){refresh(c);}
 void update(Context context){
  AppWidgetManager manager=AppWidgetManager.getInstance(context);
  int[] ids=manager.getAppWidgetIds(new ComponentName(context,getClass()));
  if(ids.length==0)return;
  for(int widgetId:ids){
  RemoteViews views=new RemoteViews(context.getPackageName(),R.layout.widget);
  String origin=Api.origin(context),mode=mode();
  String label=mode.equals("day")?"오늘 일정":mode.equals("week")?"이번 주 일정":mode.equals("month")?"월간 캘린더":mode.equals("tasks")?"할 일":"다음 일정";
  views.setTextViewText(R.id.title,label);
  views.setOnClickPendingIntent(R.id.refresh,PendingIntent.getBroadcast(context,0,new Intent(context,getClass()).setAction(REFRESH),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
  views.setOnClickPendingIntent(R.id.title,open(context,origin+"/personal-project/calendar"+(mode.equals("upcoming")||mode.equals("month")?"":"/"+mode),0));
  views.removeAllViews(R.id.events);
  try{
   String token=Api.token(context);if(token.isEmpty())throw new Exception("온도 위젯 앱에서 계정을 연결하세요");
   JSONArray events=Api.call(origin,"feed?view="+mode,token,null).getJSONArray("events");
   if(mode.equals("week"))WeekTimetable.render(context,views,events,origin,widgetId);
   else if(mode.equals("month"))renderMonth(context,views,events,origin);
   else for(int i=0;i<Math.min(4,events.length());i++){
    JSONObject e=events.getJSONObject(i);RemoteViews row=new RemoteViews(context.getPackageName(),R.layout.event);
    String date=local(e,"startTime").format(DateTimeFormatter.ofPattern(e.optBoolean("isAllDay")?"M/d · 종일":"M/d HH:mm"));
    row.setTextViewText(R.id.event,date+"  "+e.getString("title"));
    row.setOnClickPendingIntent(R.id.event,open(context,origin+"/personal-project/calendar?event="+e.getInt("id"),e.getInt("id")));
    views.addView(R.id.events,row);
   }
   views.setTextViewText(R.id.status,events.length()+"개 · "+LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))+" 갱신 · 제목을 눌러 전체 보기");
  }catch(Exception e){views.setTextViewText(R.id.status,e.getMessage());views.setOnClickPendingIntent(R.id.events,PendingIntent.getActivity(context,99,new Intent(context,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));}
  manager.updateAppWidget(widgetId,views);
  }
 }
 void renderMonth(Context c,RemoteViews views,JSONArray events,String origin)throws Exception{
  LocalDate first=LocalDate.now(ZoneId.of("Asia/Seoul")).withDayOfMonth(1), day=first.minusDays(first.getDayOfWeek().getValue()%7);
  int[] cells={R.id.c0,R.id.c1,R.id.c2,R.id.c3,R.id.c4,R.id.c5,R.id.c6};
  views.setTextViewText(R.id.title,first.getYear()+"년 "+first.getMonthValue()+"월");
  RemoteViews header=new RemoteViews(c.getPackageName(),R.layout.month_week);String[] names={"일","월","화","수","목","금","토"};
  for(int i=0;i<7;i++)header.setTextViewText(cells[i],names[i]);views.addView(R.id.events,header);
  for(int week=0;week<6;week++){
   RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.month_week);
   for(int col=0;col<7;col++,day=day.plusDays(1)){
    int count=0;
    for(int i=0;i<events.length();i++){
     JSONObject event=events.getJSONObject(i);LocalDateTime start=local(event,"startTime"),end=event.isNull("endTime")?start.plusMinutes(1):local(event,"endTime");
     if(start.isBefore(day.plusDays(1).atStartOfDay())&&end.isAfter(day.atStartOfDay()))count++;
    }
    row.setTextViewText(cells[col],day.getMonth()==first.getMonth()?day.getDayOfMonth()+(count>0?"\n·"+count:""):"");
    row.setOnClickPendingIntent(cells[col],open(c,origin+"/personal-project/calendar/day?date="+day,day.hashCode()));
   }
   views.addView(R.id.events,row);
  }
 }
}
