"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth";
import { login as apiLogin, logout as apiLogout } from "@/lib/api/auth";

function readUsernameCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)username=([^;]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

export function useAuth() {
  const username = useAuthStore((s) => s.username);
  const setUsername = useAuthStore((s) => s.setUsername);
  const router = useRouter();

  useEffect(() => {
    if (username === null) {
      const fromCookie = readUsernameCookie();
      if (fromCookie) setUsername(fromCookie);
    }
  }, [username, setUsername]);

  async function login(usernameInput: string, password: string) {
    const data = await apiLogin(usernameInput, password);
    setUsername(data.username);
  }

  async function logout() {
    await apiLogout();
    setUsername(null);
    router.push("/login");
  }

  return {
    isAuthenticated: username !== null,
    username,
    login,
    logout,
  };
}
