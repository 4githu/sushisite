<script lang="ts">
  const { title = 'Re:hear', subtitle = 'Practice. Feedback. Real Growth.' } = $props();
</script>

<header class="rehear-topbar">
  <div class="rehear-topbar-brand">
    <div class="rehear-topbar-logo">{title}</div>
    <div class="rehear-topbar-subtitle">{subtitle}</div>
  </div>
  <nav class="rehear-topbar-nav">
    <a href="#home" class="rehear-topbar-link">Home</a>
    <a href="#favorites" class="rehear-topbar-link">Favorites</a>
    <a href="#report" class="rehear-topbar-link">Report</a>
    <a href="#practice" class="rehear-topbar-link">My Practice</a>
  </nav>
</header>
