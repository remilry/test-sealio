import { useEffect, useEffectEvent } from "react";

export type KeyHandler = (event: KeyboardEvent) => void;

/**
 * Keys are `KeyboardEvent.key` values ("ArrowDown", "Enter", "Escape", "j"…), optionally prefixed
 * by modifiers: "Mod+Enter", "Shift+Tab", "Alt+ArrowUp". `Mod` is ⌘ on Apple devices, Ctrl elsewhere.
 * Letters match whatever their case (Shift is ignored for them unless the combo says "Shift+").
 */
export type KeyMap = Partial<Record<string, KeyHandler>>;

export type UseHandleKeyDownOptions = {
  /** Listen only while true (e.g. while a screen is interactive). Default: true. */
  enabled?: boolean;
  /**
   * Ignore shortcuts without Ctrl/⌘/Alt while the user types in an input, textarea, select or
   * editable element, so "j" or "↓" don't hijack typing. Default: true.
   */
  ignoreWhenTyping?: boolean;
};

type Combo = { key: string; ctrl: boolean; meta: boolean; alt: boolean; shift: boolean | null };

const isApple = () =>
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);

function normalizeKey(key: string): string {
  return key.length === 1 ? key.toLowerCase() : key;
}

function parseCombo(combo: string): Combo {
  const parts = combo.split("+");
  // "Mod++" or "+" means the plus key itself.
  const key = combo.endsWith("++") || combo === "+" ? "+" : parts[parts.length - 1];
  const modifiers = new Set(parts.slice(0, combo.endsWith("++") ? -2 : -1));
  const mod = modifiers.has("Mod");
  const apple = isApple();
  return {
    key: normalizeKey(key),
    ctrl: modifiers.has("Ctrl") || (mod && !apple),
    meta: modifiers.has("Meta") || (mod && apple),
    alt: modifiers.has("Alt"),
    shift: shiftRequirement(modifiers, key),
  };
}

/** Shift is significant for named keys ("Shift+Tab"), ignored for letters unless explicit (null). */
function shiftRequirement(modifiers: Set<string>, key: string): boolean | null {
  if (modifiers.has("Shift")) return true;
  if (key.length === 1) return null;
  return false;
}

function matches(combo: Combo, event: KeyboardEvent): boolean {
  return (
    combo.key === normalizeKey(event.key) &&
    combo.ctrl === event.ctrlKey &&
    combo.meta === event.metaKey &&
    combo.alt === event.altKey &&
    (combo.shift === null || combo.shift === event.shiftKey)
  );
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.closest("[contenteditable]:not([contenteditable='false'])") !== null ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
}

/**
 * Keyboard shortcuts for a screen: one `keydown` listener on window while enabled; the matching
 * handler runs and the browser default is prevented. Handlers always see the latest props/state.
 *
 * @example
 * useHandleKeyDown({ ArrowDown: selectNext, j: selectNext, ArrowUp: selectPrevious, Enter: confirm });
 */
export function useHandleKeyDown(
  keyMap: KeyMap,
  { enabled = true, ignoreWhenTyping = true }: UseHandleKeyDownOptions = {},
) {
  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.defaultPrevented || event.isComposing) return;
    for (const [combo, handler] of Object.entries(keyMap)) {
      if (!handler) continue;
      const parsed = parseCombo(combo);
      if (!matches(parsed, event)) continue;
      const hasModifier = parsed.ctrl || parsed.meta || parsed.alt;
      if (ignoreWhenTyping && !hasModifier && isTyping(event.target)) return;
      event.preventDefault();
      handler(event);
      return;
    }
  });

  useEffect(() => {
    if (!enabled) return;
    const listener = (event: KeyboardEvent) => onKeyDown(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [enabled]);
}
