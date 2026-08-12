// src/lib/stores/mainauth.ts

const API = import.meta.env.VITE_SUSHIFASTURL || '';

import { goto } from "$app/navigation";
import { writable, get } from "svelte/store";

type AuthPayload = {
  sub: string;
  data: {
    id: string;
    name?: string;
    email?: string;
  };
  exp: number;
};

const store = writable<AuthPayload | null>(null);

export const auth = {
  subscribe: store.subscribe,

  get() {
    return get(store);
  },

  logout() {
    store.set(null);
  },

  async check() {
    const res = await fetch(`${API}/auth/isjwt?key=mainauth`, {
      credentials: "include"
    });

    if (res.ok) {
      const payload = await res.json();
      store.set(payload);
      return payload as AuthPayload;
    }

    store.set(null);
    return null;
  },

  async refresh(pathname: string) {
    const res = await fetch(`${API}/auth/isjwt?key=mainauth`, {
      credentials: "include"
    });

    if (res.ok) {
      const payload = await res.json();
      store.set(payload);
      return true;
    }

    store.set(null);

    if (pathname !== "/login") {
      goto("/login");
    }

    return false;
  }
};
