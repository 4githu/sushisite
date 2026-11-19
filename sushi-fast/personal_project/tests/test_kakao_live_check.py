import importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[3]/'ops/kakao_live_check.py';spec=importlib.util.spec_from_file_location('live_check',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Checks(unittest.TestCase):
 def test_keep_room_open_requested_on_success(self):
  with tempfile.TemporaryDirectory() as f:
   (Path(f)/'sushi-fast/.runtime').mkdir(parents=True)
   calls=[]
   def invoke(command,**args):
    calls.append((command,args))
    return {'trusted':True,'running':True,'locked':False} if command=='status' else {'opened':True,'room':'본계정','searchEvidence':'unique_exact'} if command=='search' else {'sent':True,'cleanup':{'searchCleared':True,'roomClosed':False,'closeRequested':False}}
   result=m.check('본계정','image','keep-room-attempt',root=Path(f),invoke=invoke,keep_room_open=True)
   self.assertTrue(next(args for command,args in calls if command=='send')['keepRoomOpen'])
   self.assertEqual(result['state'],'succeeded')
   self.assertTrue(result['cleanup_verified'])
 def test_same_attempt_sends_once(self):
  with tempfile.TemporaryDirectory() as f:
   (Path(f)/'sushi-fast/.runtime').mkdir(parents=True)
   calls=[]
   def invoke(command,**args):
    calls.append(command)
    return {'trusted':True,'running':True,'locked':False} if command=='status' else {'opened':True,'room':m.ROOMS[0],'searchEvidence':'unique_exact'} if command=='search' else {'sent':True}
   a=m.check(m.ROOMS[0],'text','fixed-attempt',root=Path(f),invoke=invoke)
   b=m.check(m.ROOMS[0],'text','fixed-attempt',root=Path(f),invoke=invoke)
   self.assertEqual(a['state'],'succeeded');self.assertEqual(b['state'],'succeeded');self.assertEqual(calls.count('send'),1)
 def test_unknown_is_never_replayed(self):
  with tempfile.TemporaryDirectory() as f:
   (Path(f)/'sushi-fast/.runtime').mkdir(parents=True)
   calls=[]
   def invoke(command,**args):
    calls.append(command)
    return {'trusted':True,'running':True,'locked':False} if command=='status' else {'opened':True,'room':m.ROOMS[0],'searchEvidence':'unique_exact'} if command=='search' else {'uncertain':True,'error':'lost acknowledgement'}
   a=m.check(m.ROOMS[0],'text','unknown-attempt',root=Path(f),invoke=invoke)
   m.check(m.ROOMS[0],'text','unknown-attempt',root=Path(f),invoke=invoke)
   self.assertEqual(a['state'],'unknown');self.assertEqual(calls.count('send'),1)
 def test_other_room_and_path_injection_are_rejected(self):
  for room,key in [('real clinic','safe-attempt'),(m.ROOMS[0],'../../outside')]:
   with self.assertRaises(ValueError):m.check(room,'text',key)
 def test_ambiguous_search_never_sends(self):
  with tempfile.TemporaryDirectory() as f:
   (Path(f)/'sushi-fast/.runtime').mkdir(parents=True)
   calls=[]
   def invoke(command,**args):
    calls.append(command)
    return {'trusted':True,'running':True,'locked':False} if command=='status' else {'error':'ambiguous'}
   r=m.check(m.ROOMS[0],'text','blocked-attempt',root=Path(f),invoke=invoke)
   self.assertEqual(r['state'],'blocked');self.assertNotIn('send',calls)
if __name__ == '__main__':
 unittest.main()
