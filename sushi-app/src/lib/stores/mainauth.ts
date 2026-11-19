// src/lib/stores/mainauth.ts

import { checkPersonalAuth, invalidatePersonalAuth } from '$lib/personal-project/shared/auth';

import { goto } from "$app/navigation";
import { writable, get } from "svelte/store";

type AuthPayload = {
  sub: string;
  data: {
    id: string;
    name?: string;
    email?: string;
    email_verified?: boolean;
  };
  exp: number;
};

const store = writable<AuthPayload | null>(null);
let checkVersion = 0;

export const auth = {
  subscribe: store.subscribe,

  get() {
    return get(store);
  },

  logout() {
    checkVersion++;
    invalidatePersonalAuth();
    store.set(null);
  },

  async check(force = false) {
    const version = ++checkVersion;
    const payload = await checkPersonalAuth(force);
    if (version === checkVersion) store.set(payload);
    return payload;
  },

  async refresh(pathname: string) {
    if (await this.check(true)) return true;

    if (pathname !== "/login") {
      goto("/login");
    }

    return false;
  }
};
