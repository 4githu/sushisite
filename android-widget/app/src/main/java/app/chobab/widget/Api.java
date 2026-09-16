package app.chobab.widget;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class Api {
 static final String[] ORIGINS={"https://chobab.app","https://aura.chobab.app","https://calender.chobab.app","https://calendar.chobab.app"};
 static boolean allowed(String origin){for(String s:ORIGINS)if(s.equals(origin))return true;return false;}
 static String origin(Context c){return c.getSharedPreferences("widget",0).getString("origin",ORIGINS[0]);}
 static SecretKey key() throws Exception {KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);if(!store.containsAlias("ondo-widget")){KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");g.init(new KeyGenParameterSpec.Builder("ondo-widget",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();}return (SecretKey)store.getKey("ondo-widget",null);}
 static void save(Context c,String origin,String token)throws Exception{Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());String saved=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(token.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);c.getSharedPreferences("widget",0).edit().putString("origin",origin).putString("token",saved).apply();}
 static String token(Context c)throws Exception{String s=c.getSharedPreferences("widget",0).getString("token","");if(s.isEmpty())return "";String[] parts=s.split(":");Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),StandardCharsets.UTF_8);}
 static JSONObject call(String origin,String path,String token,JSONObject body)throws Exception{
  if(!allowed(origin))throw new Exception("허용되지 않은 서비스입니다.");
  HttpURLConnection con=(HttpURLConnection)URI.create(origin+"/api/personal/calendar/widget/"+path).toURL().openConnection();
  con.setInstanceFollowRedirects(false);con.setConnectTimeout(3500);con.setReadTimeout(4500);
  if(!token.isEmpty())con.setRequestProperty("Authorization","Bearer "+token);
  try{
   if(body!=null){con.setRequestMethod("POST");con.setDoOutput(true);con.setRequestProperty("Content-Type","application/json");try(var out=con.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}}
   if(con.getResponseCode()!=200)throw new Exception(con.getResponseCode()==401?"연결이 해제되었습니다. 앱에서 다시 연결하세요.":"연결을 확인하고 다시 시도해주세요.");
   try(var in=con.getInputStream();var out=new ByteArrayOutputStream()){
    byte[] buffer=new byte[4096];int n;while((n=in.read(buffer))!=-1){out.write(buffer,0,n);if(out.size()>1048576)throw new Exception("응답이 너무 큽니다.");}
    return new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
   }
  }finally{con.disconnect();}
 }
}
