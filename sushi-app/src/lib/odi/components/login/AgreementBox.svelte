<!-- src/lib/odi/components/login/AgreementBox.svelte -->
<script lang="ts">
	import {
		home as CheckBox,
		home as CheckBoxOutlineBlank,
		home as ChevronRight
	} from "$lib/odi/icons";

	let {
		allAgreed = $bindable(false),
		serviceAgreed = $bindable(false),
		privacyAgreed = $bindable(false),
		marketingAgreed = $bindable(false),
		onOpenTerm
	}: {
		allAgreed?: boolean;
		serviceAgreed?: boolean;
		privacyAgreed?: boolean;
		marketingAgreed?: boolean;
		onOpenTerm?: (type: "all" | "service" | "privacy" | "marketing") => void;
	} = $props();

	function toggleAll() {
		const next = !allAgreed;
		allAgreed = next;
		serviceAgreed = next;
		privacyAgreed = next;
		marketingAgreed = next;
	}

	function syncAll() {
		allAgreed = serviceAgreed && privacyAgreed && marketingAgreed;
	}

	function toggleService() {
		serviceAgreed = !serviceAgreed;
		syncAll();
	}

	function togglePrivacy() {
		privacyAgreed = !privacyAgreed;
		syncAll();
	}

	function toggleMarketing() {
		marketingAgreed = !marketingAgreed;
		syncAll();
	}
</script>

<div class="agreement-section">
	<p class="agreement-label text-body-active">약관 동의</p>

	<div class="agreement-box">
		<div class="agreement-row">
			<button type="button" class="check-area clickable" onclick={toggleAll}>
				<img src={allAgreed ? CheckBox : CheckBoxOutlineBlank} alt="" />
				<span class="text-body">모든 약관에 동의합니다.</span>
			</button>

			<button type="button" class="term-button clickable" onclick={() => onOpenTerm?.("all")}>
				<span>전문 보기</span>
				<img src={ChevronRight} alt="" />
			</button>
		</div>

		<div class="agreement-row">
			<button type="button" class="check-area clickable" onclick={toggleService}>
				<img src={serviceAgreed ? CheckBox : CheckBoxOutlineBlank} alt="" />
				<span class="text-body">[필수] 서비스 이용약관 동의</span>
			</button>

			<button type="button" class="term-button clickable" onclick={() => onOpenTerm?.("service")}>
				<span>전문 보기</span>
				<img src={ChevronRight} alt="" />
			</button>
		</div>

		<div class="agreement-row">
			<button type="button" class="check-area clickable" onclick={togglePrivacy}>
				<img src={privacyAgreed ? CheckBox : CheckBoxOutlineBlank} alt="" />
				<span class="text-body">[필수] 개인정보 수집 및 이용 동의</span>
			</button>

			<button type="button" class="term-button clickable" onclick={() => onOpenTerm?.("privacy")}>
				<span>전문 보기</span>
				<img src={ChevronRight} alt="" />
			</button>
		</div>

		<div class="agreement-row">
			<button type="button" class="check-area clickable" onclick={toggleMarketing}>
				<img src={marketingAgreed ? CheckBox : CheckBoxOutlineBlank} alt="" />
				<span class="text-body">[선택] 서비스 소식 및 혜택 알림 수신 동의</span>
			</button>

			<button type="button" class="term-button clickable" onclick={() => onOpenTerm?.("marketing")}>
				<span>전문 보기</span>
				<img src={ChevronRight} alt="" />
			</button>
		</div>
	</div>
</div>

<style>
	.agreement-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.agreement-label {
		color: var(--brand-black);
	}

	.agreement-box {
		width: 100%;
		padding: var(--space-4) var(--space-5);
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.agreement-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-5);
	}

	.check-area {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		color: var(--brand-black);
		text-align: left;
	}

	.check-area img {
		width: 24px;
		height: 24px;
		object-fit: contain;
		flex-shrink: 0;
	}

	.term-button {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--text-secondary);
		font-size: var(--caption-size);
		font-weight: var(--font-medium);
		white-space: nowrap;
	}

	.term-button img {
		width: 15px;
		height: 15px;
		object-fit: contain;
	}
</style>