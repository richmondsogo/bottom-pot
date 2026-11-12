interface ViewTransitionResult {
  ready?: Promise<unknown>;
  finished?: Promise<unknown>;
  updateCallbackDone?: Promise<unknown>;
}

interface DocumentWithViewTransition {
  startViewTransition?: (callback: () => void) => ViewTransitionResult | undefined;
}

function isAbortError(err: unknown): boolean {
  return (
    typeof err === 'object' &&
    err !== null &&
    'name' in err &&
    (err as { name: unknown }).name === 'AbortError'
  );
}

function ignoreAbortError(err: unknown): Promise<never> | void {
  if (!isAbortError(err)) {
    return Promise.reject(err);
  }
}

/**
 * Wrap a DOM/state transition in the native View Transitions API when supported
 * and reduced-motion is inactive, catching expected AbortError rejections when
 * a rapid subsequent transition supersedes an in-flight transition.
 */
export function runViewTransition(update: () => void): void {
  if (
    typeof document !== 'undefined' &&
    typeof window !== 'undefined' &&
    'startViewTransition' in document &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    const doc = document as unknown as DocumentWithViewTransition;
    if (typeof doc.startViewTransition === 'function') {
      const transition = doc.startViewTransition(update);
      transition?.ready?.catch(ignoreAbortError);
      transition?.finished?.catch(ignoreAbortError);
      transition?.updateCallbackDone?.catch(ignoreAbortError);
      return;
    }
  }
  update();
}
