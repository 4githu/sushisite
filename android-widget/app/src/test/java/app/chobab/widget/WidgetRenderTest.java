package app.chobab.widget;
import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.view.View;
import android.widget.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.time.LocalDate;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class WidgetRenderTest {
 Context context;
 @Before public void setup(){context=RuntimeEnvironment.getApplication();context.getSharedPreferences("widget",0).edit().clear().commit();}
 JSONObject feed()throws Exception{return new JSONObject("{\"events\":[{\"id\":1,\"title\":\"생명과학 세미나\",\"startTime\":\"2026-11-16T14:00:00+09:00\",\"endTime\":\"2026-11-16T15:30:00+09:00\",\"location\":\"자연과학관\",\"status\":\"passive\"}],\"captures\":[],\"tasks\":[]}");}
 View render(CalendarWidget widget,JSONObject feed)throws Exception{RemoteViews views=new RemoteViews(context.getPackageName(),R.layout.widget);widget.renderFeed(context,views,feed,"https://netaq.chobab.app",99,LocalDate.of(2026,11,16),AppWidgetManager.getInstance(context));return views.apply(context,new FrameLayout(context));}
 @Test public void compactWidgetUsesRealTitleTimeRangeAndLocation()throws Exception{View root=render(new NextWidget(),feed());assertEquals("생명과학 세미나",((TextView)root.findViewById(R.id.event_name)).getText().toString());assertEquals("14:00–15:30",((TextView)root.findViewById(R.id.event_time)).getText().toString());assertEquals("자연과학관",((TextView)root.findViewById(R.id.event_location)).getText().toString());}
 @Test public void compactWeekKeepsReadableDateAndTitle()throws Exception{
  RemoteViews views=new RemoteViews(context.getPackageName(),R.layout.widget);
  new WeekWidget().renderCompactWeek(context,views,feed().getJSONArray("events"),"https://netaq.chobab.app",160);
  View root=views.apply(context,new FrameLayout(context));
  assertEquals("11.16 14:00 생명과학 세미나",((TextView)root.findViewById(R.id.event)).getText().toString());
 }
 @Test public void dailyPlanShowsProportionalClickableTimeBlocks()throws Exception{
  JSONObject data=feed();data.getJSONArray("events").put(new JSONObject("{\"id\":2,\"title\":\"두 시간\",\"startTime\":\"2026-11-16T16:00:00+09:00\",\"endTime\":\"2026-11-16T18:00:00+09:00\"}"));
  View root=render(new PlanWidget(),data);java.util.ArrayList<TextView> blocks=new java.util.ArrayList<>();collectBlocks(root,blocks);
  assertEquals(2,blocks.size());assertTrue(blocks.get(0).getContentDescription().toString().contains("14:00–15:30"));
  assertTrue(blocks.get(0).hasOnClickListeners());assertTrue(blocks.get(1).getMinHeight()>blocks.get(0).getMinHeight());
 }
 void collectBlocks(View view,java.util.List<TextView> out){if(view instanceof TextView&&view.getId()==R.id.block&&view.getContentDescription()!=null)out.add((TextView)view);if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)collectBlocks(group.getChildAt(i),out);}}
 @Test public void upgradingKeepsExistingPinnedWeeklyWidgets(){assertEquals("week",new CalendarWidget().mode());assertEquals("upcoming",new NextWidget().mode());assertEquals(NextWidget.class,CalendarWidget.PROVIDERS[0]);}
 @Test public void memoWidgetDisplaysInheritedCompletedItemsWithoutChangingThem()throws Exception{JSONObject data=feed();data.put("note","- [x] 이전에 끝낸 일\n이어 쓸 메모");View root=render(new MemoWidget(),data);assertEquals(data.getString("note"),((TextView)root.findViewById(R.id.memo_text)).getText().toString());}
 @Test public void todoWidgetProvidesSeparateCompletionAndOpenTargets()throws Exception{JSONObject data=feed();data.put("events",new JSONArray());data.put("captures",new JSONArray("[{\"id\":\"stable\",\"text\":\"자료 보내기\"}]"));View root=render(new TodoWidget(),data);View check=root.findViewById(R.id.task_check),title=root.findViewById(R.id.task_title);assertNotNull(check);assertNotNull(title);assertEquals("자료 보내기 완료",check.getContentDescription().toString());assertTrue(check.hasOnClickListeners());assertTrue(title.hasOnClickListeners());}
 @Test public void clearRemovesPrivateContentAndChangesSessionGeneration(){var prefs=context.getSharedPreferences("widget",0);prefs.edit().putString("token","encrypted").putString("cache-1","private feed").putString("capture-draft","private draft").putLong("session",3).commit();Api.clear(context);assertFalse(prefs.contains("token"));assertFalse(prefs.contains("cache-1"));assertFalse(prefs.contains("capture-draft"));assertEquals(4,prefs.getLong("session",0));}
 @Test public void expiredConnectionNotifiesOtherWidgetsOnlyOnce(){
  assertTrue(CalendarWidget.markAuthRejected(context));
  assertFalse(CalendarWidget.markAuthRejected(context));
  Api.clear(context);
  assertTrue(CalendarWidget.markAuthRejected(context));
 }
 @Test public void dailyPlanUsesExtraWidthForTasks(){
  assertFalse(CalendarWidget.isWidePlan(339));
  assertTrue(CalendarWidget.isWidePlan(340));
 }
 @Test public void onlyApprovedServicesCanReceiveCredentials(){assertTrue(Api.allowed("https://netaq.chobab.app"));assertFalse(Api.allowed("https://netaq.chobab.app.attacker.example"));assertFalse(Api.allowed("http://netaq.chobab.app"));}
}
