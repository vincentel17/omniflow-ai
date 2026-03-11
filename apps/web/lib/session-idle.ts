"use client";

const IDLE_LIMIT_MS = 30 * 60 * 1000;
const WARNING_MS = 60 * 1000;

export type SessionIdleOptions = {
  onWarn: () => void;
  onLogout: () => void;
  onResume?: () => void;
};

function nowMs(): number {
  return Date.now();
}

export function createSessionIdleController(options: SessionIdleOptions): () => void {
  let disposed = false;
  let warningTimer: number | null = null;
  let logoutTimer: number | null = null;
  let warned = false;
  let lastActivityAt = nowMs();

  function clearTimers() {
    if (warningTimer !== null) {
      window.clearTimeout(warningTimer);
      warningTimer = null;
    }
    if (logoutTimer !== null) {
      window.clearTimeout(logoutTimer);
      logoutTimer = null;
    }
  }

  function schedule() {
    clearTimers();
    warningTimer = window.setTimeout(() => {
      if (disposed) {
        return;
      }
      warned = true;
      options.onWarn();
      logoutTimer = window.setTimeout(() => {
        if (!disposed) {
          options.onLogout();
        }
      }, WARNING_MS);
    }, IDLE_LIMIT_MS);
  }

  function markActivity() {
    if (disposed) {
      return;
    }
    const timestamp = nowMs();
    if (timestamp <= lastActivityAt) {
      return;
    }
    lastActivityAt = timestamp;
    if (warned) {
      warned = false;
      options.onResume?.();
    }
    schedule();
  }

  function handleVisibilityChange() {
    if (document.visibilityState === "visible") {
      markActivity();
    }
  }

  window.addEventListener("mousemove", markActivity, { passive: true });
  window.addEventListener("keydown", markActivity);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  schedule();

  return () => {
    disposed = true;
    clearTimers();
    window.removeEventListener("mousemove", markActivity);
    window.removeEventListener("keydown", markActivity);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}

