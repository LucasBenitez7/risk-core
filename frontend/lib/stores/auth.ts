"use client";

/**
 * Auth store — username only.
 *
 * The JWT itself lives in httpOnly cookies set by /api/auth/login and is
 * never accessible from JS. This store only mirrors the public part
 * (username) so the UI can display it without a network round-trip.
 *
 * Hydrated on mount by reading the non-httpOnly `username` cookie.
 */
import { create } from "zustand";

interface AuthState {
  username: string | null;
  setUsername: (username: string | null) => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  username: null,
  setUsername: (username) => set({ username }),
}));
