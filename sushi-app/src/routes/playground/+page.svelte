<script lang="ts">
  let count = $state(0);
  let keyword = $state('');
  let words = $state([
    { id: 1, english: 'apple', korean: '사과' },
    { id: 2, english: 'book', korean: '책' }
  ]);

  function increase() {
    count = Number(count) + 1;
  }

  function decrease() {
    count = Number(count) - 1;
  }

  let filteredWords = $derived(
    words.filter((word) =>
    word.english.includes(keyword) || word.korean.includes(keyword)
  )
  );

  import AppButton from '$lib/components/playground/AppButton.svelte';

</script>

<AppButton label="저장" />
<AppButton label="삭제" />


<br><br><br><br>
<h1> Svelte의 기본적인 문법들을 알아봅시다. </h1>
<div>
  <button onclick={decrease}>감소</button>

  <span>{count}</span>
  <button onclick={increase}>증가</button>
  <br>
  <p> bind 사용시 인풋, 입력값 묶임</p>
  <input type="number" bind:value={count} placeholder="검색어를 입력하세요" />
  <br>
  <p>{'조건문 예시 {#if}를 이용해 묶을 수 있고 끝을 {/if}로 마무리합니다. elif같은거 쓰면 {:else if}'}</p>
  {#if count === 1}
    <p>조건이 1입니다.</p>
  {:else if count === 2}
    <p>조건이 2입니다.</p>
  {:else}
    <p>조건이 1도 2도 아닙니다.</p>
  {/if}
  <br>

  <p> {'반복문 예시 {#each}를 이용해 묶을 수 있고 끝을 {/each}로 마무리합니다. key값을 지정할 수도 있습니다.'}</p>
  {#each words as word (word.id)}
    <article>
      <h2>{word.english}</h2>
      <p>{word.korean}</p>
    </article>
  {/each}


  <br>
  <input bind:value={keyword} placeholder="검색"/>
  {#each filteredWords as word (word.id)}
    <p>{word.english} - {word.korean}</p>
  {/each}
</div>
<br>



