package app.chobab.widget;
import android.app.job.*;
public class ReminderJob extends JobService {
 @Override public boolean onStartJob(JobParameters parameters){new Thread(()->{boolean retry=false;try{ReminderReceiver.sync(this);CalendarWidget.refresh(this);}catch(Exception ignored){retry=true;}jobFinished(parameters,retry);}).start();return true;}
 @Override public boolean onStopJob(JobParameters parameters){return true;}
}
