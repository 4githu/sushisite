package app.chobab.widget;
import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.widget.*;
import org.json.JSONObject;

/** A small native capture surface; no date or category is required. */
public class CaptureActivity extends Activity {
 String id;long ownerSession;EditText input;TextView status;Button save;
 int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
 @Override public void onCreate(Bundle state){super.onCreate(state);var prefs=getSharedPreferences("widget",0);ownerSession=prefs.getLong("session",0);id=state!=null?state.getString("id"):prefs.getString("capture-id",java.util.UUID.randomUUID().toString());
  LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(24),dp(48),dp(24),dp(24));root.setBackgroundColor(0xffffffff);
  TextView title=new TextView(this);title.setText("빠른 기록");title.setTextSize(24);title.setTextColor(0xff242529);root.addView(title);
  input=new EditText(this);input.setHint("떠오른 내용을 적어두세요");input.setGravity(android.view.Gravity.TOP);input.setMinLines(5);input.setTextSize(17);input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(2000)});input.setText(state!=null?state.getString("text",""):prefs.getString("capture-draft",""));root.addView(input,new LinearLayout.LayoutParams(-1,dp(200)));
  status=new TextView(this);status.setMinHeight(dp(48));status.setTextSize(13);status.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(status);
  save=new Button(this);save.setText("정리함에 기록");save.setMinHeight(dp(48));root.addView(save);
  Button open=new Button(this);open.setText("정리함 보기");root.addView(open);open.setOnClickListener(v->startActivity(WebAppLink.intent(this,Api.origin(this)+"/personal-project/calendar/inbox")));
  save.setOnClickListener(v->{String text=input.getText().toString().trim();if(text.isEmpty()){status.setText("내용을 입력해주세요.");return;}save.setEnabled(false);input.setEnabled(false);status.setText("저장 중…");long expectedSession=ownerSession;new Thread(()->{boolean ok=false;String message;try{Api.call(Api.origin(this),"capture",Api.token(this),new JSONObject().put("id",id).put("text",text));ok=true;message="정리함에 기록했어요.";}catch(Exception e){message=e.getMessage();}boolean success=ok;String result=message;runOnUiThread(()->{if(expectedSession!=prefs.getLong("session",0)){save.setEnabled(true);input.setEnabled(true);return;}if(success){input.setText("");id=java.util.UUID.randomUUID().toString();prefs.edit().remove("capture-draft").remove("capture-id").apply();}status.setText(result);save.setEnabled(true);input.setEnabled(true);});}).start();});
  setContentView(root);input.requestFocus();getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
 }
 @Override protected void onResume(){super.onResume();long current=getSharedPreferences("widget",0).getLong("session",0);if(input!=null&&current!=ownerSession){input.setText("");id=java.util.UUID.randomUUID().toString();ownerSession=current;status.setText("계정 연결이 바뀌었어요. 새로 기록해주세요.");}}
 @Override protected void onPause(){super.onPause();var prefs=getSharedPreferences("widget",0);if(ownerSession!=prefs.getLong("session",0)||!prefs.contains("token"))return;var edit=prefs.edit();if(input.getText().length()>0)edit.putString("capture-draft",input.getText().toString()).putString("capture-id",id);else edit.remove("capture-draft").remove("capture-id");edit.apply();}
 @Override protected void onSaveInstanceState(Bundle state){state.putString("id",id);state.putString("text",input.getText().toString());super.onSaveInstanceState(state);}
}
