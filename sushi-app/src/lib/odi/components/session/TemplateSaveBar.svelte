<script lang="ts">
	import { templateMutationBusy } from '$lib/odi/domain/templateMutation';
	import { template, isTemplateDirty } from '$lib/odi/stores/template';
	import Button from '$lib/odi/components/common/Button.svelte';
	let saving = $state(false),
		message = $state(''),
		failed = $state(false);
	const title = $derived(
		$template?.type === 'presentation'
			? $template.environment.title
			: $template?.environment.position
	);
	async function save() {
		if (saving) return;
		saving = true;
		message = '';
		failed = false;
		try {
			await template.saveBaseline();
			message = '기본 환경을 저장했어요.';
		} catch (e) {
			failed = true;
			message = e instanceof Error ? e.message : '저장 실패';
		} finally {
			saving = false;
		}
	}
</script>

<aside class="template-save">
	<div>
		<strong>{title || '새 환경'}</strong>
		<p>
			{$template?.id
				? $isTemplateDirty
					? '이번 세션에서 수정됨'
					: '저장된 기본 환경'
				: '새로운 환경 · 처음 저장하거나 시작할 때 템플릿이 만들어져요'}
		</p>
	</div>
	<Button variant="secondary" onclick={save} disabled={saving || $templateMutationBusy}
		>{saving
			? '저장 중…'
			: $template?.id
				? '이 템플릿의 기본 환경으로 저장'
				: '새 환경 저장'}</Button
	>
	{#if message}<p class:error={failed} role="status">{message}</p>{/if}
</aside>

<style>
	.template-save {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
		padding: 18px 22px;
		border: 1px solid var(--cool-grey-light-active, #d9ddeb);
		border-radius: 14px;
		background: var(--blue-light, #f4f6ff);
	}
	p {
		margin: 5px 0 0;
		color: var(--text-secondary);
		font-size: 14px;
	}
	.error {
		color: #bc283f;
	}
</style>
