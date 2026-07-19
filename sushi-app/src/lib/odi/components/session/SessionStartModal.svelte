<script lang="ts">
	import { onMount } from "svelte";

	import SessionTypeCard from "$lib/odi/components/session/SessionTypeCard.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";

	import {
		Close
	} from "$lib/odi/icons";

	import PresentationImage from "$lib/odi/assets/session-presentation.png";
	import InterviewImage from "$lib/odi/assets/session-interview.png";

	type SessionType =
		| "presentation"
		| "interview";

	let {
		onclose,
		onselect,
		onload
	}: {
		onclose?: () => void;
		onselect?: (type: SessionType) => void;
		onload?: () => void;
	} = $props();

	let selectedType = $state<SessionType | null>(null);

	function close() {
		onclose?.();
	}

	function startSelectedSession() {
		if (selectedType === null) return;

		onselect?.(selectedType);
	}

	function loadPrevious() {
		onload?.();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === "Escape") {
			close();
		}
	}

	onMount(() => {
		window.addEventListener(
			"keydown",
			handleKeydown
		);

		return () => {
			window.removeEventListener(
				"keydown",
				handleKeydown
			);
		};
	});

	function handleOverlayKeydown(event: KeyboardEvent) {
		if (
			event.key === "Escape" ||
			event.key === "Enter" ||
			event.key === " "
		) {
			event.preventDefault();
			close();
		}
	}
</script>

<div
	class="modal-overlay"
	role="presentation"
	tabindex="-1"
	onclick={close}
>
	<div
		class="popup-card"
		role="button"
		tabindex="0"
		onclick={(event) => event.stopPropagation()}
		onkeydown={handleOverlayKeydown}
	>
		<button
			type="button"
			class="close-button clickable"
			aria-label="닫기"
			onclick={close}
		>
			<img
				src={Close}
				alt=""
			/>
		</button>

		<div class="modal-content">

			<header class="modal-header">

				<h2
					id="session-start-title"
					class="modal-title"
				>
					새 세션을 시작할까요?
				</h2>

				<p class="modal-description text-caption-medium">
					연습할 유형을 선택하고,
					맞춤 설정을 시작해보세요.
				</p>

			</header>

			<div class="card-row">

				<SessionTypeCard
					title="발표 연습"
					description={`발표 시뮬레이션을 통해
전달력과 설득력을 향상시켜요.`}
					image={PresentationImage}
					selected={selectedType === "presentation"}
					onselect={() => selectedType = "presentation"}
				/>

				<SessionTypeCard
					title="면접 연습"
					description={`면접 시뮬레이션으로
질문 대응력을 키워요.`}
					image={InterviewImage}
					selected={selectedType === "interview"}
					onselect={() => selectedType = "interview"}
				/>

			</div>

			<Button
				variant="primary"
				width="100%"
				disabled={!selectedType}
				onclick={startSelectedSession}
			>
				이 유형으로 시작하기
			</Button>

			<button
				type="button"
				class="load-button clickable"
				onclick={loadPrevious}
			>
				기존 세션 불러오기
			</button>

		</div>

	</div>

</div>

<style>
.modal-overlay{

	position:fixed;

	inset:0;

	z-index:1000;

	display:flex;

	align-items:center;
	justify-content:center;

	padding:40px;

	background:rgba(3,8,18,.55);

	backdrop-filter:blur(2px);
}



.popup-card{
	position:relative;

	width:760px;

	background:var(--surface);

	border-radius:var(--radius-md);

	box-shadow:0 0 16px rgba(0,0,0,.15);
}

.close-button{

	position:absolute;

	top:24px;
	right:24px;

	width:32px;
	height:32px;

	display:flex;

	align-items:center;
	justify-content:center;
}

.close-button img{

	width:20px;
	height:20px;
}

.modal-content{

	padding:56px 40px 40px;

	display:flex;

	flex-direction:column;

	align-items:center;

	gap:24px;
}

.modal-header{

	width:100%;

	display:flex;

	flex-direction:column;

	align-items:center;

	gap:12px;

	text-align:center;
}

.modal-title{

	color:var(--brand-black);

	font-size:24px;

	font-weight:700;
}

.modal-description{

	color:var(--text-secondary);
}

.card-row{

	width:100%;

	display:flex;

	justify-content:center;

	gap:28px;
}

.load-button{

	width:100%;
	height:64px;

	display:flex;

	align-items:center;
	justify-content:center;

	border-radius:var(--radius-sm);

	background:var(--blue-light);

	color:var(--primary);

	font-weight:500;

	transition:var(--transition-fast);
}

.load-button:hover{

	background:var(--blue-light-hover);
}
</style>