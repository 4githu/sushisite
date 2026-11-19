#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod widget;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder, menu::{CheckMenuItem, Menu, MenuItem}, tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState}};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_wallpaper::{WallpaperExt, AttachRequest, DetachRequest};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState, Code, Modifiers};

fn focus_main(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}
fn open_widget(app: &tauri::AppHandle) {
    if let Some(window)=app.get_webview_window("widget") { let _=window.show(); let _=window.unminimize(); let _=window.set_focus(); return; }
    if let Err(error)=WebviewWindowBuilder::new(app,"widget",WebviewUrl::App("widget/index.html".into()))
      .title("NETAQ 위젯").inner_size(420.0,620.0).min_inner_size(340.0,360.0).resizable(true).decorations(false).skip_taskbar(true).build() { eprintln!("위젯을 열지 못했습니다: {error}"); }
}
fn attach_widget(app: &tauri::AppHandle) {
    open_widget(app);
    if let Err(error)=app.wallpaper().attach(AttachRequest::new("widget").with_input_forwarding(true, false)) {
        eprintln!("바탕화면에 위젯을 붙이지 못했습니다: {error}");
        if let Some(window)=app.get_webview_window("widget") { let _=window.show(); let _=window.set_focus(); }
    }
}
fn float_widget(app: &tauri::AppHandle) {
    if let Some(mini)=app.get_webview_window("mini") { let _=mini.hide(); }
    if app.get_webview_window("widget").is_some() { let _=app.wallpaper().detach(DetachRequest::new("widget")); }
    open_widget(app);
}
fn open_mini(app: &tauri::AppHandle) {
    if let Some(window)=app.get_webview_window("mini") {let _=window.show(); return;}
    if let Err(error)=WebviewWindowBuilder::new(app,"mini",WebviewUrl::App("mini/index.html".into()))
      .title("NETAQ 빠른 메모").inner_size(64.0,88.0).resizable(false).decorations(false).transparent(true).skip_taskbar(true).build() {eprintln!("축소 위젯을 열지 못했습니다: {error}");}
}
#[tauri::command]
fn mini_call(app: tauri::AppHandle, window: tauri::WebviewWindow, action: String) -> Result<(),String> {
    if window.label()!="mini" {return Err("잘못된 요청입니다.".into());}
    match action.as_str() {"memo"=>open_memo(&app),"restore"=>{let _=window.hide();float_widget(&app);},_=>return Err("잘못된 요청입니다.".into())} Ok(())
}
fn open_memo(app: &tauri::AppHandle) {
    // WebView2 window creation can deadlock inside synchronous commands and
    // event handlers on Windows. Serialize creation on a worker thread.
    static CREATE_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    let app = app.clone();
    std::thread::spawn(move || {
        let _guard = CREATE_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(window)=app.get_webview_window("quick-capture") {let _=window.show();let _=window.unminimize();let _=window.set_focus();return;}
        if let Err(error)=WebviewWindowBuilder::new(&app,"quick-capture",WebviewUrl::App("capture/index.html".into()))
          .title("NETAQ 빠른 기록").inner_size(400.0,440.0).min_inner_size(340.0,360.0).resizable(true).skip_taskbar(false).build() {eprintln!("빠른 기록 창을 열지 못했습니다: {error}");}
    });
}
// Tauri stores installers in its own temporary directories; remove only old, non-symlink directories.
fn cleanup_old_update_files(app: &tauri::AppHandle) {
    let prefix=format!("{}-",app.package_info().name);
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(180));
        if let Ok(entries)=std::fs::read_dir(std::env::temp_dir()) {
            for entry in entries.flatten() {
                let name=entry.file_name().to_string_lossy().into_owned();
                if !name.starts_with(&prefix) || !name.contains("-updater-") { continue; }
                if let Ok(kind)=entry.file_type() { if !kind.is_dir() || kind.is_symlink() { continue; } } else { continue; }
                if let Ok(meta)=entry.metadata() { if let Ok(modified)=meta.modified() { if modified.elapsed().unwrap_or_default()<std::time::Duration::from_secs(120) { continue; } } else {continue;} } else {continue;}
                let _=std::fs::remove_dir_all(entry.path());
            }
        }
    });
}
fn main() {
    tauri::Builder::default()
        .manage(widget::WidgetState::new())
        .plugin(tauri_plugin_wallpaper::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![widget::widget_call, mini_call])
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .plugin(tauri_plugin_single_instance::init(|app, _, _| focus_main(app)))
        .plugin(tauri_plugin_global_shortcut::Builder::new().with_handler(|app, shortcut, event| {
            if event.state == ShortcutState::Pressed {
                if shortcut.matches(Modifiers::CONTROL | Modifiers::SHIFT, Code::KeyW) { float_widget(app); }
                else if shortcut.matches(Modifiers::CONTROL | Modifiers::SHIFT, Code::KeyM) { open_memo(app); }
            }
        }).build())
        .setup(|app| {
            cleanup_old_update_files(app.handle());
            // Distinguish the calendar window from the widget's square icon.
            if let Some(main) = app.get_webview_window("main") {
                let mut rgba = vec![0u8; 32 * 32 * 4];
                for y in 0..32i32 { for x in 0..32i32 {
                    let d = (2*x-31).pow(2)+(2*y-31).pow(2);
                    if (225..=841).contains(&d) { let i=((y*32+x)*4) as usize; rgba[i..i+4].copy_from_slice(&[196,65,44,255]); }
                }}
                let _ = main.set_icon(tauri::image::Image::new_owned(rgba, 32, 32));
            }
            let widget_menu = MenuItem::with_id(app, "widget", "바탕화면 위젯", true, None::<&str>)?;
            let attach = MenuItem::with_id(app, "attach", "바탕화면에 위젯 추가", true, None::<&str>)?;
            let floating = MenuItem::with_id(app, "floating", "위젯 창으로 열기", true, None::<&str>)?;
            let show = MenuItem::with_id(app, "show", "NETAQ 열기", true, None::<&str>)?;
            let memo = MenuItem::with_id(app, "memo", "빠른 메모", true, None::<&str>)?;
            let pin = CheckMenuItem::with_id(app, "pin", "항상 위에 표시", true, false, None::<&str>)?;
            let auto = CheckMenuItem::with_id(app, "autostart", "로그인할 때 실행", true, app.autolaunch().is_enabled().unwrap_or(false), None::<&str>)?;
            let pin_item=pin.clone();
            let auto_item=auto.clone();
            let quit = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&widget_menu, &attach, &floating, &show, &memo, &pin, &auto, &quit])?;
            let mut tray = TrayIconBuilder::new().menu(&menu).show_menu_on_left_click(false)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "widget" => float_widget(app), "attach" => attach_widget(app), "floating" => float_widget(app), "show" => focus_main(app), "memo" => open_memo(app),
                    "pin" => if let Some(window)=app.get_webview_window("widget") {
                        let old=window.is_always_on_top().unwrap_or(false);
                        let enabled=if window.set_always_on_top(!old).is_ok(){!old}else{old};
                        let _=pin_item.set_checked(enabled);
                    },
                    "autostart" => {
                        let manager=app.autolaunch(); let old=manager.is_enabled().unwrap_or(false);
                        let result=if old {manager.disable()} else {manager.enable()};
                        let _=auto_item.set_checked(if result.is_ok(){!old}else{old});
                    },
                    "quit" => app.exit(0), _ => ()
                }).on_tray_icon_event(|tray, event| {
                    if matches!(event, TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. }) { open_memo(tray.app_handle()); }
                });
            let mut pixels=vec![0u8;32*32*4];
            for y in 0..32 { for x in 0..32 { let i=(y*32+x)*4; let inside=x>=4&&x<28&&y>=4&&y<28; let mark=(x>=10&&x<22&&y>=10&&y<13)||(x>=10&&x<22&&y>=16&&y<19)||(x>=10&&x<18&&y>=22&&y<25); if inside { pixels[i..i+4].copy_from_slice(if mark { &[255,255,255,255] } else { &[196,65,44,255] }); } } }
            tray = tray.icon(tauri::image::Image::new_owned(pixels,32,32)).tooltip("NETAQ 위젯 · 클릭하여 빠른 메모");
            tray.build(app)?;
            open_widget(app.handle());
            if let Err(error) = app.global_shortcut().register("CommandOrControl+Shift+M") {
                eprintln!("빠른 메모 단축키를 사용할 수 없습니다: {error}");
            }
            if let Err(error) = app.global_shortcut().register("CommandOrControl+Shift+W") {
                eprintln!("위젯 단축키를 사용할 수 없습니다: {error}");
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == "main" || window.label() == "quick-capture" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("NETAQ 앱을 시작하지 못했습니다");
}
