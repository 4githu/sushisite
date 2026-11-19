package app.chobab.widget;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.TextView;
import java.net.HttpURLConnection;
import java.net.URL;

/** Stream the official update into the system installer, without a Downloads-folder APK. */
final class UpdateInstaller {
 static void start(Activity activity, TextView status){
  if(!activity.getPackageManager().canRequestPackageInstalls()){
   status.setText("업데이트 설치를 허용한 뒤 다시 눌러주세요.");
   activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.getPackageName())));return;
  }
  status.setText("업데이트를 준비하고 있어요…");
  new Thread(()->{
   int id=-1;HttpURLConnection connection=null;PackageInstaller.Session session=null;
   try{
    connection=(HttpURLConnection)new URL("https://netaq.chobab.app/downloads/android-widget").openConnection();
    connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(7000);connection.setReadTimeout(12000);
    if(connection.getResponseCode()!=200)throw new Exception("설치 파일을 받지 못했어요.");
    PackageInstaller installer=activity.getPackageManager().getPackageInstaller();
    PackageInstaller.SessionParams params=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
    params.setAppPackageName(activity.getPackageName());
    id=installer.createSession(params);session=installer.openSession(id);
    try(java.io.InputStream in=connection.getInputStream();java.io.OutputStream out=session.openWrite("netaq-update.apk",0,-1)){
     byte[] buffer=new byte[16384];int n;long total=0;while((n=in.read(buffer))!=-1){total+=n;if(total>30L*1024*1024)throw new Exception("설치 파일이 너무 커요.");out.write(buffer,0,n);}if(total==0)throw new Exception("설치 파일이 비어 있어요.");session.fsync(out);
    }
    Intent callback=new Intent(activity,UpdateResultActivity.class).setAction("app.chobab.widget.UPDATE_RESULT");
    int flags=PendingIntent.FLAG_UPDATE_CURRENT|(Build.VERSION.SDK_INT>=31?PendingIntent.FLAG_MUTABLE:0);
    PendingIntent pending=PendingIntent.getActivity(activity,id,callback,flags);
    session.commit(pending.getIntentSender());session.close();session=null;id=-1;
    activity.runOnUiThread(()->status.setText("시스템 설치 화면에서 업데이트를 확인해주세요."));
   }catch(Exception e){
    if(session!=null)session.close();if(id>=0)try{activity.getPackageManager().getPackageInstaller().abandonSession(id);}catch(Exception ignored){}
    activity.runOnUiThread(()->status.setText("업데이트를 준비하지 못했어요. 인터넷 연결을 확인하고 다시 시도해주세요."));
   }finally{if(connection!=null)connection.disconnect();}
  }).start();
 }
}
