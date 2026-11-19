use std::{collections::BTreeMap, path::PathBuf, time::Duration};
use base64::{engine::general_purpose::STANDARD, Engine};
use chacha20poly1305::{aead::{Aead, KeyInit, OsRng}, ChaCha20Poly1305, Nonce};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{Manager, WebviewWindow};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_updater::UpdaterExt;
use tauri_plugin_wallpaper::{WallpaperExt, AttachRequest, DetachRequest};
use tokio::sync::Mutex;

const ORIGINS: [&str;4] = ["https://netaq.chobab.app", "https://calendar.chobab.app", "https://calender.chobab.app", "https://chobab.app"];
#[derive(Default, Serialize, Deserialize)]
#[serde(default)]
struct Data { origin: String, token: String, cache: BTreeMap<String,Value>, draft: Option<Value>, quick_draft: Option<Value>, theme: String, meal_restaurant: String, session_id: String }
pub struct WidgetState { data: Mutex<Option<Data>>, http: reqwest::Client }
impl WidgetState { pub fn new()->Self { Self { data: Mutex::new(None), http:reqwest::Client::builder().timeout(Duration::from_secs(12)).redirect(reqwest::redirect::Policy::none()).build().expect("http client") } } }
fn storage(app:&tauri::AppHandle)->Result<(PathBuf,ChaCha20Poly1305),String>{
 let dir=app.path().app_data_dir().map_err(|_|"저장 공간을 열지 못했어요.")?;
 std::fs::create_dir_all(&dir).map_err(|_|"저장 공간을 열지 못했어요.")?;
 let file=dir.join("widget-v1.enc");
 let entry=keyring::Entry::new("app.chobab.netaq.desktop.widget", "encryption-key").map_err(|_|"보안 저장소를 사용할 수 없어요.")?;
 let bytes=match entry.get_password(){
  Ok(key)=>STANDARD.decode(key).map_err(|_|"보안 키를 읽지 못했어요.")?,
  Err(keyring::Error::NoEntry) if !file.exists()=>{let mut key=[0u8;32];OsRng.fill_bytes(&mut key);entry.set_password(&STANDARD.encode(key)).map_err(|_|"보안 키를 저장하지 못했어요.")?;key.to_vec()},
  Err(_)=>return Err("보안 저장소를 열지 못했어요. 기존 기록은 보존했어요.".into())
 };
 let cipher=ChaCha20Poly1305::new_from_slice(&bytes).map_err(|_|"보안 키를 읽지 못했어요.")?;
 Ok((file,cipher))
}
fn load(app:&tauri::AppHandle)->Result<Data,String>{
 let (file,cipher)=storage(app)?;
 if !file.exists() {
  let backup=file.with_extension("bak");
  if backup.exists(){std::fs::rename(&backup,&file).map_err(|_|"기존 기록을 복구하지 못했어요.")?;}
  else{return Ok(Data{origin:ORIGINS[0].into(),theme:"system".into(),..Default::default()});}
 }
 let bytes=std::fs::read(file).map_err(|_|"저장된 내용을 읽지 못했어요.")?;
 if bytes.len()<12{return Err("저장된 내용을 읽지 못했어요.".into());}
 let plain=cipher.decrypt(Nonce::from_slice(&bytes[..12]),&bytes[12..]).map_err(|_|"저장된 내용을 복원하지 못했어요.")?;
 serde_json::from_slice(&plain).map_err(|_|"저장된 내용을 복원하지 못했어요.".into())
}
fn save(app:&tauri::AppHandle,data:&Data)->Result<(),String>{
 let (file,cipher)=storage(app)?;let mut nonce=[0u8;12];OsRng.fill_bytes(&mut nonce);
 let plain=serde_json::to_vec(data).map_err(|_|"저장하지 못했어요.")?;
 let body=cipher.encrypt(Nonce::from_slice(&nonce),plain.as_slice()).map_err(|_|"저장하지 못했어요.")?;
 let mut bytes=nonce.to_vec();bytes.extend(body);let temp=file.with_extension("tmp");
 std::fs::write(&temp,bytes).map_err(|_|"저장하지 못했어요.")?;
 // Windows rename cannot replace an existing file. Preserve a recoverable backup.
 let backup=file.with_extension("bak");if file.exists(){let _=std::fs::remove_file(&backup);std::fs::rename(&file,&backup).map_err(|_|"저장하지 못했어요.")?;}
 if std::fs::rename(&temp,&file).is_err(){let _=std::fs::rename(&backup,&file);return Err("저장하지 못했어요.".into());}let _=std::fs::remove_file(backup);Ok(())
}
fn string<'a>(args:&'a Value,key:&str)->Result<&'a str,String>{args.get(key).and_then(Value::as_str).ok_or_else(||"입력 내용을 확인해주세요.".into())}
async fn request(http:&reqwest::Client,data:&Data,path:&str,body:Option<Value>,method:reqwest::Method)->Result<(u16,Value),String>{
 if !ORIGINS.contains(&data.origin.as_str()){return Err("서비스 주소를 확인해주세요.".into());}
 let mut req=http.request(method,format!("{}/api/personal/calendar/widget/{}",data.origin,path));
 if !data.token.is_empty(){req=req.bearer_auth(&data.token);}if let Some(b)=body{req=req.json(&b);}
 let resp=req.send().await.map_err(|_|"인터넷 연결을 확인하고 다시 시도해주세요.".to_string())?;let status=resp.status().as_u16();let value=resp.json::<Value>().await.unwrap_or(json!({}));Ok((status,value))
}
fn service_error(status:u16,value:&Value)->String{if status==401{"계정을 다시 연결해주세요.".into()}else{value.get("detail").and_then(Value::as_str).unwrap_or("요청을 처리하지 못했어요. 다시 시도해주세요.").into()}}
#[tauri::command]
pub async fn widget_call(app:tauri::AppHandle,window:WebviewWindow,state:tauri::State<'_,WidgetState>,action:String,args:Value)->Result<Value,String>{
 if window.label()!="widget" && !(window.label()=="quick-capture" && ["state","draft","capture","window"].contains(&action.as_str())) {return Err("잘못된 요청입니다.".into());}
 if action=="desktop-state" {return Ok(json!({"attached":app.wallpaper().is_attached("widget")}));}
 if action=="attach-desktop" {app.wallpaper().attach(AttachRequest::new("widget").with_input_forwarding(true,false)).map_err(|_|"바탕화면에 추가하지 못했어요. 알림 영역 메뉴에서 위젯 창을 다시 열어주세요.")?;return Ok(json!(true));}
 if action=="detach-desktop" {app.wallpaper().detach(DetachRequest::new("widget")).map_err(|_|"위젯 창을 다시 열지 못했어요.")?;window.show().map_err(|_|"위젯 창을 다시 열지 못했어요.")?;let _=window.set_focus();return Ok(json!(true));}
 if action=="update" {let updater=app.updater().map_err(|_|"업데이트를 준비하지 못했어요.")?;let update=updater.check().await.map_err(|_|"업데이트 정보를 확인하지 못했어요. 인터넷을 확인해주세요.")?;if let Some(update)=update {update.download_and_install(|_,_|{},||{}).await.map_err(|_|"서명 확인 또는 업데이트 설치에 실패했어요. 기존 앱은 유지됩니다.")?;return Ok(json!({"installed":true}));}return Ok(json!({"installed":false}));}

 let mut guard=state.data.lock().await;if guard.is_none(){*guard=Some(load(&app)?);}let data=guard.as_mut().unwrap();
 if window.label()=="quick-capture" && ["draft","capture"].contains(&action.as_str()) && (data.token.is_empty() || args.get("sessionId").and_then(Value::as_str)!=Some(data.session_id.as_str())) {return Err("계정 연결이 바뀌었어요. 창을 다시 열어주세요.".into());}
 match action.as_str(){
 "version"=>{if !ORIGINS.contains(&data.origin.as_str()){return Err("서비스 주소를 확인해주세요.".into());}let response=state.http.get(format!("{}/downloads/widget-version",data.origin)).send().await.map_err(|_|"업데이트 정보를 불러오지 못했어요.")?;if !response.status().is_success(){return Err("업데이트 정보를 불러오지 못했어요.".into());}let value=response.json::<Value>().await.map_err(|_|"업데이트 정보를 읽지 못했어요.")?;Ok(value)},
 "state"=>Ok(json!({"connected":!data.token.is_empty(),"appVersion":app.package_info().version.to_string(),"sessionId":data.session_id,"origin":data.origin,"origins":ORIGINS,"draft":if window.label()=="quick-capture" {&data.quick_draft}else{&data.draft},"theme":data.theme,"mealRestaurant":data.meal_restaurant,"alwaysOnTop":window.is_always_on_top().unwrap_or(false),"startup":app.autolaunch().is_enabled().unwrap_or(false)})),
 "claim"=>{let code=string(&args,"code")?.trim();let origin=string(&args,"origin")?;if !ORIGINS.contains(&origin)||code.len()<16||code.len()>200{return Err("서비스와 연결 코드를 확인해주세요.".into());}let old=data.origin.clone();data.origin=origin.into();let result=request(&state.http,data,"claim",Some(json!({"token":code,"platform":"Windows"})),reqwest::Method::POST).await;match result {Ok((s,v)) if s==200=>{let token=v.get("token").and_then(Value::as_str).filter(|x|!x.is_empty()).ok_or("연결 응답을 확인하지 못했어요.")?;data.token=token.into();data.session_id=STANDARD.encode(rand::random::<[u8;16]>());data.cache.clear();data.draft=None;data.quick_draft=None;save(&app,data)?;Ok(json!({"connected":true}))},Ok((s,v))=>{data.origin=old;Err(service_error(s,&v))},Err(e)=>{data.origin=old;Err(e)}}},
 "feed"|"cached"=>{let view=string(&args,"view")?;let date=string(&args,"date")?;if !["day","planning","week","month","tasks","meal","recent"].contains(&view)||date.len()!=10||!date.bytes().enumerate().all(|(i,c)|if i==4||i==7{c==b'-'}else{c.is_ascii_digit()}){return Err("날짜를 확인해주세요.".into());}if data.token.is_empty(){return Ok(json!({"connected":false}));}let key=format!("{view}:{date}");if action=="cached" {return Ok(data.cache.get(&key).cloned().map(|mut v|{v["connected"]=json!(true);v["cached"]=json!(true);v}).unwrap_or(json!(null)));}let path=match view {"meal"=>format!("meals?day={date}"),"recent"=>"recent-notes".to_string(),_=>format!("feed?view={view}&anchor={date}")};match request(&state.http,data,&path,None,reqwest::Method::GET).await{Ok((200,mut v))=>{data.cache.insert(key,v.clone());save(&app,data)?;v["connected"]=json!(true);v["cached"]=json!(false);Ok(v)},Ok((401,_))=>{data.token.clear();data.cache.clear();data.draft=None;data.quick_draft=None;save(&app,data)?;Ok(json!({"connected":false,"error":"계정을 다시 연결해주세요."}))},Ok((s,v)) if s>=500=>if let Some(mut cached)=data.cache.get(&key).cloned(){cached["connected"]=json!(true);cached["cached"]=json!(true);cached["error"]=json!(service_error(s,&v));Ok(cached)}else{Err(service_error(s,&v))},Ok((s,v))=>Err(service_error(s,&v)),Err(e)=>if let Some(mut v)=data.cache.get(&key).cloned(){v["connected"]=json!(true);v["cached"]=json!(true);v["error"]=json!(e);Ok(v)}else{Err(e)}}},
 "complete"|"capture"=>{let body=if action=="complete"{let src=string(&args,"source")?;let id=string(&args,"id")?;if !["event","capture"].contains(&src)||id.len()>200{return Err("할 일을 확인해주세요.".into());}json!({"source":src,"id":id,"done":args.get("done").and_then(Value::as_bool).ok_or("할 일을 확인해주세요.")?})}else{let id=string(&args,"id")?;let text=string(&args,"text")?;if id.len()>200||text.trim().is_empty()||text.chars().count()>2000{return Err("기록은 1~2,000자로 입력해주세요.".into());}json!({"id":id,"text":text})};let path=if action=="complete"{"task"}else{"capture"};let (status,v)=request(&state.http,data,path,Some(body),reqwest::Method::POST).await?;if !(200..300).contains(&status){return Err(service_error(status,&v));}if action=="complete"{data.cache.clear();save(&app,data)?;}Ok(json!({"ok":true}))},
 "draft"=>{let draft=args.get("value").filter(|v|!v.is_null()).cloned();if let Some(d)=&draft{let t=string(d,"text")?;let id=string(d,"id")?;if t.chars().count()>2000||id.len()>200{return Err("기록을 확인해주세요.".into());}}if window.label()=="quick-capture" {data.quick_draft=draft;}else{data.draft=draft;}save(&app,data)?;Ok(json!(true))},
 "disconnect"=>{let result=if data.token.is_empty(){Ok((204,json!({})))}else{request(&state.http,data,"device",None,reqwest::Method::DELETE).await};data.token.clear();data.session_id=STANDARD.encode(rand::random::<[u8;16]>());data.cache.clear();data.draft=None;data.quick_draft=None;save(&app,data)?;let (status,v)=result?;if !(200..300).contains(&status)&&status!=401{return Err(service_error(status,&v));}Ok(json!({"connected":false}))},
 "settings"=>{let v=&args["value"];if let Some(top)=v.get("alwaysOnTop").and_then(Value::as_bool){window.set_always_on_top(top).map_err(|_|"창 설정을 저장하지 못했어요.")?;}if let Some(start)=v.get("startup").and_then(Value::as_bool){if start{app.autolaunch().enable()}else{app.autolaunch().disable()}.map_err(|_|"자동 실행을 설정하지 못했어요.")?;}if let Some(restaurant)=v.get("mealRestaurant").and_then(Value::as_str){if restaurant.chars().count()<=200{data.meal_restaurant=restaurant.into();save(&app,data)?;}}if let Some(theme)=v.get("theme").and_then(Value::as_str){if ["system","light","dark"].contains(&theme){data.theme=theme.into();save(&app,data)?;}}Ok(json!(true))},
 "open"=>{let route=string(&args,"route")?;let path=route.split(['?', '#']).next().unwrap_or("");if !(path=="/personal-project/calendar"||path.starts_with("/personal-project/calendar/")||path=="/personal-project/notes"||path=="/student/meals")||route.contains('\\')||route.contains('\n')||route.contains('\r'){return Err("잘못된 주소입니다.".into());}let url=reqwest::Url::parse(&data.origin).map_err(|_|"주소 오류")?.join(route).map_err(|_|"주소 오류")?;if url.origin().ascii_serialization()!=data.origin{return Err("잘못된 주소입니다.".into());}let main=app.get_webview_window("main").ok_or("앱 창을 찾지 못했어요.")?;let current=main.url().map_err(|_|"앱 주소를 확인하지 못했어요.")?;if current.origin().ascii_serialization()!=data.origin{return Err("열려 있는 앱의 주소를 확인해주세요.".into());}let destination=serde_json::to_string(url.as_str()).map_err(|_|"주소 오류")?;main.eval(format!("window.location.assign({destination})")).map_err(|_|"앱을 열지 못했어요.")?;main.show().map_err(|_|"앱을 열지 못했어요.")?;let _=main.unminimize();main.set_focus().map_err(|_|"앱을 열지 못했어요.")?;Ok(json!(true))},
 "window"=>{match string(&args,"action")?{"minimize"=>{window.hide().map_err(|_|"창을 최소화하지 못했어요.")?;crate::open_mini(&app);},"close"=>window.hide().map_err(|_|"창을 닫지 못했어요.")?,_=>return Err("잘못된 요청입니다.".into())};Ok(json!(true))},
 _=>Err("잘못된 요청입니다.".into())
 }
}
