import type { PlayerCollection, PlayerTrack } from './api';

export class PlayQueue {
	private remaining = 0;
	private lastId: number | null = null;
	private started = false;

	constructor(private collection: PlayerCollection) {}

	reset(collection: PlayerCollection) {
		this.collection = collection;
		this.remaining = 0;
		this.lastId = null;
		this.started = false;
	}

	private enabled() {
		return this.collection.tracks.filter((track) => track.enabled);
	}

	private refill(tracks: PlayerTrack[]) {
		this.remaining = Math.max(tracks.length, Math.round(tracks.reduce((sum, track) => sum + track.weight, 0)));
		this.started = true;
	}

	next(current: PlayerTrack | null): PlayerTrack | null {
		const tracks = this.enabled();
		if (!tracks.length) return null;
		if (current && this.collection.repeat_mode === 'one') return current;
		if (this.collection.mode === 'ordered') {
			if (!current) return tracks[0];
			const index = tracks.findIndex((track) => track.id === current.id);
			if (index < 0) return tracks[0];
			if (index + 1 >= tracks.length) return this.collection.repeat_mode === 'all' ? tracks[0] : null;
			return tracks[index + 1];
		}
		if (!this.remaining) {
			if (this.started && this.collection.repeat_mode === 'off') return null;
			this.refill(tracks);
		}
		const previous = current?.id ?? this.lastId;
		const choices = this.collection.avoid_repeat && tracks.length > 1
			? tracks.filter((track) => track.id !== previous)
			: tracks;
		const total = choices.reduce((sum, track) => sum + track.weight, 0);
		let pick = Math.random() * total;
		let selected = choices[choices.length - 1];
		for (const track of choices) {
			pick -= track.weight;
			if (pick < 0) { selected = track; break; }
		}
		this.remaining -= 1;
		this.lastId = selected.id;
		return selected;
	}
}
