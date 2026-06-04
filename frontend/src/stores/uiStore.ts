"use client";
import { useEffect, useSyncExternalStore } from "react";

/**
 * UI 全局开关。
 * - debugMode = true:sidebar 显示所有 tab(无权置灰,hover 提示缺什么权限点)
 * - debugMode = false:sidebar 只显示当前用户有权的 tab
 *
 * 持久化到 localStorage,跨刷新保留。本轮 RBAC 可视化测试场景默认 true。
 */

const STORAGE_KEY = "ovx_debug_mode";
const DEFAULT_DEBUG_MODE = false;

type Listener = () => void;
const listeners = new Set<Listener>();
let cachedValue: boolean | null = null;

function readFromStorage(): boolean {
  if (typeof window === "undefined") return DEFAULT_DEBUG_MODE;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === "true") return true;
  if (raw === "false") return false;
  return DEFAULT_DEBUG_MODE;
}

function getSnapshot(): boolean {
  if (cachedValue === null) cachedValue = readFromStorage();
  return cachedValue;
}

function getServerSnapshot(): boolean {
  return DEFAULT_DEBUG_MODE;
}

function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useDebugMode(): [boolean, (v: boolean) => void] {
  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // 跨 tab 同步
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        cachedValue = readFromStorage();
        listeners.forEach((l) => l());
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  const setValue = (v: boolean) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, String(v));
    }
    cachedValue = v;
    listeners.forEach((l) => l());
  };

  return [value, setValue];
}
