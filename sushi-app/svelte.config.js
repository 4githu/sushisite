import { mdsvex } from 'mdsvex';
import adapter from '@sveltejs/adapter-vercel';
import nodeAdapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// The app is hosted at the domain root. Absolute asset paths keep deep
		// routes and query-driven board navigation from requesting /personal-project/_app.
		paths: { relative: false },
		adapter: process.env.BUILD_TARGET === 'node' ? nodeAdapter({ out: process.env.BUILD_OUT || 'build-node', envPrefix: 'SUSHI_' }) : adapter(),
		typescript: {
			config: (config) => ({
				...config,
				include: [...config.include, '../drizzle.config.ts']
			})
		}
	},
	preprocess: [mdsvex({ extensions: ['.svx', '.md'] })],
	extensions: ['.svelte', '.svx', '.md']
};

export default config;
