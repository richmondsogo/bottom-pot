import { describe, it, expect, afterEach } from 'vitest';
import { runViewTransition } from '../viewTransition';

const originalDocument = globalThis.document;
const originalWindow = globalThis.window;

afterEach(() => {
  Object.defineProperty(globalThis, 'document', {
    value: originalDocument,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, 'window', {
    value: originalWindow,
    configurable: true,
    writable: true,
  });
});

function installGlobals({
  prefersReducedMotion = false,
  startViewTransition,
}: {
  prefersReducedMotion?: boolean;
  startViewTransition?: (cb: () => void) => {
    ready?: Promise<void>;
    finished?: Promise<void>;
    updateCallbackDone?: Promise<void>;
  };
}) {
  const doc = startViewTransition ? { startViewTransition } : {};
  Object.defineProperty(globalThis, 'document', {
    value: doc,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, 'window', {
    value: {
      matchMedia: () => ({ matches: prefersReducedMotion }),
    },
    configurable: true,
    writable: true,
  });
}

describe('runViewTransition', () => {
  it('calls update directly when startViewTransition is unsupported or reduced motion is active', () => {
    let calls = 0;
    installGlobals({ prefersReducedMotion: false });
    runViewTransition(() => {
      calls += 1;
    });
    expect(calls).toBe(1);

    let vtCalls = 0;
    installGlobals({
      prefersReducedMotion: true,
      startViewTransition: (cb) => {
        vtCalls += 1;
        cb();
        return {};
      },
    });
    runViewTransition(() => {
      calls += 1;
    });
    expect(calls).toBe(2);
    expect(vtCalls).toBe(0);
  });

  it('catches AbortError rejections when a new ViewTransition supersedes an in-flight one', async () => {
    const abortError = Object.assign(
      new Error('Transition was skipped. New ViewTransition started'),
      { name: 'AbortError' }
    );
    const observedChains: Promise<unknown>[] = [];
    const trackRejected = () => {
      const base = Promise.reject(abortError);
      return {
        catch(onRejected?: (reason: unknown) => unknown) {
          const chained = base.catch(onRejected);
          observedChains.push(chained);
          return chained;
        },
      } as unknown as Promise<void>;
    };

    let updated = false;
    installGlobals({
      startViewTransition: function (this: unknown, cb: () => void) {
        expect(this).toBe(globalThis.document);
        cb();
        return {
          ready: trackRejected(),
          finished: trackRejected(),
          updateCallbackDone: trackRejected(),
        };
      },
    });

    runViewTransition(() => {
      updated = true;
    });
    expect(updated).toBe(true);
    expect(observedChains).toHaveLength(3);
    await expect(Promise.all(observedChains)).resolves.toEqual([undefined, undefined, undefined]);
  });

  it('does not swallow non-AbortError rejections from transition lifecycle promises', async () => {
    const fatalError = new TypeError('Unexpected DOM failure');
    const observedChains: Promise<unknown>[] = [];
    const base = Promise.reject(fatalError);
    const trackedReady = {
      catch(onRejected?: (reason: unknown) => unknown) {
        const chained = base.catch(onRejected);
        observedChains.push(chained);
        return chained;
      },
    } as unknown as Promise<void>;

    installGlobals({
      startViewTransition: (cb) => {
        cb();
        return { ready: trackedReady };
      },
    });

    runViewTransition(() => {});
    expect(observedChains).toHaveLength(1);
    await expect(observedChains[0]).rejects.toThrow('Unexpected DOM failure');
  });
});
