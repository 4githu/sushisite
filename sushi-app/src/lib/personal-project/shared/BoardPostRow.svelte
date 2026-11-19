<script lang="ts">
	let {
		post,
		href
	}: {
		post: {
			title: string;
			excerpt?: string;
			author_name: string;
			created_at: string;
			comments: number;
			pinned: number;
			thumbnail?: string;
		};
		href: string;
	} = $props();
</script>

<a {href} class="board-post-row">
	<div class="post-copy">
		<div class="post-title">
			{#if post.pinned}<span class="pin">공지</span>{/if}<strong>{post.title}</strong><span
				class="comments"
				aria-label={`댓글 ${post.comments}개`}
				><img src="/netaq-design/de317.svg" alt="" />{post.comments}</span
			>
		</div>
		{#if post.excerpt}<p>{post.excerpt}</p>{/if}
		<small>{post.author_name} · {post.created_at.slice(0, 10)}</small>
	</div>
	{#if post.thumbnail}<img
			class="thumbnail"
			src={post.thumbnail}
			alt="첨부 이미지"
			loading="lazy"
		/>{/if}
</a>

<style>
	.board-post-row {
		display: flex;
		width: 100%;
		align-items: center;
		gap: 20px;
		padding: 20px 12px;
		min-height: 100px;
		box-sizing: border-box;
		color: var(--ondo-ink);
		text-decoration: none;
		border-bottom: 1px solid var(--ondo-line);
		background: white;
	}
	.board-post-row:hover {
		background: #f8f9fa;
	}
	.post-copy {
		flex: 1;
		min-width: 0;
	}
	.post-title {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.post-title strong {
		font-size: 17px;
		line-height: 1.5;
		overflow-wrap: anywhere;
	}
	.comments {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 6px;
		white-space: nowrap;
		color: var(--ondo-muted);
		font-size: 13px;
	}
	.comments img {
		flex: none;
	}
	.post-copy p {
		font-size: 14px;
		line-height: 1.6;
		color: var(--ondo-muted);
		margin: 6px 0;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
	}
	.post-copy small {
		display: block;
		margin-top: 6px;
		font-size: 12px;
		color: var(--ondo-muted);
	}
	.thumbnail {
		width: 72px;
		height: 72px;
		object-fit: cover;
		border-radius: 8px;
	}
	.pin {
		font-size: 12px;
		font-weight: 600;
		color: var(--ondo-accent);
		flex: none;
	}
	@media (max-width: 760px) {
		.board-post-row {
			padding: 16px 0;
			gap: 12px;
		}
		.post-title strong {
			font-size: 16px;
		}
		.thumbnail {
			width: 56px;
			height: 56px;
		}
	}
</style>
