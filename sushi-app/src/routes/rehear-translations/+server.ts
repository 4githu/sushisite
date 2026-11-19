import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { authorized, changeReviewer, entries, publish, readState, reviewerEmails } from '$lib/server/rehear-translations/store';
const headers = {'cache-control':'no-store', 'x-content-type-options':'nosniff'};
export const GET: RequestHandler = async ({request,url}) => {
  try {
    const state = await readState();
    if (url.searchParams.get('review') === '1') {
      const user = await authorized(request.headers.get('cookie'));
      if (!user) return json({error:'허용된 계정으로 로그인해 주세요.'}, {status:403,headers});
      return json({version:state.version,overrides:state.overrides,entries:entries(),email:user.email,reviewers:await reviewerEmails()}, {headers});
    }
    return json({version:state.version,overrides:state.overrides}, {headers});
  } catch { return json({error:'번역 정보를 불러오지 못했습니다.'},{status:503,headers}); }
};
export const POST: RequestHandler = async ({request,url}) => {
  const origin = request.headers.get('origin');
  if (!origin || origin !== url.origin || !request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) return json({error:'요청 출처를 확인할 수 없습니다.'},{status:403,headers});
  try {
    const user = await authorized(request.headers.get('cookie'));
    if (!user) return json({error:'편집 권한이 없거나 로그인이 만료되었습니다.'},{status:403,headers});
    const body = await request.json();
    if (body?.action === 'add-reviewer' || body?.action === 'remove-reviewer') {
      if (typeof body.email !== 'string') return json({error:'이메일을 확인해 주세요.'},{status:400,headers});
      const reviewers = await changeReviewer(body.email,body.action === 'add-reviewer' ? 'add' : 'remove',user.email);
      return json({reviewers},{headers});
    }
    if (!Number.isSafeInteger(body?.version) || typeof body?.id !== 'string' || typeof body?.english !== 'string') return json({error:'입력값을 확인해 주세요.'},{status:400,headers});
    const result = await publish(body.version,{id:body.id,english:body.english},user.email);
    if (result.conflict) return json({error:'다른 변경이 저장되었습니다. 목록을 새로 불러온 뒤 다시 수정해 주세요.'},{status:409,headers});
    return json({version:result.state.version,overrides:result.state.overrides},{headers});
  } catch (e) {
    if (e instanceof Error && ['Invalid email','Too many reviewers'].includes(e.message)) return json({error:'이메일 형식 또는 검수자 수를 확인해 주세요.'},{status:400,headers});
    if (e instanceof Error && e.message === 'Invalid translation') return json({error:'문구는 비어 있을 수 없고 2,000자를 넘을 수 없습니다.'},{status:400,headers});
    return json({error:'저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'},{status:503,headers});
  }
};
