<script lang="ts">
  import Slider from './lib/components/Slider.svelte';
  import Select from './lib/components/Select.svelte';
  import SegmentedControl from './lib/components/SegmentedControl.svelte';
  import ProgressStepper from './lib/components/ProgressStepper.svelte';
  import Button from './lib/components/Button.svelte';
  import InputField from './lib/components/InputField.svelte';
  import TopBar from './lib/components/TopBar.svelte';
  import Chip from './lib/components/Chip.svelte';
  import PopupCard from './lib/components/PopupCard.svelte';
  import Card from './lib/components/Card.svelte';

  const timeSteps = ['10분', '20분', '30분', '40분', '50분', '60분'];
  const audienceSteps = ['1', '10', '20', '30', '40', '50+'];
  const sessionSteps = ['면접 기본 정보', '자료 업로드', 'AI 면접관 설정', '세션 확인'];
  const segmentOptions = ['일대일', '일대다', '다대다'];
  const countOptions = ['1개', '2개', '3개'];
</script>

<TopBar title="Re:hear" subtitle="Practice. Feedback. Real Growth." />

<main class="rehear-demo-page">
  <section class="rehear-demo-section">
    <h2>Slider</h2>
    <Slider values={timeSteps} activeIndex={2} />
    <Slider values={audienceSteps} activeIndex={1} />
  </section>

  <section class="rehear-demo-section">
    <h2>Select</h2>
    <div class="rehear-demo-row">
      <Select label="발표 시간" value="20분" placeholder="선택하세요" />
      <Select label="청중 규모" value="10명" />
      <Select label="잠금 선택" value="1명" disabled />
    </div>
  </section>

  <section class="rehear-demo-section">
    <h2>Segmented Control</h2>
    <SegmentedControl options={segmentOptions} selectedIndex={0} />
    <SegmentedControl options={countOptions} selectedIndex={2} />
  </section>

  <section class="rehear-demo-section">
    <h2>Progress Stepper</h2>
    <ProgressStepper steps={sessionSteps} current={1} />
  </section>

  <section class="rehear-demo-section">
    <h2>Inputs</h2>
    <div class="rehear-demo-row">
      <InputField label="발표 제목" placeholder="예: AI 서비스 커뮤니케이션 전략" />
      <InputField label="발표 스크립트" value="작성중" state="filled" />
    </div>
  </section>

  <section class="rehear-demo-section">
    <h2>Buttons</h2>
    <div class="rehear-demo-row">
      <Button label="다음 단계" variant="primary" size="lg" />
      <Button label="취소" variant="secondary" />
      <Button label="비활성" variant="ghost" disabled />
    </div>
  </section>

  <section class="rehear-demo-section">
    <h2>Cards & Popup</h2>
    <div class="rehear-demo-row cards-row">
        <Card title="세션 정보" highlight>
          <div class="card-meta">
            <span>일대다 · 3명</span>
            <span>30분</span>
            <span>청중 10명</span>
          </div>
          <div class="card-row">
            <div class="card-entry">
              <strong>다음 세션</strong>
              <span>6월 26일 금요일 · 14:00</span>
            </div>
            <div class="card-entry">
              <strong>목표</strong>
              <span>AI 서비스 발표 스크립트 피드백</span>
            </div>
          </div>
          <div class="card-badges">
            <span class="card-badge">발표 준비</span>
            <span class="card-badge">Q&A 연습</span>
            <span class="card-badge">피드백 포함</span>
          </div>
        </Card>
        <PopupCard title="팝업 카드" description="설정한 세션 정보를 확인하고 바로 시작해보세요.">
          <div class="popup-card-actions">
            <Button label="변경하기" variant="secondary" />
            <Button label="세션 시작" variant="primary" />
          </div>
        </PopupCard>
    </div>
  </section>

  <section class="rehear-demo-section">
    <h2>Top Bar / Chip</h2>
    <Chip label="추천" variant="accent" />
  </section>
</main>

<style>
  .rehear-demo-page {
    padding: 2rem;
    display: grid;
    gap: 2rem;
  }

  .rehear-demo-section {
    background: white;
    border-radius: 24px;
    padding: 1.5rem;
    box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  }

  .rehear-demo-row {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-top: 1rem;
  }

  .cards-row {
    align-items: flex-start;
  }

  h2 {
    font-size: 1.2rem;
    margin-bottom: 0.75rem;
    color: var(--text-primary);
  }
</style>
