package app.chobab.widget;

import android.app.job.*;
import android.content.*;
import android.os.PersistableBundle;
import org.json.JSONObject;

/** Network work belongs to a JobService, not a receiver's ten-second lifetime. */
public class WidgetUpdateJob extends JobService {
 static void schedule(Context c,Class<?> provider,int widgetId,Intent action){
  PersistableBundle extras=new PersistableBundle();extras.putString("provider",provider.getName());extras.putInt("widgetId",widgetId);
  boolean completing=CalendarWidget.COMPLETE.equals(action.getAction());
  if(completing){extras.putString("source",action.getStringExtra("source"));extras.putString("taskId",action.getStringExtra("taskId"));}
  int key=10000+(java.util.Objects.hash(provider.getName(),widgetId)&0x3fffffff);
  if(completing)key=20000+(java.util.Objects.hash(provider.getName(),action.getStringExtra("source"),action.getStringExtra("taskId"))&0x3fffffff);
  c.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(key,new ComponentName(c,WidgetUpdateJob.class)).setExtras(extras).setOverrideDeadline(0).build());
 }
 @Override public boolean onStartJob(JobParameters params){
  new Thread(()->{try{
   PersistableBundle e=params.getExtras();Class<?> provider=null;
   for(Class<?> candidate:CalendarWidget.PROVIDERS)if(candidate.getName().equals(e.getString("provider")))provider=candidate;
   if(provider==null)return;
   CalendarWidget widget=(CalendarWidget)provider.getDeclaredConstructor().newInstance();
   String task=e.getString("taskId");
   if(task!=null){
    try{Api.call(Api.origin(this),"task",Api.token(this),new JSONObject().put("source",e.getString("source")).put("id",task).put("done",true));CalendarWidget.refresh(this);}
    catch(Api.ApiError error){if(error.status==401){if(CalendarWidget.markAuthRejected(this))CalendarWidget.refresh(this);}else getSharedPreferences("widget",0).edit().putString("action-error","완료하지 못했어요. 다시 눌러주세요.").apply();}
    catch(Exception error){getSharedPreferences("widget",0).edit().putString("action-error","완료 상태를 확인하지 못했어요. 새로고침하거나 다시 눌러주세요.").apply();}
   }
   widget.update(this,e.getInt("widgetId",-1));
  }catch(Exception ignored){}finally{jobFinished(params,false);}}).start();return true;
 }
 @Override public boolean onStopJob(JobParameters params){return false;}
}
