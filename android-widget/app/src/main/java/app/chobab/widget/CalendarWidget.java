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
 static final java.util.concurrent.ConcurrentHashMap<Integer,java.util.concurrent.atomic.AtomicLong> updates=new java.util.concurrent.ConcurrentHashMap<>();
 static final String COMPLETE="app.chobab.widget.COMPLETE";
 static final String NAVIGATE="app.chobab.widget.NAVIGATE";
 static final String REFRESH="app.chobab.widget.REFRESH";
 static final Class<?>[] PROVIDERS={NextWidget.class,DayWidget.class,WeekWidget.class,MonthWidget.class,TodoWidget.class,PlanWidget.class,MemoWidget.class,CalendarWidget.class,MealWidget.class,RecentNotesWidget.class};
 // Keep the provider identity and weekly mode of widgets pinned by earlier releases.
 protected String mode(){return "week";}
 static boolean markAuthRejected(Context context){
  synchronized(CalendarWidget.class){var prefs=context.getSharedPreferences("widget",0);if(prefs.getBoolean("auth-rejected",false))return false;prefs.edit().putBoolean("auth-rejected",true).apply();return true;}
 }
 static boolean isWidePlan(int widthDp){return widthDp>=340;}
 static void refresh(Context context){for(Class<?> cls:PROVIDERS)context.sendBroadcast(new Intent(context,cls).setAction(REFRESH));}
 @Override public void onReceive(Context context,Intent intent){
  String action=intent.getAction();
  if(REFRESH.equals(action)||NAVIGATE.equals(action)||COMPLETE.equals(action)||AppWidgetManager.ACTION_APPWIDGET_UPDATE.equals(action)){
   int id=intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,-1);
   if(NAVIGATE.equals(action)&&id!=-1){
    int delta=intent.getIntExtra("delta",0);android.content.SharedPreferences prefs=context.getSharedPreferences("widget",0);
    int offset=delta==0?0:prefs.getInt("offset-"+id,0)+delta;
    prefs.edit().putInt("offset-"+id,Math.max(-120,Math.min(120,offset))).apply();
   }
   WidgetUpdateJob.schedule(context,getClass(),id,intent);
  }else super.onReceive(context,intent);
 }
 @Override public void onDeleted(Context c,int[] ids){for(int id:ids)c.getSharedPreferences("widget",0).edit().remove("offset-"+id).remove("cache-"+id).apply();}
 PendingIntent navigation(Context c,int id,int delta){return PendingIntent.getBroadcast(c,id,new Intent(c,getClass()).setAction(NAVIGATE).setData(Uri.parse("ondo-widget://navigate/"+id+"/"+delta)).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,id).putExtra("delta",delta),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}

 static PendingIntent open(Context c,String url,int id){return PendingIntent.getActivity(c,id,WebAppLink.intent(c,url),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
 static LocalDateTime local(JSONObject e,String key)throws Exception{String raw=e.getString(key);try{return OffsetDateTime.parse(raw).atZoneSameInstant(ZoneId.of("Asia/Seoul")).toLocalDateTime();}catch(Exception ignored){return LocalDateTime.parse(raw);}}
 @Override public void onAppWidgetOptionsChanged(Context c,AppWidgetManager m,int id,android.os.Bundle options){WidgetUpdateJob.schedule(c,getClass(),id,new Intent(c,getClass()).setAction(REFRESH));}
 void update(Context context,int onlyId){
  AppWidgetManager manager=AppWidgetManager.getInstance(context);
  int[] ids=manager.getAppWidgetIds(new ComponentName(context,getClass()));
  for(int widgetId:ids){
   if(onlyId!=-1&&onlyId!=widgetId)continue;
   var prefs=context.getSharedPreferences("widget",0);long session=prefs.getLong("session",0);
   var sequence=updates.computeIfAbsent(widgetId,id->new java.util.concurrent.atomic.AtomicLong());long request=sequence.incrementAndGet();
   RemoteViews views=new RemoteViews(context.getPackageName(),R.layout.widget);
   String origin=Api.origin(context),mode=mode();int offset=prefs.getInt("offset-"+widgetId,0);
   LocalDate today=LocalDate.now(ZoneId.of("Asia/Seoul")),anchor=mode.equals("week")?today.plusWeeks(offset):mode.equals("month")?today.plusMonths(offset):today.plusDays(offset);
   int availableWidth=manager.getAppWidgetOptions(widgetId).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH,250);
   boolean compact=availableWidth<240;
   views.setViewVisibility(R.id.now_clock,mode.equals("plan")?android.view.View.VISIBLE:android.view.View.GONE);
   boolean nav=mode.equals("week")||mode.equals("month")||mode.equals("day")||mode.equals("plan")||mode.equals("memo");
   for(int id:new int[]{R.id.previous,R.id.next,R.id.today})views.setViewVisibility(id,nav&&!compact?android.view.View.VISIBLE:android.view.View.GONE);
   views.setOnClickPendingIntent(R.id.previous,navigation(context,widgetId,-1));views.setOnClickPendingIntent(R.id.next,navigation(context,widgetId,1));views.setOnClickPendingIntent(R.id.today,navigation(context,widgetId,0));
   String label=mode.equals("plan")?anchor.format(DateTimeFormatter.ofPattern("M월 d일 E요일",java.util.Locale.KOREAN)):mode.equals("day")?(anchor.equals(today)?"오늘 일정":anchor.format(DateTimeFormatter.ofPattern("M월 d일 일정",java.util.Locale.KOREAN))):mode.equals("week")?"이번 주":mode.equals("month")?"월간":mode.equals("tasks")?"할 일":mode.equals("memo")?"메모":mode.equals("meal")?"학식":mode.equals("recent")?"최근 필기":today.getMonthValue()+"월 "+today.getDayOfMonth()+"일";
   views.setTextViewText(R.id.title,label);
   if(mode.equals("upcoming"))views.setTextViewTextSize(R.id.title,android.util.TypedValue.COMPLEX_UNIT_SP,12);
   views.setViewVisibility(R.id.refresh,compact?android.view.View.GONE:android.view.View.VISIBLE);
   views.setOnClickPendingIntent(R.id.refresh,PendingIntent.getBroadcast(context,widgetId,new Intent(context,getClass()).setAction(REFRESH).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,widgetId),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
   views.setOnClickPendingIntent(R.id.add,PendingIntent.getActivity(context,widgetId,new Intent(context,CaptureActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
   String route=mode.equals("meal")?"/student/meals":mode.equals("recent")?"/today":mode.equals("memo")?"/today":mode.equals("upcoming")?"/today":mode.equals("plan")?"/day":mode.equals("month")?"":"/"+mode;
   views.setOnClickPendingIntent(R.id.title,open(context,origin+(mode.equals("meal")?route:"/personal-project/calendar"+route)+"?date="+anchor,widgetId));
   views.setViewVisibility(R.id.add,mode.equals("upcoming")?android.view.View.GONE:android.view.View.VISIBLE);
   JSONObject cached=null;
   try{JSONObject saved=new JSONObject(prefs.getString("cache-"+widgetId,"{}"));if(!prefs.getBoolean("auth-rejected",false)&&saved.optString("key").equals(mode+anchor))cached=saved.getJSONObject("feed");}catch(Exception ignored){}
   try{
    if(prefs.getBoolean("auth-rejected",false)||Api.token(context).isEmpty()){views.removeAllViews(R.id.events);views.setTextViewText(R.id.status,prefs.getBoolean("auth-rejected",false)?"연결이 해제됐어요. 앱에서 다시 연결해주세요.":"앱에서 계정을 연결해주세요");views.setOnClickPendingIntent(R.id.title,PendingIntent.getActivity(context,99,new Intent(context,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));manager.updateAppWidget(widgetId,views);continue;}
    if(cached!=null)renderFeed(context,views,cached,origin,widgetId,anchor,manager);else views.removeAllViews(R.id.events);
    views.setTextViewText(R.id.status,cached==null?"불러오는 중…":"마지막 일정 · 새로고침 중…");manager.updateAppWidget(widgetId,views);
    String endpoint=mode.equals("meal")?"meals?day="+anchor:mode.equals("recent")?"recent-notes":"feed?view="+(mode.equals("memo")?"day":mode.equals("plan")?"planning":mode)+"&anchor="+anchor;
    JSONObject feed=Api.call(origin,endpoint,Api.token(context),null);
    if(session!=prefs.getLong("session",0)||request!=sequence.get()||prefs.getBoolean("auth-rejected",false))continue;
    renderFeed(context,views,feed,origin,widgetId,anchor,manager);
    prefs.edit().remove("auth-rejected").putString("cache-"+widgetId,new JSONObject().put("key",mode+anchor).put("feed",feed).toString()).apply();
    String actionError=prefs.getString("action-error","");prefs.edit().remove("action-error").apply();
    views.setViewVisibility(R.id.status,(mode.equals("upcoming")||mode.equals("recent"))&&actionError.isEmpty()?android.view.View.GONE:android.view.View.VISIBLE);
    views.setTextViewText(R.id.status,actionError.isEmpty()?LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))+" 업데이트":actionError);
   }catch(Exception error){
    if(session!=prefs.getLong("session",0))continue;
    if(error instanceof Api.ApiError && ((Api.ApiError)error).status==401){boolean firstRejection=markAuthRejected(context);cached=null;views.removeAllViews(R.id.events);views.setTextViewText(R.id.status,"연결이 해제됐어요. 앱에서 다시 연결해주세요.");views.setOnClickPendingIntent(R.id.title,PendingIntent.getActivity(context,99,new Intent(context,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));if(firstRejection)CalendarWidget.refresh(context);}
    else views.setTextViewText(R.id.status,cached==null?"연결을 확인하고 새로고침해주세요.":"연결 실패 · 마지막 일정 표시 · ↻ 재시도");
   }
   views.setViewVisibility(R.id.loading,android.view.View.GONE);
   if(sequence.get()==request)manager.updateAppWidget(widgetId,views);
  }
 }
 void renderFeed(Context c,RemoteViews views,JSONObject feed,String origin,int id,LocalDate anchor,AppWidgetManager manager)throws Exception{
  String mode=mode();views.removeAllViews(R.id.events);
  if(mode.equals("meal")){renderMeal(c,views,feed,origin,id);return;}
  if(mode.equals("recent")){renderRecent(c,views,feed,origin,id,manager);return;}
  JSONArray events=feed.getJSONArray("events");
  int height=manager.getAppWidgetOptions(id).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT,180);
  if(mode.equals("plan")){
   int width=manager.getAppWidgetOptions(id).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH,250);
   RemoteViews columns=new RemoteViews(c.getPackageName(),R.layout.plan_columns);boolean wide=isWidePlan(width);
   columns.setViewVisibility(R.id.plan_tasks,wide?android.view.View.VISIBLE:android.view.View.GONE);
   DayTimetable.render(c,columns,events,origin,id,anchor,height);
   if(wide){JSONArray tasks=feed.optJSONArray("tasks"), captures=feed.optJSONArray("captures");int limit=Math.max(1,(height-90)/44);
    int shownTasks=tasks==null?0:Math.min(tasks.length(),limit);
    renderTasksInto(c,columns,R.id.plan_task_rows,tasks,origin,id,"event",shownTasks);
    renderTasksInto(c,columns,R.id.plan_task_rows,captures,origin,id,"capture",limit-shownTasks);
    if(shownTasks==0&&(captures==null||captures.length()==0)){RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.event);row.setTextViewText(R.id.event,"할 일이 없어요.");columns.addView(R.id.plan_task_rows,row);}
   }
   views.addView(R.id.events,columns);
  }else if(mode.equals("week")){
   int width=manager.getAppWidgetOptions(id).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH,300);
   WeekTimetable.render(c,views,events,origin,id,anchor);
  }
  else if(mode.equals("month"))renderMonth(c,views,events,origin,anchor,height);
  else if(mode.equals("memo")){
   RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.memo_text);String note=feed.optString("note","");row.setInt(R.id.memo_text,"setMaxLines",Math.max(1,Math.min(10,(height-104)/24)));row.setTextViewText(R.id.memo_text,note.isEmpty()?"아직 메모가 없어요. 눌러서 적어보세요.":note);row.setOnClickPendingIntent(R.id.memo_text,open(c,origin+"/personal-project/calendar/today?date="+anchor+"#daily-note",id));views.addView(R.id.events,row);
  }else if(mode.equals("upcoming")){
   if(events.length()>0){JSONObject event=events.getJSONObject(0);RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.next_event);row.setTextViewTextSize(R.id.event_name,android.util.TypedValue.COMPLEX_UNIT_SP,height<170?18:20);row.setViewVisibility(R.id.event_location,height<170?android.view.View.GONE:android.view.View.VISIBLE);row.setTextViewText(R.id.event_name,event.getString("title"));row.setTextViewText(R.id.event_time,event.optBoolean("timeUnspecified")?"시간 미정":event.optBoolean("isAllDay")?"종일":local(event,"startTime").format(DateTimeFormatter.ofPattern("HH:mm"))+(event.isNull("endTime")?"":"–"+local(event,"endTime").format(DateTimeFormatter.ofPattern("HH:mm"))));row.setTextViewText(R.id.event_location,event.optString("location","").equals("null")?"":event.optString("location",""));row.setOnClickPendingIntent(R.id.event_card,open(c,origin+"/personal-project/calendar?event="+event.getInt("id"),event.getInt("id")));views.addView(R.id.events,row);}else empty(c,views,"예정된 일정이 없어요.");
  }else if(mode.equals("tasks")){
   JSONArray captures=feed.optJSONArray("captures");int budget=Math.max(1,(height-80)/44);int eventBudget=captures!=null&&captures.length()>0?Math.max(0,budget-1):budget;int shown=Math.min(eventBudget,events.length());renderTasks(c,views,events,origin,id,"event",shown);renderTasks(c,views,captures,origin,id,"capture",budget-shown);if(events.length()==0&&(feed.optJSONArray("captures")==null||feed.getJSONArray("captures").length()==0))empty(c,views,"남은 할 일이 없어요.");
  }else{
   int shown=Math.min(events.length(),Math.max(1,Math.min(4,(height-104)/30)));
   if(events.length()==0)empty(c,views,"오늘 예정된 일정이 없어요.");else renderRows(c,views,events,origin,"일정",shown);
   int spare=height-80-(events.length()==0?44:26+shown*26);
   if(spare>=44)renderTasks(c,views,feed.optJSONArray("captures"),origin,id,"capture",Math.min(2,spare/44));
  }
 }
 static String mealPeriod(int hour){return hour<10?"breakfast":hour<15?"lunch":"dinner";}
 void renderMeal(Context c,RemoteViews views,JSONObject feed,String origin,int id)throws Exception{
  String selected=c.getSharedPreferences("widget",0).getString("meal-restaurant","");
  String period=mealPeriod(LocalTime.now(ZoneId.of("Asia/Seoul")).getHour());
  String label=period.equals("breakfast")?"아침":period.equals("lunch")?"점심":"저녁";
  views.setTextViewText(R.id.title,label+" · 학식");
  JSONArray restaurants=feed.optJSONArray("restaurants");JSONObject chosen=null;
  if(restaurants!=null)for(int i=0;i<restaurants.length();i++){JSONObject r=restaurants.optJSONObject(i);if(r!=null&&selected.equals(r.optString("title"))){chosen=r;break;}}
  RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.event);
  String content=!feed.optBoolean("supported",true)?"학교 식단을 지원하지 않아요":selected.isEmpty()?"앱에서 식당을 선택해주세요":chosen==null?"선택한 식당의 메뉴가 없어요":selected+"\n"+(chosen.optString(period,"").isBlank()?"제공되는 식단이 없어요":chosen.optString(period));
  row.setTextViewText(R.id.event,content);row.setOnClickPendingIntent(R.id.event,PendingIntent.getActivity(c,id,new Intent(c,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));views.addView(R.id.events,row);
 }
 void renderRecent(Context c,RemoteViews views,JSONObject feed,String origin,int id,AppWidgetManager manager)throws Exception{
  JSONArray notes=feed.optJSONArray("notes");if(notes==null||notes.length()==0){empty(c,views,"최근에 저장한 노트가 없어요.");return;}
  int height=manager.getAppWidgetOptions(id).getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT,180);
  int count=Math.min(notes.length(),Math.max(1,(height-70)/30));for(int i=0;i<count;i++){
   JSONObject note=notes.getJSONObject(i);String nid=note.optString("id");if(nid.isEmpty())continue;
   RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.day_event);row.setTextViewText(R.id.event,note.optString("title","제목 없는 노트"));
   String link=origin+"/personal-project/notes?note="+Uri.encode(nid);row.setOnClickPendingIntent(R.id.event,open(c,link,nid.hashCode()));views.addView(R.id.events,row);
  }
 }
 void renderCompactWeek(Context c,RemoteViews views,JSONArray events,String origin,int height)throws Exception{
  int limit=Math.max(1,Math.min(6,(height-75)/30));
  if(events.length()==0){empty(c,views,"이번 주 일정이 없어요.");return;}
  for(int i=0;i<Math.min(limit,events.length());i++){
   JSONObject event=events.getJSONObject(i);LocalDateTime start=local(event,"startTime");
   RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.day_event);
   row.setTextViewText(R.id.event,start.format(DateTimeFormatter.ofPattern("M.d HH:mm "))+event.getString("title"));
   row.setOnClickPendingIntent(R.id.event,open(c,origin+"/personal-project/calendar/day?date="+start.toLocalDate()+"&event="+event.getInt("id"),event.getInt("id")));
   views.addView(R.id.events,row);
  }
 }
 void empty(Context c,RemoteViews views,String text){RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.event);row.setTextViewText(R.id.event,text);views.addView(R.id.events,row);}
 void renderTasks(Context c,RemoteViews views,JSONArray items,String origin,int widgetId,String source,int limit)throws Exception{
  renderTasksInto(c,views,R.id.events,items,origin,widgetId,source,limit);
 }
 void renderTasksInto(Context c,RemoteViews views,int container,JSONArray items,String origin,int widgetId,String source,int limit)throws Exception{
  if(items==null)return;
  for(int i=0;i<Math.min(limit,items.length());i++){
   JSONObject item=items.getJSONObject(i);String id=item.getString("id"),title=source.equals("capture")?item.getString("text"):item.getString("title");
   RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.task);row.setTextViewText(R.id.task_title,title);row.setContentDescription(R.id.task_check,title+" 완료");
   boolean editable=source.equals("capture")||(item.optBoolean("canEdit",true)&&!item.optString("completionSource").equals("external"));
   if(editable)row.setOnClickPendingIntent(R.id.task_check,PendingIntent.getBroadcast(c,(source+id).hashCode(),new Intent(c,getClass()).setAction(COMPLETE).setData(Uri.parse("netaq-widget://complete/"+widgetId+"/"+source+"/"+id)).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,widgetId).putExtra("source",source).putExtra("taskId",id),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
   else row.setTextViewText(R.id.task_check,"–");
   row.setOnClickPendingIntent(R.id.task_title,open(c,origin+"/personal-project/calendar/"+(source.equals("capture")?"inbox":"tasks?event="+id),id.hashCode()));views.addView(container,row);
  }
 }
 static String place(JSONObject e){String p=e.optString("location","");return p.isEmpty()||p.equals("null")?"":" · "+p;}
 void renderRows(Context c,RemoteViews views,JSONArray events,String origin,String label,int limit)throws Exception{
  RemoteViews heading=new RemoteViews(c.getPackageName(),R.layout.day_event);heading.setTextViewText(R.id.event,label+" · "+events.length()+"개");views.addView(R.id.events,heading);
  for(int i=0;i<Math.min(limit,events.length());i++){
   JSONObject e=events.getJSONObject(i);RemoteViews row=new RemoteViews(c.getPackageName(),R.layout.day_event);
   row.setTextViewText(R.id.event,(label.equals("할 일")?"□ ":local(e,"startTime").format(DateTimeFormatter.ofPattern(e.optBoolean("isAllDay")?"'종일 '":"HH:mm ")))+e.getString("title")+place(e));
   row.setOnClickPendingIntent(R.id.event,open(c,origin+"/personal-project/calendar/day?date="+local(e,"startTime").toLocalDate()+"&event="+e.getInt("id"),e.getInt("id")));views.addView(R.id.events,row);
  }
 }
 void renderMonth(Context c,RemoteViews views,JSONArray events,String origin,LocalDate anchor,int height)throws Exception{
  LocalDate first=anchor.withDayOfMonth(1), day=first.minusDays(first.getDayOfWeek().getValue()%7);
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
    boolean current=day.getMonth()==first.getMonth();boolean isToday=day.equals(LocalDate.now(ZoneId.of("Asia/Seoul")));
    row.setTextViewText(cells[col],current?day.getDayOfMonth()+(count>0?"\n"+(count==1?"━":count==2?"━━":"━━ +"+(count-2)):""):"");
    row.setTextColor(cells[col],isToday?0xffffffff:col==0?0xffc4412c:col==6?0xff52749d:0xff242529);
    if(current&&isToday)row.setInt(cells[col],"setBackgroundResource",R.drawable.month_today);
    row.setOnClickPendingIntent(cells[col],open(c,origin+"/personal-project/calendar/day?date="+day,day.hashCode()));
   }
   views.addView(R.id.events,row);
  }
  if(height>=340){
   LocalDate today=LocalDate.now(ZoneId.of("Asia/Seoul"));
   for(int i=0;i<events.length();i++){
    JSONObject event=events.getJSONObject(i);LocalDateTime start=local(event,"startTime");
    LocalDateTime end=event.isNull("endTime")?start.plusMinutes(1):local(event,"endTime");
    if(start.isBefore(today.plusDays(1).atStartOfDay())&&end.isAfter(today.atStartOfDay())){
     RemoteViews summary=new RemoteViews(c.getPackageName(),R.layout.day_event);
     summary.setTextViewText(R.id.event,"오늘 · "+event.getString("title"));
     summary.setOnClickPendingIntent(R.id.event,open(c,origin+"/personal-project/calendar/day?date="+today+"&event="+event.getInt("id"),event.getInt("id")));
     views.addView(R.id.events,summary);break;
    }
   }
  }
 }
}
