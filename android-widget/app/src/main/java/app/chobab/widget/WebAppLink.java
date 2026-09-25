package app.chobab.widget;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;

/** Prefer the installed, URL-scoped web app over a generic browser. */
final class WebAppLink {
 static Intent intent(Context context,String url){
  Uri uri=Uri.parse(url);
  Intent intent=new Intent(Intent.ACTION_VIEW,uri).addCategory(Intent.CATEGORY_BROWSABLE)
   .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
  // Prefer NETAQ when Aura and Calendar have overlapping historical PWA scopes.
  ResolveInfo best=null;int bestScore=-1;
  for(ResolveInfo candidate:context.getPackageManager().queryIntentActivities(intent,PackageManager.MATCH_DEFAULT_ONLY|PackageManager.GET_RESOLVED_FILTER)){
   if(candidate.filter==null||candidate.filter.countDataAuthorities()==0||candidate.activityInfo==null)continue;
   if(candidate.filter.matchDataAuthority(uri)<0)continue;
   int score=0;
   try{
    android.os.Bundle data=context.getPackageManager().getApplicationInfo(candidate.activityInfo.packageName,PackageManager.GET_META_DATA).metaData;
    String start=data==null?null:data.getString("org.chromium.webapk.shell_apk.startUrl");
    if(start!=null){
     Uri app=Uri.parse(start);String path=app.getPath();
     if(!java.util.Objects.equals(uri.getAuthority(),app.getAuthority())||path==null)continue;
     if(!uri.getPath().equals(path)&&!uri.getPath().startsWith(path.endsWith("/")?path:path+"/"))continue;
     score=100+path.length();
    }
   }catch(PackageManager.NameNotFoundException ignored){continue;}
   if(score>bestScore){bestScore=score;best=candidate;}
  }
  if(best!=null)intent.setComponent(new android.content.ComponentName(best.activityInfo.packageName,best.activityInfo.name));
  return intent;
 }
}
