import {it,expect} from 'vitest';
import {centerline,horizontalPageSwipe} from './ink-render';
it('keeps vertical finger drags as scrolling in either vertical mode',()=>{for(const mode of ['vertical','continuous'])expect(horizontalPageSwipe(mode,{x:100,y:300},{x:102,y:50},false)).toBe(0);});
it('changes pages only for a dominant horizontal swipe in horizontal mode',()=>{expect(horizontalPageSwipe('horizontal',{x:300,y:100},{x:100,y:110},false)).toBe(1);expect(horizontalPageSwipe('horizontal',{x:300,y:100},{x:200,y:300},false)).toBe(0);expect(horizontalPageSwipe('horizontal',{x:300,y:100},{x:100,y:110},true)).toBe(0);});
it('committed uniform ink retains every position without pressure-driven geometry changes',()=>{expect(centerline([{x:0,y:0,p:.1},{x:5,y:2,p:.9},{x:7,y:4,p:0}])).toBe('M0,0 L5,2 L7,4');expect(centerline([{x:1,y:2}])).toBe('M1,2l0.01,0');});
