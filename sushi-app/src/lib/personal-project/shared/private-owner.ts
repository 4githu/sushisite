import { checkPersonalAuth, privateCacheUser } from './auth';
// A foreground refresh briefly clears the auth cache. Await its result rather than
// interpreting that intermediate empty cache as a different account.
export async function verifiedPrivateOwner(): Promise<string> {
	for (let attempt = 0; attempt < 2; attempt++) {
		const user = await checkPersonalAuth();
		if (user?.data.id !== undefined && user?.data.id !== null) return String(user.data.id);
	}
	throw new Error('로그인 상태를 다시 확인해주세요.');
}
export async function samePrivateOwner(account: string) {
	if (account && String(privateCacheUser()) === account) return true;
	return (await verifiedPrivateOwner()) === account;
}
