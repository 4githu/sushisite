<script lang="ts">
  const { title = 'Popup card', description = '간단한 카드 설명을 추가할 수 있습니다.', children } = $props();
</script>

<div class="rehear-popup-card">
  <div class="popup-card-head">
    <div class="popup-card-title">{title}</div>
  </div>
  <div class="popup-card-body">
    <p class="popup-card-description">{description}</p>
    {@render children()}
  </div>
</div>
