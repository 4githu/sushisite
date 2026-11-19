export type DeliveryResult = {
 sent?: boolean; deliveryStatus?: string; retryable?: boolean; destination?: string;
 deliveryFormat?: string; sentCount?: number; fallbackReason?: string; completionStatus?: string;
};

export function deliveryView(result: DeliveryResult): { message: string; unlock: boolean; verified: boolean } {
 if (result.sent === true && result.deliveryStatus === 'verified') {
  let message: string;
  if (result.deliveryFormat === 'text' && result.destination === '본계정' && result.fallbackReason === 'both_rooms_confirmed_absent') {
   message = '본계정에 리포트 내용을 텍스트로 보냈습니다. 학생 방에는 발송되지 않았습니다.';
  } else if ((result.deliveryFormat === 'image' || result.deliveryFormat === 'images') && result.destination === '본계정' && result.fallbackReason === 'both_rooms_confirmed_absent' && Number.isSafeInteger(result.sentCount) && (result.sentCount ?? 0) > 0) {
   message = `본계정에 리포트 이미지 ${result.sentCount}장을 대체 전송했습니다. 학생 방에는 발송되지 않았습니다.`;
  } else if (result.destination && result.deliveryFormat !== 'text' && Number.isSafeInteger(result.sentCount) && (result.sentCount ?? 0) > 0) {
   message = `${result.destination}에 서버에서 만든 리포트 ${result.sentCount}장을 보냈습니다.`;
  } else if (result.destination) {
   message = `${result.destination}에 리포트를 보냈습니다.`;
  } else {
   message = '리포트 전송이 확인되었습니다. 전송 대상은 이 응답에서 확인할 수 없습니다.';
  }
  if (result.completionStatus === 'pending') message += ' 작성완료 저장은 확인되지 않았습니다.';
  return {message, unlock:true, verified:true};
 }
 if (result.deliveryStatus === 'not_started' && result.retryable === true) return {message:'전송 전에 중단되었습니다. 다시 누르면 재시도할 수 있습니다.', unlock:true, verified:false};
 if (result.deliveryStatus === 'partial') return {message:'일부 전송되었으며 전체 전송 결과는 확인되지 않았습니다.', unlock:false, verified:false};
 return {message:'전송 결과를 확인할 수 없습니다.', unlock:false, verified:false};
}
