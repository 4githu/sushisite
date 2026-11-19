//! Windows desktop hosting. The window remains a real interactive WebView.
#[cfg(windows)]
mod platform {
 use std::{ffi::c_void,ptr};
 use tauri::WebviewWindow;
 type Hwnd=*mut c_void;
 #[link(name="user32")]
 extern "system" {
  fn FindWindowW(class:*const u16,name:*const u16)->Hwnd;
  fn FindWindowExW(parent:Hwnd,after:Hwnd,class:*const u16,name:*const u16)->Hwnd;
  fn EnumWindows(callback:unsafe extern "system" fn(Hwnd,isize)->i32,param:isize)->i32;
  fn SendMessageTimeoutW(window:Hwnd,msg:u32,wparam:usize,lparam:isize,flags:u32,timeout:u32,result:*mut usize)->usize;
  fn SetParent(child:Hwnd,parent:Hwnd)->Hwnd;
  fn GetWindowLongPtrW(window:Hwnd,index:i32)->isize;
  fn SetWindowLongPtrW(window:Hwnd,index:i32,value:isize)->isize;
  fn SetWindowPos(window:Hwnd,after:Hwnd,x:i32,y:i32,cx:i32,cy:i32,flags:u32)->i32;
 }
 fn wide(value:&str)->Vec<u16>{value.encode_utf16().chain(Some(0)).collect()}
 unsafe extern "system" fn find_host(window:Hwnd,param:isize)->i32 {
  let def=FindWindowExW(window,ptr::null_mut(),wide("SHELLDLL_DefView").as_ptr(),ptr::null());
  if !def.is_null(){let worker=FindWindowExW(ptr::null_mut(),window,wide("WorkerW").as_ptr(),ptr::null());if !worker.is_null(){*(param as *mut Hwnd)=worker;return 0;}}
  1
 }
 pub fn attach(window:&WebviewWindow)->Result<(),String>{
  unsafe {
   let progman=FindWindowW(wide("Progman").as_ptr(),ptr::null());if progman.is_null(){return Err("바탕화면을 찾지 못했어요.".into());}
   let mut ignored=0;SendMessageTimeoutW(progman,0x052c,0,0,2,1000,&mut ignored);
   let mut host:Hwnd=ptr::null_mut();EnumWindows(find_host,&mut host as *mut Hwnd as isize);
   if host.is_null(){return Err("바탕화면 위젯을 붙이지 못했어요. 작업 표시줄에서 다시 열어주세요.".into());}
   let hwnd=window.hwnd().map_err(|_|"위젯 창을 찾지 못했어요.")?.0 as Hwnd;
   let style=GetWindowLongPtrW(hwnd,-16);
   SetWindowLongPtrW(hwnd,-16,(style & !(0x80000000u32 as isize)) | 0x40000000);
   SetParent(hwnd,host);
   SetWindowPos(hwnd,ptr::null_mut(),32,32,0,0,0x0001|0x0004|0x0020|0x0040);
   Ok(())
  }
 }
}
#[cfg(windows)] pub use platform::attach;
#[cfg(not(windows))] pub fn attach(_: &tauri::WebviewWindow)->Result<(),String>{Err("Windows에서만 바탕화면에 표시할 수 있어요.".into())}
