package app.chobab.widget;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;

/** Standalone fallback when no installed WebAPK handles the calendar URL. */
public class WebAppActivity extends Activity {
 private WebView web;
 private ValueCallback<Uri[]> upload;
 private boolean trusted(Uri uri){return uri!=null&&"https".equals(uri.getScheme())&&Api.allowed("https://"+uri.getAuthority());}
 private void load(Intent intent){Uri uri=intent.getData();if(trusted(uri))web.loadUrl(uri.toString());else finish();}
 @Override public void onCreate(Bundle state){
  super.onCreate(state);
  LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
  TextView help=new TextView(this);help.setText("NETAQ · 앱 화면  |  처음에는 한 번 로그인해주세요");help.setTextSize(11);help.setPadding(20,14,20,14);root.addView(help);
  web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
  web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
  CookieManager.getInstance().setAcceptCookie(true);
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
    Uri uri=request.getUrl();if(trusted(uri))return false;
    if(request.isForMainFrame()&&("https".equals(uri.getScheme())||"http".equals(uri.getScheme()))){try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(android.content.ActivityNotFoundException ignored){Toast.makeText(WebAppActivity.this,"링크를 열 앱이 없습니다.",Toast.LENGTH_SHORT).show();}}
    return true;
   }
   @Override public void onPageFinished(WebView view,String url){CookieManager.getInstance().flush();}
   @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame()){help.setText("연결을 확인한 뒤 여기를 눌러 다시 시도해주세요");help.setOnClickListener(v->web.reload());}}
  });
  web.setWebChromeClient(new WebChromeClient(){
   @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
    if(upload!=null)upload.onReceiveValue(null);upload=callback;
    try{startActivityForResult(params.createIntent(),20);}catch(android.content.ActivityNotFoundException e){upload.onReceiveValue(null);upload=null;}return true;
   }
  });
  web.setDownloadListener((url,ua,disposition,mime,length)->{Uri uri=Uri.parse(url);if(trusted(uri))try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(android.content.ActivityNotFoundException ignored){}});
  if(state==null||web.restoreState(state)==null)load(getIntent());
 }
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==20&&upload!=null){upload.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));upload=null;}}
 @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);load(intent);}
 @Override protected void onSaveInstanceState(Bundle state){web.saveState(state);super.onSaveInstanceState(state);}
 @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
 @Override protected void onDestroy(){if(upload!=null)upload.onReceiveValue(null);web.destroy();super.onDestroy();}
}
