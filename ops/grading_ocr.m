#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
int main(int argc, const char *argv[]) {
 @autoreleasepool {
  if(argc!=2){fputs("Expected image path\n",stderr);return 2;}
  VNRecognizeTextRequest *request=[[VNRecognizeTextRequest alloc] init];
  request.recognitionLevel=VNRequestTextRecognitionLevelAccurate;
  request.recognitionLanguages=@[@"ko-KR",@"en-US"];
  request.usesLanguageCorrection=YES;
  VNImageRequestHandler *handler=[[VNImageRequestHandler alloc] initWithURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]] options:@{}];
  NSError *error=nil;
  if(![handler performRequests:@[request] error:&error]){fputs("OCR failed\n",stderr);return 1;}
  NSMutableArray *lines=[NSMutableArray array];
  for(VNRecognizedTextObservation *observation in request.results){VNRecognizedText *text=[observation topCandidates:1].firstObject;if(text)[lines addObject:text.string];}
  NSData *json=[NSJSONSerialization dataWithJSONObject:@{@"text":[lines componentsJoinedByString:@"\n"]} options:0 error:&error];
  if(!json)return 1;
  fwrite(json.bytes,1,json.length,stdout);return 0;
 }
}
