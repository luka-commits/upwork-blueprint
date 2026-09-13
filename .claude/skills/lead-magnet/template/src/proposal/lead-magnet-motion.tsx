"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

const Seen = createContext<Set<string> | null>(null);

/** One registry per report, including panels that unmount between visits. */
export function ReportMotion({ children }: { children: ReactNode }) {
  const [seen] = useState(() => new Set<string>());
  useEffect(() => {
    const root = document.querySelector(".lm-report");
    if (!root || typeof IntersectionObserver === "undefined") return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const running = new Set<Animation>();
    const play = (element: Element, frames: Keyframe[], duration: number) => {
      if (preference.matches) return;
      const animation = element.animate(frames, { duration, easing: "cubic-bezier(.22,1,.36,1)" });
      running.add(animation);
      animation.onfinish = () => running.delete(animation);
    };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (!isIntersecting) return;
        const id = target.getAttribute("data-lm-motion")!;
        observer.unobserve(target);
        if (!id || seen.has(id)) return;
        seen.add(id);
        if (target.hasAttribute("data-grow")) {
          play(target, [{ transform: "scaleX(0)", transformOrigin: "left" }, { transform: "scaleX(1)", transformOrigin: "left" }], 320);
        } else {
          const height = target.getBoundingClientRect().height;
          play(target, [{ height: "0px", opacity: .6, overflow: "clip" }, { height: `${height}px`, opacity: 1, overflow: "clip" }], 280);
        }
      });
    }, { threshold: 0 });
    const scan = () => root.querySelectorAll("[data-lm-motion]").forEach((element) => {
      if (!seen.has(element.getAttribute("data-lm-motion")!)) observer.observe(element);
    });
    scan();
    const changes = new MutationObserver(scan);
    changes.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-lm-motion"] });
    const onToggle = (event: Event) => {
      const element = event.target;
      if (!(element instanceof HTMLDetailsElement) || !element.open) return;
      const id = `details-${element.closest("[id]")?.id ?? "actions"}-${element.querySelector("summary")?.textContent}-${Array.from(root.querySelectorAll("details")).indexOf(element)}`;
      if (seen.has(id)) return;
      seen.add(id);
      // Keep the summary still: only the newly revealed evidence moves.
      Array.from(element.children).filter((child) => child.tagName !== "SUMMARY").forEach((child) => {
        play(child, [{ opacity: .4, transform: "translateY(-4px)" }, { opacity: 1, transform: "translateY(0)" }], 220);
      });
    };
    root.addEventListener("toggle", onToggle, true);
    const stop = () => { if (preference.matches) { running.forEach((animation) => animation.cancel()); running.clear(); } };
    preference.addEventListener("change", stop);
    return () => {
      observer.disconnect(); changes.disconnect();
      root.removeEventListener("toggle", onToggle, true);
      preference.removeEventListener("change", stop);
      running.forEach((animation) => animation.cancel());
    };
  }, [seen]);
  return <Seen.Provider value={seen}>{children}</Seen.Provider>;
}

/** The measured value remains the accessible value throughout the 320 ms reveal. */
export function CountUp({ value, id }: { value: number | null | undefined; id: string }) {
  const seen = useContext(Seen);
  const ref = useRef<HTMLSpanElement>(null);
  const [frameValue, setFrameValue] = useState({ target: value, display: value });
  // A refreshed report always shows its current measurement, even after the entrance ran.
  const display = frameValue.target === value ? frameValue.display : value;
  useEffect(() => {
    const element = ref.current;
    if (!element || value == null || !seen || seen.has(id) || typeof IntersectionObserver === "undefined") return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect(); seen.add(id);
      if (preference.matches) return;
      const start = performance.now();
      const tick = (now: number) => {
        const progress = Math.max(0, Math.min((now - start) / 320, 1));
        setFrameValue({ target: value, display: Math.round(value * (1 - (1 - progress) ** 3)) });
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    observer.observe(element);
    const stop = () => { if (preference.matches) { cancelAnimationFrame(frame); setFrameValue({ target: value, display: value }); } };
    preference.addEventListener("change", stop);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); preference.removeEventListener("change", stop); };
  }, [value, id, seen]);
  return <span ref={ref} role="img" aria-label={String(value ?? "—")}><span aria-hidden>{display ?? "—"}</span></span>;
}
