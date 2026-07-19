import { API_BASE_URL } from "$lib/config/env";

export async function saveSessionConfig(sessionId, config) {
  const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });

  if (!res.ok) {
    throw new Error("설정 저장 실패");
  }

  return await res.json();
}

export async function getSessionResult(sessionId) {
  const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/result`);

  if (!res.ok) {
    throw new Error("결과 불러오기 실패");
  }

  return await res.json();
}