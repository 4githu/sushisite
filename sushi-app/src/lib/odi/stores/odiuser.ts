// src/lib/odi/stores/odiuser.ts

import { API_BASE as API } from '$lib/config/api';

import { goto } from "$app/navigation";
import { writable, get } from "svelte/store";
import { auth } from "$lib/stores/mainauth";

export type JsonObject = Record<string, any>;

export type OdiUser = {
  user_id: string;
  auth_id: string | null;
  recent_template: JsonObject | null;
  config: JsonObject;
  created_at: string;
  updated_at: string;
};

export type OdiAccessStatus =
  | "odi_authenticated"
  | "main_authenticated_needs_odi_join"
  | "guest";

const store = writable<OdiUser | null>(null);

async function fetchJson(res: Response) {
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message = data?.detail ?? data?.message ?? "요청 실패";
    throw new Error(message);
  }

  return data;
}

export const odiuser = {
  subscribe: store.subscribe,

  get() {
    return get(store);
  },

  set(user: OdiUser | null) {
    store.set(user);
  },

  clear() {
    store.set(null);
  },

  async checkAccess() {
    // mainauth를 먼저 확인하고 auth_id로 ODI 토큰을 갱신합니다.
    // ODI 쿠키가 아직 없을 때 /me 404를 먼저 발생시키지 않습니다.
    const authPayload = await auth.check();

    if (authPayload === null) {
      store.set(null);

      return {
        status: "guest" as const,
        user: null
      };
    }

    const authId = authPayload.data?.id;

    if (!authId) {
      store.set(null);

      return {
        status: "guest" as const,
        user: null
      };
    }

    const loginRes = await fetch(`${API}/odi/db/login`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        auth_id: authId
      })
    });

    if (loginRes.ok) {
      const data = await loginRes.json();
      store.set(data.user);

      return {
        status: "odi_authenticated" as const,
        user: data.user as OdiUser
      };
    }

    store.set(null);

    return {
      status: "main_authenticated_needs_odi_join" as const,
      user: null
    };
  },

  async refresh(pathname: string = "") {
    const meRes = await fetch(`${API}/odi/db/me`, {
      credentials: "include"
    });

    if (meRes.ok) {
      const data = await meRes.json();
      store.set(data.user);
      return true;
    }

    let authPayload = auth.get();

    if (authPayload === null) {
      const authOk = await auth.refresh(pathname);

      if (!authOk) {
        store.set(null);
        return false;
      }

      authPayload = auth.get();
    }

    const authId = authPayload?.data?.id;

    if (!authId) {
      store.set(null);
      goto("/login");
      return false;
    }

    const loginRes = await fetch(`${API}/odi/db/login`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        auth_id: authId
      })
    });

    if (loginRes.ok) {
      const data = await loginRes.json();
      store.set(data.user);
      return true;
    }

    store.set(null);

    if (pathname !== "/odi/login") {
      goto("/odi/login");
    }

    return false;
  },

  async join(config: JsonObject, recent_template: JsonObject | null = null) {
    const authPayload = auth.get();

    if (authPayload === null) {
      throw new Error("mainauth가 없습니다.");
    }

    const authId = authPayload.data?.id;

    if (!authId) {
      throw new Error("mainauth payload에 id가 없습니다.");
    }

    const res = await fetch(`${API}/odi/db/join`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: authId,
        auth_id: authId,
        config,
        recent_template
      })
    });

    const data = await fetchJson(res);
    store.set(data.user);
    return data.user as OdiUser;
  },

  async updateConfig(config: JsonObject) {
    const user = get(store);

    if (user === null) {
      throw new Error("ODI 유저가 없습니다.");
    }

    const res = await fetch(`${API}/odi/db/users/${user.user_id}/config`, {
      method: "PUT",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        config
      })
    });

    const data = await fetchJson(res);
    store.set(data.user);
    return data.user as OdiUser;
  },

  async updateRecentTemplate(template: JsonObject | null) {
    const user = get(store);

    if (user === null) {
      throw new Error("ODI 유저가 없습니다.");
    }

    const res = await fetch(`${API}/odi/db/users/${user.user_id}/recent-template`, {
      method: "PUT",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        template
      })
    });

    const data = await fetchJson(res);
    store.set(data.user);
    return data.user as OdiUser;
  },

  async logout() {
    await fetch(`${API}/odi/db/logout`, {
      method: "POST",
      credentials: "include"
    }).catch(() => null);

    store.set(null);
  }
};
