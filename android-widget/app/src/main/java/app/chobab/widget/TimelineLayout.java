package app.chobab.widget;

import java.util.*;

/** Shared, Android-independent geometry for the week renderer. */
final class TimelineLayout {
 static class Span {
  final int start,end;int lane;
  Span(int start,int end){if(start<0||end>1440||end<=start)throw new IllegalArgumentException("Invalid day span");this.start=start;this.end=end;}
 }
 static int assignLanes(List<? extends Span> spans){
  spans.sort(Comparator.comparingInt(e->e.start));List<Integer> ends=new ArrayList<>();
  for(Span span:spans){int lane=0;while(lane<ends.size()&&ends.get(lane)>span.start)lane++;if(lane==ends.size())ends.add(span.end);else ends.set(lane,span.end);span.lane=lane;}
  return Math.max(1,ends.size());
 }
 static int pixelAt(int minute,int from,int to,int height){return Math.round((minute-from)*(float)height/(to-from));}
}
