package app.chobab.widget;

import android.Manifest;
import android.app.*;
import android.app.job.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.*;
import java.time.*;

public class ReminderReceiver extends BroadcastReceiver {
 static final String CHANNEL="calendar-reminders";
 static final int JOB=8100;
 static void periodic(Context c,boolean enabled){
  JobScheduler jobs=c.getSystemService(JobScheduler.class);
  if(enabled)jobs.schedule(new JobInfo.Builder(JOB,new ComponentName(c,ReminderJob.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(30*60*1000L).setPersisted(true).build());
  else { jobs.cancel(JOB); cancel(c); c.getSystemService(NotificationManager.class).cancelAll(); }
 }
 static PendingIntent alarm(Context c,int id,Intent intent){return PendingIntent.getBroadcast(c,id,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
 static void cancel(Context c){
  AlarmManager manager=c.getSystemService(AlarmManager.class);
  for(String value:c.getSharedPreferences("widget",0).getString("alarmIds","").split(","))try{manager.cancel(alarm(c,Integer.parseInt(value),new Intent(c,ReminderReceiver.class)));}catch(Exception ignored){}
  c.getSharedPreferences("widget",0).edit().remove("alarmIds").apply();
 }
 static synchronized void sync(Context c)throws Exception{
  var prefs=c.getSharedPreferences("widget",0);
  if(!prefs.getBoolean("reminders",false))return;
  String token=Api.token(c);if(token.isEmpty()){cancel(c);return;}
  JSONArray events=Api.call(Api.origin(c),"feed",token,null).getJSONArray("events");
  cancel(c);StringBuilder ids=new StringBuilder();long now=System.currentTimeMillis();
  AlarmManager manager=c.getSystemService(AlarmManager.class);
  for(int i=0;i<events.length();i++){
   JSONObject e=events.getJSONObject(i);if(e.optBoolean("isAllDay"))continue;
   long at=CalendarWidget.local(e,"startTime").atZone(ZoneId.of("Asia/Seoul")).toInstant().toEpochMilli();
   int id=e.getInt("id");String key=id+"@"+at;
   if(at<=now || prefs.getLong("fired-"+id,0)==at)continue;
   Intent intent=new Intent(c,ReminderReceiver.class).putExtra("id",id).putExtra("title",e.getString("title")).putExtra("start",at);
   manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,Math.max(now+1000,at-10*60*1000L),alarm(c,id,intent));
   ids.append(id).append(',');
  }
  prefs.edit().putString("alarmIds",ids.toString()).apply();
 }
 @Override public void onReceive(Context c,Intent intent){
  if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())){periodic(c,c.getSharedPreferences("widget",0).getBoolean("reminders",false));return;}
  var prefs=c.getSharedPreferences("widget",0);
  if(!prefs.getBoolean("reminders",false)||!prefs.contains("token"))return;
  if(Build.VERSION.SDK_INT>=33 && c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;
  int id=intent.getIntExtra("id",0);long start=intent.getLongExtra("start",0);
  if(start<System.currentTimeMillis()-5*60*1000L)return;
  NotificationManager manager=c.getSystemService(NotificationManager.class);
  manager.createNotificationChannel(new NotificationChannel(CHANNEL,"일정 알림",NotificationManager.IMPORTANCE_DEFAULT));
  Notification notice=new Notification.Builder(c,CHANNEL).setSmallIcon(R.drawable.ic_calendar).setContentTitle(intent.getStringExtra("title")).setContentText("곧 시작할 일정이 있습니다.").setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).setContentIntent(CalendarWidget.open(c,Api.origin(c)+"/personal-project/calendar?event="+id,id)).build();
  manager.notify(id,notice);prefs.edit().putLong("fired-"+id,start).apply();
 }
}
