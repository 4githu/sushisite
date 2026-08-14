<!-- src/lib/odi/components/login/AccountModal.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import Modal from "$lib/odi/components/login/Modal.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import { auth } from "$lib/stores/mainauth";
	import { odiuser } from "$lib/odi/stores";
	import { home as Person, home as Mail, home as Lock } from "$lib/odi/icons";
	import { API_BASE as API } from '$lib/config/api';

	const titleId = "account-modal-title";

	let {
		onClose
	}: {
		onClose?: () => void;
	} = $props();

	const authPayload = $derived(auth.get() as any);
	const authId = $derived(authPayload?.data?.id ?? "");
	const currentEmail = $derived(authPayload?.data?.email ?? "");
	const currentName = $derived(authPayload?.data?.name ?? "");
	const currentOdiUser = $derived($odiuser);

	let name = $state("");
	let email = $state("");
	let nickname = $state("");
	let profileInitialized = $state(false);
	let currentPassword = $state("");
	let newPassword = $state("");
	let newPasswordConfirm = $state("");
	let deletePassword = $state("");
	let loading = $state(false);
	let message = $state("");
	let errorMessage = $state("");

	const passwordValid = $derived(newPassword.length === 0 || /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/.test(newPassword));
	const passwordError = $derived(newPassword.length > 0 && !passwordValid ? "영문, 숫자, 특수문자 포함 8자리 이상 입력해주세요" : "");
	const passwordConfirmError = $derived(newPasswordConfirm.length > 0 && newPassword !== newPasswordConfirm ? "비밀번호가 일치하지 않습니다" : "");
	const canSaveProfile = $derived(!loading && authId && name.trim().length > 0 && nickname.trim().length >= 2);
	const canChangePassword = $derived(!loading && authId && currentPassword.length > 0 && newPassword.length > 0 && passwordValid && newPassword === newPasswordConfirm);
	const canDeleteAccount = $derived(!loading && authId && deletePassword.length > 0);

	$effect(() => {
		if (profileInitialized || (!currentName && !currentEmail && !currentOdiUser)) return;
		name = currentName;
		email = currentEmail;
		nickname = currentOdiUser?.config?.profile?.nickname ?? currentName;
		profileInitialized = true;
	});

	async function fetchJson(res: Response) {
		const data = await res.json().catch(() => null);

		if (!res.ok) {
			throw new Error(data?.detail ?? data?.message ?? "요청 실패");
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
					email: email.trim() || undefined
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "회원정보 수정에 실패했습니다.");
			}

			const currentConfig = currentOdiUser?.config ?? {};
			await odiuser.updateConfig({
				...currentConfig,
				profile: {
					...(currentConfig.profile ?? {}),
					nickname: nickname.trim()
				}
			});

			message = "이름·이메일·ODI 닉네임을 수정했습니다.";
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "회원정보 수정에 실패했습니다.";
		} finally {
			loading = false;
		}
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
				credentials: "include"
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
			<h2 id={titleId} class="text-title-main">회원정보 관리</h2>
			<p class="subtitle text-caption-main">{currentOdiUser?.config?.profile?.nickname ?? currentName ?? "사용자"}님의 계정 정보를 관리합니다.</p>
		</div>

		{#if message}
			<p class="message text-caption-medium">{message}</p>
		{/if}

		{#if errorMessage}
			<p class="error-message text-caption-medium">{errorMessage}</p>
		{/if}

		<section class="section">
			<h3 class="text-title-small">기본 정보</h3>

			<div class="grid">
				<AuthField label="이름" placeholder="이름" icon={Person} bind:value={name} />
				<AuthField label="이메일" type="email" placeholder="이메일" icon={Mail} bind:value={email} />
				<AuthField label="ODI 닉네임" placeholder="사이드바와 홈에 표시할 닉네임" icon={Person} bind:value={nickname} />
			</div>

			<div class="section-actions">
				<Button variant="primary" width="180px" disabled={!canSaveProfile} onclick={saveProfile}>
					정보 수정
				</Button>
			</div>
		</section>

		<section class="section">
			<h3 class="text-title-small">비밀번호 변경</h3>

			<div class="grid">
				<AuthField label="현재 비밀번호" type="password" placeholder="현재 비밀번호" icon={Lock} bind:value={currentPassword} />
				<AuthField label="새 비밀번호" type="password" placeholder="영문, 숫자, 특수문자 포함 8자리 이상" icon={Lock} bind:value={newPassword} error={passwordError} />
				<AuthField label="새 비밀번호 확인" type="password" placeholder="새 비밀번호 확인" icon={Lock} bind:value={newPasswordConfirm} error={passwordConfirmError} />
			</div>

			<div class="section-actions">
				<Button variant="outline" width="180px" disabled={!canChangePassword} onclick={changePassword}>
					비밀번호 변경
				</Button>
			</div>
		</section>

		<section class="section danger-section">
			<h3 class="text-title-small">계정 관리</h3>

			<div class="danger-box">
				<div>
					<strong>로그아웃</strong>
					<p>현재 브라우저에서 로그아웃합니다.</p>
				</div>

				<Button variant="secondary" width="140px" onclick={logout}>
					로그아웃
				</Button>
			</div>

			<div class="danger-box">
				<div>
					<strong>계정 삭제</strong>
					<p>계정과 로그인 정보를 삭제합니다. 삭제 후 복구할 수 없습니다.</p>
				</div>

				<div class="delete-control">
					<AuthField label="삭제 확인 비밀번호" type="password" placeholder="비밀번호 입력" icon={Lock} bind:value={deletePassword} />
					<Button variant="outline" width="140px" disabled={!canDeleteAccount} onclick={deleteAccount}>
						탈퇴
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
		overflow: auto;
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
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-5);
	}

	.section-actions {
		display: flex;
		justify-content: flex-end;
	}

	.danger-section {
		padding-bottom: var(--space-2);
	}

	.danger-box {
		padding: var(--space-4);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-5);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		flex-wrap: wrap;
	}

	.danger-box > :first-child {
		min-width: 0;
		flex: 1 1 200px;
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
		width: auto;
		min-width: 0;
		flex: 1 1 320px;
		display: flex;
		align-items: flex-end;
		gap: var(--space-3);
	}

	.delete-control :global(.field) {
		flex: 1;
	}

	@media (max-width: 780px) {
		.account-modal {
			padding: var(--space-6);
		}

		.grid,
		.danger-box,
		.delete-control {
			grid-template-columns: 1fr;
			flex-direction: column;
			align-items: stretch;
			width: 100%;
		}
	}
</style>
