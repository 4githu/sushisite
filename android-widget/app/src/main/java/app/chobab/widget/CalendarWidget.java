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
 static void refresh(Context context){context.sendBroadcast(new Intent(context,CalendarWidget.class).setAction(REFRESH));}
 @Override public void onReceive(Context context,Intent intent){String action=intent.getAction();if(REFRESH.equals(action)||AppWidgetManager.ACTION_APPWIDGET_UPDATE.equals(action)){PendingResult pending=goAsync();new Thread(()->{try{update(context);}finally{pending.finish();}}).start();}else super.onReceive(context,intent);}
 static void update(Context context){AppWidgetManager manager=AppWidgetManager.getInstance(context);int[] ids=manager.getAppWidgetIds(new ComponentName(context,CalendarWidget.class));RemoteViews views=new RemoteViews(context.getPackageName(),R.layout.widget);String origin=Api.origin(context);views.setOnClickPendingIntent(R.id.refresh,PendingIntent.getBroadcast(context,0,new Intent(context,CalendarWidget.class).setAction(REFRESH),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));views.setOnClickPendingIntent(R.id.title,PendingIntent.getActivity(context,0,new Intent(Intent.ACTION_VIEW,Uri.parse(origin+"/personal-project/calendar")),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));views.removeAllViews(R.id.events);try{String token=Api.token(context);if(token.isEmpty())throw new Exception("온도 위젯 앱에서 계정을 연결하세요");JSONArray events=Api.call(origin,"feed",token,null).getJSONArray("events");for(int i=0;i<Math.min(4,events.length());i++){JSONObject e=events.getJSONObject(i);RemoteViews row=new RemoteViews(context.getPackageName(),R.layout.event);String raw=e.getString("startTime"),date;try{LocalDateTime local=e.optBoolean("isAllDay")?LocalDateTime.parse(raw):OffsetDateTime.parse(raw).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime();date=local.format(DateTimeFormatter.ofPattern(e.optBoolean("isAllDay")?"M/d · 종일":"M/d HH:mm"));}catch(Exception ignored){date=raw.substring(0,Math.min(16,raw.length())).replace('T',' ');}row.setTextViewText(R.id.event,date+"  "+e.getString("title"));row.setOnClickPendingIntent(R.id.event,PendingIntent.getActivity(context,e.getInt("id"),new Intent(Intent.ACTION_VIEW,Uri.parse(origin+"/personal-project/calendar?event="+e.getInt("id"))),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));views.addView(R.id.events,row);}views.setTextViewText(R.id.status,events.length()==0?"다가오는 일정이 없습니다":LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))+" 업데이트 · ↻ 새로고침");}catch(Exception e){views.setTextViewText(R.id.status,e.getMessage());views.setOnClickPendingIntent(R.id.events,PendingIntent.getActivity(context,99,new Intent(context,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));}for(int id:ids)manager.updateAppWidget(id,views);}
}
