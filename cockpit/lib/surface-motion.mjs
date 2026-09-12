// Motion follows deliberate navigation, never polling or typing.
const running = new WeakMap();

export function allowsSurfaceMotion(input, reducedMotion) {
  return input === 'pointer' && !reducedMotion;
}

export function sectionIndex(pathname) {
  return ({ '/follow-ups': 1, '/analytics': 2, '/commands': 3 })[pathname] || 0;
}

export function revealContent(element, options) {
  if (!element) return;
  running.get(element)?.cancel();
  running.delete(element);
  const input = options?.input ?? document.documentElement.dataset.input;
  const reducedMotion = options?.reducedMotion ?? window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!allowsSurfaceMotion(input, reducedMotion) || typeof element.animate !== 'function') return;
  const animation = element.animate([
    { opacity: .45, transform: 'translateY(6px)' },
    { opacity: 1, transform: 'translateY(0)' },
  ], { duration: 180, easing: 'cubic-bezier(.23, 1, .32, 1)' });
  running.set(element, animation);
  animation.onfinish = () => { if (running.get(element) === animation) running.delete(element); };
  return animation;
}
