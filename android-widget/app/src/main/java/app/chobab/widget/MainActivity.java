package app.chobab.widget;
import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.*;
import android.os.Bundle;
import android.widget.*;
import org.json.JSONObject;

public class MainActivity extends Activity {
 Switch reminderToggle;TextView result;Button connect,pin;EditText code;
 int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
 TextView text(String value,int size){TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(0xff242529);view.setPadding(0,dp(10),0,dp(10));return view;}
 Button button(String value){Button b=new Button(this);b.setText(value);b.setMinHeight(dp(48));return b;}
 @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==1&&(results.length==0||results[0]!=android.content.pm.PackageManager.PERMISSION_GRANTED)){reminderToggle.setChecked(false);result.setText("알림 권한을 허용해야 일정 알림을 받을 수 있어요.");}}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(24),dp(48),dp(24),dp(32));root.setBackgroundColor(0xffffffff);
  root.addView(text("NETAQ 위젯",26));root.addView(text("다음 일정, 오늘 할 일과 메모를 홈 화면에서 확인하세요.",15));
  root.addView(text("처음 한 번 연결 코드를 발급해 이 기기를 연결하세요. 위젯에서 일정을 누르면 설치된 NETAQ 웹앱이 열립니다. 웹앱이 없으면 앱 화면이 열리며, 처음에 로그인이 필요할 수 있어요.",13));
  Button pairPage=button("연결 코드 받기");root.addView(pairPage);pairPage.setOnClickListener(v->startActivity(WebAppLink.intent(this,"https://netaq.chobab.app/personal-project/calendar/widgets")));
  root.addView(text("1. 서비스 계정 연결",18));Spinner sites=new Spinner(this);sites.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,Api.ORIGINS));for(int i=0;i<Api.ORIGINS.length;i++)if(Api.ORIGINS[i].equals(Api.origin(this)))sites.setSelection(i);root.addView(sites);
  code=new EditText(this);code.setSingleLine(true);code.setHint("5분 연결 코드");code.setTextSize(16);code.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS|android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);root.addView(code);
  connect=button("계정 연결");root.addView(connect);result=text("",13);result.setMinHeight(dp(64));result.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(result);if(!getSharedPreferences("widget",0).getString("token","").isEmpty()&&!getSharedPreferences("widget",0).getBoolean("auth-rejected",false))result.setText("이 기기는 이미 연결되어 있어요. 업데이트할 때 연결 코드를 다시 입력하지 않아도 돼요.");
  if(!getSharedPreferences("widget",0).getString("token","").isEmpty()&&!getSharedPreferences("widget",0).getBoolean("auth-rejected",false)){
   pairPage.setVisibility(android.view.View.GONE);sites.setVisibility(android.view.View.GONE);code.setVisibility(android.view.View.GONE);connect.setVisibility(android.view.View.GONE);
   Button reconnect=button("다른 계정 연결");root.addView(reconnect);reconnect.setOnClickListener(v->{pairPage.setVisibility(android.view.View.VISIBLE);sites.setVisibility(android.view.View.VISIBLE);code.setVisibility(android.view.View.VISIBLE);connect.setVisibility(android.view.View.VISIBLE);reconnect.setVisibility(android.view.View.GONE);});
  }
  root.addView(text("2. 홈 화면에 위젯 추가",18));Spinner modes=new Spinner(this);modes.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"다음 일정 · 2×2","오늘 일정 · 4×2","주간 시간표","월간 캘린더 · 4×4","할 일 · 완료 체크","일별 계획","이어 쓰는 메모","학식","최근 필기"}));root.addView(modes);
  Class<?>[] choices={NextWidget.class,DayWidget.class,WeekWidget.class,MonthWidget.class,TodoWidget.class,PlanWidget.class,MemoWidget.class,MealWidget.class,RecentNotesWidget.class};
  pin=button("홈 화면에 추가");root.addView(pin);pin.setOnClickListener(v->{AppWidgetManager manager=AppWidgetManager.getInstance(this);if(manager.isRequestPinAppWidgetSupported())manager.requestPinAppWidget(new ComponentName(this,choices[modes.getSelectedItemPosition()]),null,null);else result.setText("홈 화면을 길게 누르고 위젯 → NETAQ를 선택해주세요.");});
  root.addView(text("학식 식당 선택",18));
  Spinner restaurants=new Spinner(this);String savedRestaurant=getSharedPreferences("widget",0).getString("meal-restaurant","");
  java.util.ArrayList<String> names=new java.util.ArrayList<>();names.add(savedRestaurant.isEmpty()?"식당 목록 불러오기":savedRestaurant);
  ArrayAdapter<String> menuAdapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,names);restaurants.setAdapter(menuAdapter);root.addView(restaurants);
  restaurants.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> a){} public void onItemSelected(android.widget.AdapterView<?> a,android.view.View v,int position,long id){String value=names.get(position);if(!value.equals("식당 목록 불러오기")){getSharedPreferences("widget",0).edit().putString("meal-restaurant",value).apply();CalendarWidget.refresh(MainActivity.this);}}});
  Button loadRestaurants=button("식당 목록 불러오기");root.addView(loadRestaurants);loadRestaurants.setOnClickListener(v->{loadRestaurants.setEnabled(false);new Thread(()->{try{
   String day=java.time.LocalDate.now(java.time.ZoneId.of("Asia/Seoul")).toString();JSONObject data=Api.call(Api.origin(this),"meals?day="+day,Api.token(this),null);org.json.JSONArray rows=data.optJSONArray("restaurants");java.util.ArrayList<String> loaded=new java.util.ArrayList<>();
   if(rows!=null)for(int i=0;i<rows.length();i++){String value=rows.getJSONObject(i).optString("title","");if(!value.isEmpty()&&!loaded.contains(value))loaded.add(value);}
   runOnUiThread(()->{loadRestaurants.setEnabled(true);if(loaded.isEmpty()){result.setText("식당 목록이 없어요. 학교 설정과 연결을 확인해주세요.");return;}String old=getSharedPreferences("widget",0).getString("meal-restaurant","");names.clear();names.add("식당 목록 불러오기");names.addAll(loaded);menuAdapter.notifyDataSetChanged();int index=names.indexOf(old);restaurants.setSelection(index<0?0:index);result.setText("식당을 선택하면 학식 위젯에 반영돼요.");});
  }catch(Exception e){runOnUiThread(()->{loadRestaurants.setEnabled(true);result.setText("식당 목록을 불러오지 못했어요. 연결을 확인해주세요.");});}}).start();});
  Button update=button("위젯 업데이트 확인");root.addView(update);
  new Thread(()->{java.net.HttpURLConnection c=null;try{c=(java.net.HttpURLConnection)new java.net.URL("https://netaq.chobab.app/downloads/widget-version").openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(3500);c.setReadTimeout(4500);if(c.getResponseCode()==200){try(java.io.InputStream in=c.getInputStream()){java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] bytes=new byte[1024];int n;while((n=in.read(bytes))!=-1){out.write(bytes,0,n);if(out.size()>4096)throw new java.io.IOException("response too large");}JSONObject versions=new JSONObject(new String(out.toByteArray(),java.nio.charset.StandardCharsets.UTF_8));if(versions.getJSONObject("android").getInt("code")>getPackageManager().getPackageInfo(getPackageName(),0).versionCode)runOnUiThread(()->update.setText("새 버전 받기"));}}}catch(Exception ignored){}finally{if(c!=null)c.disconnect();}}).start();update.setOnClickListener(v->UpdateInstaller.start(this,result));
  Button capture=button("빠른 기록");root.addView(capture);capture.setOnClickListener(v->startActivity(new Intent(this,CaptureActivity.class)));
  reminderToggle=new Switch(this);reminderToggle.setText("시작 10분 전 일정 알림");reminderToggle.setMinHeight(dp(48));reminderToggle.setChecked(getSharedPreferences("widget",0).getBoolean("reminders",false));root.addView(reminderToggle);
  root.addView(text("위젯은 약 30분마다 갱신해요. ↻ 버튼으로 바로 새로고침할 수 있어요. 절전 상태에서는 갱신과 알림이 늦어질 수 있어요.",12));
  reminderToggle.setOnCheckedChangeListener((button,checked)->{getSharedPreferences("widget",0).edit().putBoolean("reminders",checked).apply();if(checked&&android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},1);ReminderReceiver.periodic(this,checked);if(checked)new Thread(()->{try{ReminderReceiver.sync(this);}catch(Exception e){runOnUiThread(()->result.setText(e.getMessage()));}}).start();});
  Button disconnect=button("이 기기 연결 해제");root.addView(disconnect);disconnect.setOnClickListener(v->{disconnect.setEnabled(false);new Thread(()->{boolean revoked=true;try{String token=Api.token(this);if(!token.isEmpty())Api.callMethod(Api.origin(this),"device",token,null,"DELETE");}catch(Exception e){revoked=false;}Api.clear(this);CalendarWidget.refresh(this);boolean serverRevoked=revoked;runOnUiThread(()->{reminderToggle.setChecked(false);ReminderReceiver.periodic(this,false);disconnect.setEnabled(true);result.setText(serverRevoked?"이 기기 연결을 해제했어요.":"기기에서 연결 정보를 지웠어요. 서버 연결은 웹의 ‘연결 모두 해제’에서 해제해주세요.");});}).start();});
  connect.setOnClickListener(v->{String token=code.getText().toString().trim(),origin=sites.getSelectedItem().toString();if(token.length()<16){result.setText("연결 코드를 입력해주세요.");return;}connect.setEnabled(false);result.setText("연결 중…");new Thread(()->{boolean success=false;String message;try{JSONObject response=Api.call(origin,"claim","",new JSONObject().put("token",token).put("platform","Android"));ReminderReceiver.cancel(this);Api.save(this,origin,response.getString("token"));CalendarWidget.refresh(this);try{ReminderReceiver.sync(this);}catch(Exception ignored){}success=true;message="연결했어요. 원하는 위젯을 홈 화면에 추가해주세요.";}catch(Exception e){message=e.getMessage();}boolean ok=success;String resultText=message;runOnUiThread(()->{result.setText(resultText);connect.setEnabled(true);if(ok)code.setText("");});}).start();});
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(root);setContentView(scroll);
 }
}
