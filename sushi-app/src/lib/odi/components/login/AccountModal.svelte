<!-- src/lib/odi/components/login/AccountModal.svelte -->
<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
 import { locale, copy } from "$lib/odi/i18n";
	import { onMount } from "svelte";
	import { goto } from "$app/navigation";
	import Modal from "$lib/odi/components/login/Modal.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import { auth } from "$lib/stores/mainauth";
	import { odiuser } from "$lib/odi/stores";
	import { authPerson as Person, authMail as Mail, authLock as Lock } from "$lib/odi/icons";
	import { API_BASE as API } from '$lib/config/api';

	const titleId = "account-modal-title";

	let {
		onClose
	}: {
		onClose?: () => void;
	} = $props();

	const authPayload = $derived($auth);
	const authId = $derived(authPayload?.data?.id ?? "");
	const currentEmail = $derived(authPayload?.data?.email ?? "");
	const currentName = $derived(authPayload?.data?.name ?? "");
	const currentOdiUser = $derived($odiuser);

	let name = $state("");
	let email = $state("");
	let nickname = $state("");
	let currentPassword = $state("");
	let newPassword = $state("");
	let newPasswordConfirm = $state("");
	let deletePassword = $state("");
	let loading = $state(false);
	let message = $state("");
	let errorMessage = $state("");
	let verified = $state<boolean | undefined>(undefined);
	let code = $state("");
	let verificationMessage = $state("");
	let verificationError = $state("");
	let resendAfter = $state(0);
	let now = $state(Date.now());
	let savedEmail = $state("");
	const needsVerification = $derived(verified === false);

	const passwordValid = $derived(newPassword.length === 0 || /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/.test(newPassword));
	const passwordError = $derived(newPassword.length > 0 && !passwordValid ? "영문, 숫자, 특수문자 포함 8자리 이상 입력해주세요" : "");
	const passwordConfirmError = $derived(newPasswordConfirm.length > 0 && newPassword !== newPasswordConfirm ? "비밀번호가 일치하지 않습니다" : "");
	const canSaveProfile = $derived(!loading && authId && name.trim().length > 0 && nickname.trim().length >= 2 && (email.trim() === savedEmail || currentPassword.length > 0));
	const canChangePassword = $derived(!loading && authId && currentPassword.length > 0 && newPassword.length > 0 && passwordValid && newPassword === newPasswordConfirm);
	const canDeleteAccount = $derived(!loading && authId && deletePassword.length > 0);

	// Capture the authenticated profile once when opening this editable form.
	onMount(() => {
		name = currentName;
		email = currentEmail;
		savedEmail = currentEmail;
		nickname = currentOdiUser?.config?.profile?.nickname ?? currentName;
		verified = authPayload?.data?.email_verified;
		const timer = window.setInterval(() => (now = Date.now()), 1000);
		return () => window.clearInterval(timer);
	});

	async function fetchJson(res: Response) {
		const data = await res.json().catch(() => null);

		if (!res.ok) {
			if (res.status === 401) throw new Error("로그인이 만료되었습니다. 다시 로그인해주세요.");
			throw new Error(typeof data?.detail === 'string' ? data.detail : data?.message ?? "요청 실패");
		}

		return data;
	}

	async function saveProfile() {
		if (!canSaveProfile) return;

		loading = true;
		message = "";
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/user`, {
				method: "PUT",
				credentials: "include",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					id: authId,
					name,
					password: email.trim() !== savedEmail ? currentPassword : undefined,
					email: email.trim() || undefined
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "회원정보 수정에 실패했습니다.");
			}

			// Profile PUT and ODI nickname are independent writes.
			const changedEmail = data.data.email !== savedEmail;
			savedEmail = data.data.email;
			currentPassword = "";
			verified = data.data.email_verified;
			if (changedEmail) { code = ""; resendAfter = 0; verificationMessage = ""; }
			message = "프로필 저장 완료";
			try { await auth.check(true); window.dispatchEvent(new Event('personal-auth-updated')); }
			catch { message += ". 최신 표시 갱신에 실패했습니다. 연결을 확인해주세요"; }
			if (nickname.trim() !== (currentOdiUser?.config?.profile?.nickname ?? currentName)) {
				try {
					const currentConfig = currentOdiUser?.config ?? {};
					await odiuser.updateConfig({ ...currentConfig, profile: { ...(currentConfig.profile ?? {}), nickname: nickname.trim() } });
					message += ". ODI 닉네임 저장 완료";
				} catch {
					errorMessage = "프로필은 저장됐지만 ODI 닉네임 저장 실패. 다시 시도해주세요.";
				}
			}
		} catch (error) {
			errorMessage = error instanceof TypeError ? "네트워크 연결을 확인하고 다시 시도해주세요." : error instanceof Error ? error.message : "회원정보 수정에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	async function sendVerification() {
		if (loading || !needsVerification || Date.now() < resendAfter) return;
		loading = true;
		verificationError = "";
		try {
			const res = await fetch(`${API}/auth/user/email-verification/send`, { method: 'POST', credentials: 'include' });
			if (res.status === 429) {
				resendAfter = Date.now() + 60000;
				throw new Error('재전송 제한 중입니다. 잠시 후 다시 시도해주세요.');
			}
			await fetchJson(res);
			resendAfter = Date.now() + 60000;
			verificationMessage = "인증 메일을 보냈습니다. 받은 편지함을 확인해주세요.";
		} catch (error) {
			verificationError = error instanceof TypeError ? "네트워크 연결을 확인하고 다시 시도해주세요." : error instanceof Error ? error.message : "발송에 실패했습니다.";
		} finally { loading = false; }
	}

	async function confirmVerification() {
		if (loading || !code.trim() || !needsVerification) return;
		loading = true;
		verificationError = "";
		try {
			const data = await fetchJson(await fetch(`${API}/auth/user/email-verification/confirm`, {
				method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ code: code.trim() })
			}));
			if (!data.success || data.data?.email_verified !== true) throw new Error("확인 상태를 확인하지 못했습니다.");
			code = "";
			verified = true;
			verificationMessage = "이메일 확인 완료";
			try { await auth.check(true); window.dispatchEvent(new Event('personal-auth-updated')); }
			catch { verificationError = '확인은 완료됐지만 최신 표시 갱신에 실패했습니다. 다시 열어 확인해주세요.'; }
		} catch (error) {
			verificationError = error instanceof TypeError ? "네트워크 연결을 확인하고 다시 시도해주세요." : error instanceof Error ? error.message : "확인에 실패했습니다.";
		} finally { loading = false; }
	}

	async function changePassword() {
		if (!canChangePassword) return;

		loading = true;
		message = "";
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/user`, {
				method: "PUT",
				credentials: "include",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					id: authId,
					password: currentPassword,
					new_password: newPassword
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "비밀번호 변경에 실패했습니다.");
			}

			currentPassword = "";
			newPassword = "";
			newPasswordConfirm = "";
			message = "비밀번호를 변경했습니다.";
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "비밀번호 변경에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	async function logout() {
		await Promise.all([
			fetch(`${API}/auth/logout`, {
				method: "POST",
				credentials: "include"
			}).catch(() => null),
			odiuser.logout().catch(() => null)
		]);

		auth.logout();
		onClose?.();
		goto("/odi");
	}

	async function deleteAccount() {
		if (!canDeleteAccount) return;

		const confirmed = window.confirm("정말 계정을 삭제할까요? 삭제 후 복구할 수 없습니다.");

		if (!confirmed) return;

		loading = true;
		message = "";
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/user/${authId}`, {
				method: "DELETE",
				credentials: "include",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ password: deletePassword })
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "계정 삭제에 실패했습니다.");
			}

			await odiuser.logout().catch(() => null);
			auth.logout();
			onClose?.();
			goto("/odi");
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "계정 삭제에 실패했습니다.";
		} finally {
			loading = false;
		}
	}
</script>

<Modal width="720px" minHeight="680px" labelledby={titleId} {onClose}>
	<div class="account-modal">
		<div class="title-group">
			<p class="page-label text-caption-main">Account</p>
			<h2 id={titleId} class="text-title-main">{tr($siteLocale, "회원정보 관리")}</h2>
			<p class="subtitle text-caption-main">{currentOdiUser?.config?.profile?.nickname ?? currentName ?? "사용자"}님의 계정 정보를 관리합니다.</p>
		</div>

		{#if message}
			<p class="message text-caption-medium">{message}</p>
		{/if}

		{#if errorMessage}
			<p class="error-message text-caption-medium" role="alert">{errorMessage}</p>
		{/if}
		{#if needsVerification}
			<section class="section" aria-label={tr($siteLocale, "이메일 확인")}>
				<h3 class="text-title-small">{tr($siteLocale, "새 이메일 확인 필요")}</h3>
				<p>{tr($siteLocale, "현재 이메일을 확인해주세요. 확인 전에도 서비스를 계속 사용할 수 있습니다.")}</p>
				{#if verificationMessage}<p role="status">{verificationMessage}</p>{/if}
				{#if verificationError}<p class="error-message" role="alert">{verificationError}</p>{/if}
				<div class="grid"><AuthField label={tr($siteLocale, "인증 코드")} type="password" placeholder={tr($siteLocale, "메일로 받은 코드")} icon={Mail} bind:value={code} /></div>
				<div class="section-actions verification-actions">
					<Button variant="outline" disabled={loading || now < resendAfter} onclick={sendVerification}>{resendAfter > now ? `재전송 대기 ${Math.ceil((resendAfter - now) / 1000)}초` : tr($siteLocale, "인증 메일 발송 / 재전송")}</Button>
					<Button variant="primary" disabled={loading || !code.trim()} onclick={confirmVerification}>{tr($siteLocale, "코드 확인")}</Button>
				</div>
			</section>
		{:else if verified === true}
			<p class="message text-caption-medium">{verificationMessage || '이메일 확인 완료'}</p>
		{/if}

		<section class="section">
			<h3 class="text-title-small">{tr($siteLocale, "기본 정보")}</h3>

			<div class="grid">
				<AuthField label={tr($siteLocale, "이름")} placeholder={tr($siteLocale, "이름")} icon={Person} bind:value={name} />
				<AuthField label={copy($locale, "이메일")} type="email" placeholder={copy($locale, "이메일")} icon={Mail} bind:value={email} />
				{#if email.trim() !== savedEmail}
					<AuthField label={tr($siteLocale, "이메일 변경 확인 비밀번호")} type="password" placeholder={tr($siteLocale, "현재 비밀번호")} icon={Lock} bind:value={currentPassword} />
				{/if}
				<AuthField label={tr($siteLocale, "ODI 닉네임")} placeholder={tr($siteLocale, "사이드바와 홈에 표시할 닉네임")} icon={Person} bind:value={nickname} />
			</div>

			<div class="section-actions">
				<Button variant="primary" width="180px" disabled={!canSaveProfile} onclick={saveProfile}>
					{tr($siteLocale, "정보 수정")}
				</Button>
			</div>
		</section>

		<section class="section">
			<h3 class="text-title-small">{tr($siteLocale, "비밀번호 변경")}</h3>

			<div class="grid">
				<AuthField label={tr($siteLocale, "현재 비밀번호")} type="password" placeholder={tr($siteLocale, "현재 비밀번호")} icon={Lock} bind:value={currentPassword} />
				<AuthField label={tr($siteLocale, "새 비밀번호")} type="password" placeholder={tr($siteLocale, "영문, 숫자, 특수문자 포함 8자리 이상")} icon={Lock} bind:value={newPassword} error={passwordError} />
				<AuthField label={tr($siteLocale, "새 비밀번호 확인")} type="password" placeholder={tr($siteLocale, "새 비밀번호 확인")} icon={Lock} bind:value={newPasswordConfirm} error={passwordConfirmError} />
			</div>

			<div class="section-actions">
				<Button variant="outline" width="180px" disabled={!canChangePassword} onclick={changePassword}>
					{tr($siteLocale, "비밀번호 변경")}
				</Button>
			</div>
		</section>

		<section class="section danger-section">
			<h3 class="text-title-small">{tr($siteLocale, "계정 관리")}</h3>

			<div class="danger-box">
				<div>
					<strong>{tr($siteLocale, "로그아웃")}</strong>
					<p>{tr($siteLocale, "현재 브라우저에서 로그아웃합니다.")}</p>
				</div>

				<Button variant="secondary" width="140px" onclick={logout}>
					{tr($siteLocale, "로그아웃")}
				</Button>
			</div>

			<div class="danger-box">
				<div>
					<strong>{tr($siteLocale, "계정 삭제")}</strong>
					<p>{tr($siteLocale, "계정과 로그인 정보를 삭제합니다. 삭제 후 복구할 수 없습니다.")}</p>
				</div>

				<div class="delete-control">
					<AuthField label={tr($siteLocale, "삭제 확인 비밀번호")} type="password" placeholder={tr($siteLocale, "비밀번호 입력")} icon={Lock} bind:value={deletePassword} />
					<Button variant="outline" width="140px" disabled={!canDeleteAccount} onclick={deleteAccount}>
						{tr($siteLocale, "탈퇴")}
					</Button>
				</div>
			</div>
		</section>
	</div>
</Modal>

<style>
	.account-modal {
		width: 100%;
		min-width: 0;
		min-height: 680px;
		max-height: min(860px, calc(100vh - 48px));
		padding: 42px;
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		overflow-x: hidden;
		overflow-y: auto;
		background: var(--surface);
		border-radius: var(--radius-md);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.page-label {
		color: var(--primary);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.message {
		padding: var(--space-3) var(--space-4);
		border-radius: var(--radius-sm);
		background: rgba(68, 198, 153, 0.15);
		color: #44c699;
	}

	.error-message {
		padding: var(--space-3) var(--space-4);
		border-radius: var(--radius-sm);
		background: var(--accent-light);
		color: var(--accent);
	}

	.section {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		padding-top: var(--space-5);
		border-top: 1px solid var(--border);
	}

	.grid {
		min-width: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-5);
	}

	.verification-actions { gap: var(--space-3); flex-wrap: wrap; }
	.section-actions {
		display: flex;
		justify-content: flex-end;
	}

	.danger-section {
		padding-bottom: var(--space-2);
	}

	.danger-box {
		padding: var(--space-4);
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-5);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.danger-box > :first-child {
		min-width: 0;
	}

	.danger-box strong {
		color: var(--brand-black);
		font-size: 18px;
		font-weight: var(--font-bold);
	}

	.danger-box p {
		margin-top: var(--space-1);
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
	}

	.delete-control {
		width: min(100%, 460px);
		min-width: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) 140px;
		align-items: flex-end;
		gap: var(--space-3);
	}

	.delete-control :global(.field) {
		min-width: 0;
	}

	@media (max-width: 780px) {
		.account-modal {
			padding: var(--space-6);
		}

		.grid,
		.danger-box,
		.delete-control {
			grid-template-columns: 1fr;
			align-items: stretch;
			width: 100%;
		}

		.section-actions :global(.button),
		.danger-box :global(.button) {
			width: 100% !important;
		}
	}
</style>
