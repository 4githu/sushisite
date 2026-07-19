<script lang="ts">
	import Icon from '../_components/Icon.svelte';
	import PageHeader from '../_components/PageHeader.svelte';
	import StepIndicator from '../_components/StepIndicator.svelte';

	let deckFile = $state('');
	let referenceFile = $state('');
	let script = $state('');

	function handleFile(event: Event, target: 'deck' | 'reference') {
		const input = event.currentTarget as HTMLInputElement;
		const fileName = input.files?.[0]?.name ?? '';

		if (target === 'deck') {
			deckFile = fileName;
		} else {
			referenceFile = fileName;
		}
	}
</script>

<div class="rehear-page">
	<PageHeader
		title="자료 업로드"
		description="발표 준비에 필요한 자료를 업로드하면 더 정교한 피드백을 받을 수 있어요."
	/>

	<StepIndicator currentStep={2} />

	<div class="rehear-upload-layout">
		<section class="rehear-upload-form" aria-label="자료 업로드 입력">
			<div class="rehear-upload-block">
				<h2 class="rehear-section-title compact">
					<span class="rehear-title-icon"><Icon name="document" size={21} /></span>
					발표 슬라이드 PDF <small>*</small>
				</h2>
				<label class="rehear-upload-zone">
					<input type="file" accept=".pdf" onchange={(event) => handleFile(event, 'deck')} />
					<span>
						<Icon name="upload" size={34} />
						<strong>{deckFile || 'PDF 파일을 드래그하거나 클릭하여 업로드 해주세요'}</strong>
						<span>최대 300MB</span>
					</span>
				</label>
			</div>

			<div class="rehear-upload-block">
				<h2 class="rehear-section-title compact">
					<span class="rehear-title-icon"><Icon name="document" size={21} /></span>
					발표 슬라이드 PDF <small>*</small>
				</h2>
				<label class="rehear-upload-zone">
					<input type="file" accept=".pdf" onchange={(event) => handleFile(event, 'reference')} />
					<span>
						<Icon name="upload" size={34} />
						<strong>{referenceFile || 'PDF 파일을 드래그하거나 클릭하여 업로드 해주세요'}</strong>
						<span>최대 300MB</span>
					</span>
				</label>
			</div>

			<div class="rehear-upload-block">
				<h2 class="rehear-section-title compact">
					<span class="rehear-title-icon"><Icon name="document" size={21} /></span>
					발표 슬라이드 PDF <small>*</small>
				</h2>
				<div class="rehear-textarea-wrap">
					<textarea
						class="rehear-textarea"
						bind:value={script}
						maxlength={10000}
						placeholder="발표 스크립트 텍스트를 입력해주세요."
						aria-label="발표 스크립트 텍스트"
					></textarea>
					<span class="rehear-counter">{script.length}/ 10,000</span>
				</div>
				<div class="rehear-script-action">
					<button type="button" class="rehear-outline-button">
						<Icon name="arrow-right" size={20} />
						<span>스크립트 검사하기</span>
					</button>
				</div>
			</div>
		</section>

		<aside class="rehear-tip-card" aria-label="자료 업로드 팁">
			<h2>자료 업로드 TIP</h2>
			<div class="rehear-upload-graphic">
				업로드된 자료는 암호화되어 안전하게 저장되며, 사용자의 동의 없이 외부로 공유되지 않습니다.
				<span class="rehear-upload-lock"></span>
			</div>
			<div class="rehear-tip-list">
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="target" size={28} /></span>
					<p>
						<strong>더 정확한 질문 생성</strong>
						<span>풍부한 자료를 기반으로 지원자의 경험과 역량에 맞춘 정교한 질문을 생성합니다.</span
						>
					</p>
				</div>
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="document" size={28} /></span>
					<p>
						<strong>다양한 형식 지원</strong>
						<span>PDF, PPT, DOCX, TXT, 이미지 등 다양한 형식의 파일을 지원합니다.</span>
					</p>
				</div>
			</div>
		</aside>
	</div>

	<div class="rehear-actions">
		<a class="rehear-secondary-button" href="/rehear">이전 단계</a>
		<a class="rehear-primary-button" href="/rehear/presentation/setup/audience">
			<span>다음 단계</span>
			<Icon name="arrow-right" size={22} />
		</a>
	</div>
</div>
