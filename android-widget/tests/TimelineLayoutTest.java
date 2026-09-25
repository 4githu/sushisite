package app.chobab.widget;
import java.util.*;
public class TimelineLayoutTest {
 public static void main(String[] args){
  TimelineLayout.Span first=new TimelineLayout.Span(540,600),overlap=new TimelineLayout.Span(570,630),adjacent=new TimelineLayout.Span(600,660);
  List<TimelineLayout.Span> spans=new ArrayList<>(Arrays.asList(adjacent,overlap,first));
  if(TimelineLayout.assignLanes(spans)!=2||first.lane!=0||overlap.lane!=1||adjacent.lane!=0)throw new AssertionError("Overlap lanes and touching boundaries");
  if(TimelineLayout.pixelAt(570,480,1320,420)!=45)throw new AssertionError("Half-hour position");
  if(TimelineLayout.pixelAt(1440,0,1440,480)!=480)throw new AssertionError("Midnight exclusive end");
  if(TimelineLayout.assignLanes(new ArrayList<>())!=1)throw new AssertionError("Empty day");
  System.out.println("4 timeline geometry checks passed");
 }
}
