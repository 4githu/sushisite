package app.chobab.widget;

import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;
import android.widget.*;
import org.json.JSONObject;

public class MainActivity extends Activity {
 static final int VERTICAL = LinearLayout.VERTICAL;
 @Override public void onCreate(Bundle b){super.onCreate(b);LinearLayout root=new LinearLayout(this);root.setOrientation(VERTICAL);root.setPadding(32,80,32,32);root.setBackgroundColor(0xfff8fafc);TextView title=new TextView(this);title.setText("온도 캘린더 위젯");title.setTextSize(24);root.addView(title);TextView help=new TextView(this);help.setText("웹앱의 연결·공유 → 안드로이드 위젯 연결에서 코드를 발급한 후 입력하세요.\n\n코드를 발급한 서비스 주소를 선택하세요.");help.setPadding(0,24,0,24);root.addView(help);Spinner sites=new Spinner(this);sites.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,Api.ORIGINS));for(int i=0;i<Api.ORIGINS.length;i++)if(Api.ORIGINS[i].equals(Api.origin(this)))sites.setSelection(i);root.addView(sites);EditText code=new EditText(this);code.setSingleLine(true);code.setHint("5분 연결 코드");root.addView(code);Button connect=new Button(this);connect.setText("계정 연결");root.addView(connect);TextView result=new TextView(this);root.addView(result);Button pin=new Button(this);pin.setText("홈 화면에 위젯 추가");root.addView(pin);pin.setOnClickListener(v->{AppWidgetManager manager=AppWidgetManager.getInstance(this);if(manager.isRequestPinAppWidgetSupported())manager.requestPinAppWidget(new ComponentName(this,CalendarWidget.class),null,null);else result.setText("홈 화면을 길게 누른 후 위젯 → 온도 위젯을 선택하세요.");});Button disconnect=new Button(this);disconnect.setText("이 기기 연결 해제");root.addView(disconnect);disconnect.setOnClickListener(v->{getSharedPreferences("widget",0).edit().remove("token").apply();CalendarWidget.refresh(this);result.setText("기기에서 연결 정보를 지웠습니다. 웹앱에서 ‘위젯 연결 모두 해제’하면 서버 접근 권한도 폐기됩니다.");});connect.setOnClickListener(v->{String token=code.getText().toString().trim(),origin=sites.getSelectedItem().toString();if(token.length()<16){result.setText("연결 코드를 입력해주세요.");return;}connect.setEnabled(false);new Thread(()->{String message;try{JSONObject response=Api.call(origin,"claim","",new JSONObject().put("token",token));Api.save(this,origin,response.getString("token"));CalendarWidget.refresh(this);message="연결했습니다. 홈 화면에 위젯을 추가하세요.";}catch(Exception e){message=e.getMessage();}String finalMessage=message;runOnUiThread(()->{result.setText(finalMessage);connect.setEnabled(true);code.setText("");});}).start();});setContentView(root);}
}
