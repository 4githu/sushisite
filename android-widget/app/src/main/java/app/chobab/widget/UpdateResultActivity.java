package app.chobab.widget;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.os.Bundle;
import android.widget.Toast;

/** Receives the system installer's confirmation or result for an in-app update. */
public final class UpdateResultActivity extends Activity {
 @Override protected void onCreate(Bundle state){super.onCreate(state);handle(getIntent());}
 @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);handle(intent);}
 private void handle(Intent intent){
  int result=intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE);
  if(result==PackageInstaller.STATUS_PENDING_USER_ACTION){
   Intent confirm=intent.getParcelableExtra(Intent.EXTRA_INTENT);
   if(confirm!=null){startActivity(confirm);finish();return;}
  }
  if(result!=PackageInstaller.STATUS_SUCCESS)Toast.makeText(this,"업데이트가 완료되지 않았어요. 앱에서 다시 시도해주세요.",Toast.LENGTH_LONG).show();
  finish();
 }
}
