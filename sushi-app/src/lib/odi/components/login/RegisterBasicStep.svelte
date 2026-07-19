<!-- src/lib/odi/components/login/RegisterBasicStep.svelte -->
<script lang="ts">
	import {
		home as Person,
		home as Mail,
		home as Lock
	} from "$lib/odi/icons";

	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import AgreementBox from "$lib/odi/components/login/AgreementBox.svelte";

	let {
		name = $bindable(""),
		email = $bindable(""),
		password = $bindable(""),
		passwordConfirm = $bindable(""),
		allAgreed = $bindable(false),
		serviceAgreed = $bindable(false),
		privacyAgreed = $bindable(false),
		marketingAgreed = $bindable(false),
		passwordError = "",
		passwordConfirmError = "",
		nameSuccess = "",
		onOpenTerm
	}: {
		name?: string;
		email?: string;
		password?: string;
		passwordConfirm?: string;
		allAgreed?: boolean;
		serviceAgreed?: boolean;
		privacyAgreed?: boolean;
		marketingAgreed?: boolean;
		passwordError?: string;
		passwordConfirmError?: string;
		nameSuccess?: string;
		onOpenTerm?: (type: "all" | "service" | "privacy" | "marketing") => void;
	} = $props();
</script>

<div class="basic-step">
	<div class="field-grid">
		<AuthField
			label="이름"
			placeholder="이름을 입력해주세요"
			icon={Person}
			autocomplete="name"
			bind:value={name}
			success={nameSuccess}
			required
		/>

		<AuthField
			label="이메일"
			type="email"
			placeholder="이메일 주소를 입력해주세요"
			icon={Mail}
			autocomplete="email"
			bind:value={email}
			required
		/>

		<AuthField
			label="비밀번호"
			type="password"
			placeholder="영문, 숫자, 특수문자 포함 8자리 이상"
			icon={Lock}
			autocomplete="new-password"
			bind:value={password}
			error={passwordError}
			required
		/>

		<AuthField
			label="비밀번호 확인"
			type="password"
			placeholder="비밀번호를 다시 입력해주세요"
			icon={Lock}
			autocomplete="new-password"
			bind:value={passwordConfirm}
			error={passwordConfirmError}
			success={passwordConfirm && !passwordConfirmError ? "비밀번호가 일치합니다" : ""}
			required
		/>
	</div>

	<AgreementBox
		bind:allAgreed
		bind:serviceAgreed
		bind:privacyAgreed
		bind:marketingAgreed
		{onOpenTerm}
	/>
</div>

<style>
	.basic-step {
		display: flex;
		flex-direction: column;
		gap: 48px;
	}

	.field-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 40px;
	}

	@media (max-width: 1100px) {
		.field-grid {
			grid-template-columns: 1fr;
		}
	}
</style>