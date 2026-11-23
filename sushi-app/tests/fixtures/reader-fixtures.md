# Reader browser-test PDFs

These research papers are fetched from arXiv, not checked into this repository:

- Vaswani et al., _Attention Is All You Need_, arXiv:1706.03762v7 — https://arxiv.org/abs/1706.03762v7
- Devlin et al., _BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding_, arXiv:1810.04805v2 — https://arxiv.org/abs/1810.04805v2

From `sushi-app`, before running `reader-real-pdf.svelte.spec.ts` in a clean checkout:

```sh
sh scripts/prepare-reader-fixtures.sh
npx vitest run src/routes/personal-project/reader/reader-real-pdf.svelte.spec.ts src/routes/personal-project/reader/reader-page.svelte.spec.ts
```

The script requires network access, `curl` and `shasum`; it checks pinned SHA-256 digests before installing each PDF. The files are ignored by Git. arXiv availability is an external dependency.
