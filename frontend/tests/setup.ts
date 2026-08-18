import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom has no ResizeObserver, but Recharts' ResponsiveContainer needs one
// to learn its size. Report a fixed, non-zero size immediately so charts
// actually render their children in tests.
class MockResizeObserver {
  private callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    this.callback(
      [
        {
          target,
          contentRect: { width: 600, height: 360 } as DOMRectReadOnly,
        } as ResizeObserverEntry,
      ],
      this as unknown as ResizeObserver,
    );
  }

  unobserve() {}
  disconnect() {}
}

vi.stubGlobal("ResizeObserver", MockResizeObserver);
