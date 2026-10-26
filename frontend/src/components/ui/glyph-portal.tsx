import React, { useId, useRef, useLayoutEffect } from 'react';

export interface GlyphPortalProps {
  word?: string;
  focusChar?: string;
  interactive?: boolean;
  background?: React.ReactNode;
  front?: React.ReactNode;
  children?: React.ReactNode;
  scrollLength?: number;
  fontFamily?: string;
  fontWeight?: number;
  annotations?: boolean;
  enterLabel?: string;
  className?: string;
  style?: React.CSSProperties;
  onProgress?: (progress: number) => void;
}

interface LetterBox {
  index: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface InkInterior {
  index: number;
  x: number;
  y: number;
  radius: number;
}

const clamp = (val: number, min = 0, max = 1): number => Math.min(max, Math.max(min, val));

const smooth = (min: number, max: number, val: number): number => {
  const h = clamp((val - min) / (max - min));
  return h * h * (3 - 2 * h);
};

const DEFAULT_FONT = '"Geist Variable", "Arial", sans-serif';

function findInterior(
  ctx: CanvasRenderingContext2D,
  char: string,
  font: string,
): { x: number; y: number; radius: number } | null {
  const canvas = ctx.canvas;
  ctx.font = font;
  const metrics = ctx.measureText(char);
  const padding = 8;
  const left = Math.ceil(metrics.actualBoundingBoxLeft);
  const ascent = Math.ceil(metrics.actualBoundingBoxAscent);
  canvas.width = Math.max(
    1,
    Math.ceil(metrics.actualBoundingBoxLeft + metrics.actualBoundingBoxRight) + padding * 2,
  );
  canvas.height = Math.max(
    1,
    Math.ceil(metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent) + padding * 2,
  );
  ctx.font = font;
  ctx.fontKerning = 'none';
  ctx.fillText(char, padding + left, padding + ascent);
  const { width, height } = canvas;
  const data = ctx.getImageData(0, 0, width, height).data;
  const table = new Uint16Array(width + 1);
  let maxRadius = 0;
  let bestX = 0;
  let bestY = 0;

  for (let y = 0; y < height; y++) {
    let prev = 0;
    for (let x = 0; x < width; x++) {
      const current = table[x + 1];
      table[x + 1] =
        data[(y * width + x) * 4 + 3] > 245
          ? Math.min(current, table[x], prev) + 1
          : 0;
      prev = current;
      if (table[x + 1] > maxRadius) {
        maxRadius = table[x + 1];
        bestX = x;
        bestY = y;
      }
    }
  }

  if (maxRadius < 3) return null;
  return {
    x: (bestX + 1 - maxRadius / 2 - padding - left) / 3,
    y: (bestY + 1 - maxRadius / 2 - padding - ascent) / 3,
    radius: (maxRadius / 2 - 1) / 3,
  };
}

function getScrollParent(el: HTMLElement | null): HTMLElement | null {
  for (let parent = el?.parentElement; parent; parent = parent.parentElement) {
    if (
      /(auto|scroll|hidden)/.test(getComputedStyle(parent).overflowY) &&
      parent !== document.body &&
      parent !== document.documentElement
    ) {
      return parent;
    }
  }
  return null;
}

export const GlyphPortal: React.FC<GlyphPortalProps> = ({
  word = 'Bottom Pot',
  focusChar,
  interactive = true,
  background,
  front,
  children,
  scrollLength = 1.8,
  fontFamily = DEFAULT_FONT,
  fontWeight = 700,
  annotations = false,
  enterLabel = 'Start searching',
  className,
  style,
  onProgress,
}) => {
  const sectionId = `gp-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const clipId = `${sectionId}-clip`;
  const containerRef = useRef<HTMLElement>(null);
  const onProgressRef = useRef(onProgress);

  useLayoutEffect(() => {
    onProgressRef.current = onProgress;
  }, [onProgress]);

  const cleanWord = word.trim().normalize('NFC') || 'Bottom Pot';
  const characterList = (() => {
    let cursor = 0;
    return Array.from(cleanWord).map((char) => {
      const idx = cursor;
      cursor += char.length;
      return { char, index: idx };
    });
  })();

  const clampedScrollLength = Number.isFinite(scrollLength) ? clamp(scrollLength, 1, 8) : 1.8;
  const clampedFontWeight = Number.isFinite(fontWeight) ? clamp(fontWeight, 100, 1000) : 700;
  const hasFrontSlot = front != null;
  const scopeSelector = `:where(#${sectionId})`;

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const pinEl = container.querySelector<HTMLElement>('[data-gp-pin]');
    const fieldEl = container.querySelector<HTMLElement>('[data-gp-field]');
    const artEl = container.querySelector<SVGSVGElement>('[data-gp-art]');
    const clipEl = container.querySelector<SVGClipPathElement>(`#${clipId}`);
    const glyphTextEl = container.querySelector<SVGTextElement>('[data-gp-glyph]');
    const marksGroup = container.querySelector<SVGGElement>('[data-gp-marks]');
    const marksPath = marksGroup?.querySelector<SVGPathElement>('path');
    const choicesEl = container.querySelector<HTMLElement>('[data-gp-choices]');
    const letterButtons = Array.from(choicesEl?.querySelectorAll<HTMLButtonElement>('button') ?? []);
    const selectEl = container.querySelector<HTMLSelectElement>('[data-gp-select]');
    const scrollParent = getScrollParent(container);
    const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    let isDisposed = false;
    let animFrameId = 0;
    let needsMeasure = true;
    let isIntersecting = true;
    let isInkMeasured = false;
    const mountTime = performance.now();
    let hasRenderedFirstFrame = false;
    let fontTimeoutOccurred = false;

    let containerWidth = 1;
    let pinHeight = 1;
    let totalScrollSpan = 1;
    let baseScale = 1;
    let zoomScale = 1;
    let centerPt = { x: 0, y: 0 };
    let currentInk: InkInterior | null = null;
    let lastProgress = -1;
    let inkSpots: InkInterior[] = [];
    let letterBoxes: LetterBox[] = [];
    let isChoosingLetter = false;
    let wordBounds = { x: 0, y: 0, width: 1, height: 1 };
    let shouldReadInk = true;

    if (glyphTextEl) {
      glyphTextEl.style.fontFamily = fontFamily;
      const parsedFamilies = getComputedStyle(glyphTextEl).fontFamily.match(/(?:[^,"']+|"[^"]*"|'[^']*')+/g) ?? [];
      const verifiedFamilies = parsedFamilies.filter((fam) => {
        try {
          return document.fonts.check(`${clampedFontWeight} 100px ${fam.trim()}`, cleanWord);
        } catch {
          return false;
        }
      });
      glyphTextEl.style.fontFamily = [...verifiedFamilies, DEFAULT_FONT].join(',');
      fontTimeoutOccurred = verifiedFamilies.length < parsedFamilies.length;
    }

    const readInk = (): boolean => {
      if (!ctx || !glyphTextEl) return false;
      const computed = getComputedStyle(glyphTextEl);
      const largeFont = `${computed.fontWeight} 300px ${computed.fontFamily}`;
      ctx.font = `${computed.fontWeight} 100px ${computed.fontFamily}`;
      ctx.fontKerning = 'none';

      const fullMetrics = ctx.measureText(cleanWord);
      const offsets = Array.from({ length: cleanWord.length }, (_, i) => ctx.measureText(cleanWord.slice(0, i)).width);

      wordBounds = {
        x: -fullMetrics.actualBoundingBoxLeft,
        y: -fullMetrics.actualBoundingBoxAscent,
        width: fullMetrics.actualBoundingBoxLeft + fullMetrics.actualBoundingBoxRight,
        height: fullMetrics.actualBoundingBoxAscent + fullMetrics.actualBoundingBoxDescent,
      };

      if (!wordBounds.width || !wordBounds.height) return false;

      centerPt = {
        x: wordBounds.x + wordBounds.width / 2,
        y: wordBounds.y + wordBounds.height / 2,
      };

      const requestedCharIndex = focusChar ? cleanWord.indexOf(focusChar.normalize('NFC')) : -1;
      let charIdx = 0;
      inkSpots = [];
      letterBoxes = [];

      for (const char of Array.from(cleanWord)) {
        ctx.font = `${computed.fontWeight} 100px ${computed.fontFamily}`;
        const charMetrics = ctx.measureText(char);
        letterBoxes.push({
          index: charIdx,
          x: offsets[charIdx] - charMetrics.actualBoundingBoxLeft,
          y: -charMetrics.actualBoundingBoxAscent,
          width: charMetrics.actualBoundingBoxLeft + charMetrics.actualBoundingBoxRight,
          height: charMetrics.actualBoundingBoxAscent + charMetrics.actualBoundingBoxDescent,
        });

        const spot = findInterior(ctx, char, largeFont);
        if (spot) {
          inkSpots.push({
            ...spot,
            x: spot.x + offsets[charIdx],
            index: charIdx,
          });
        }
        charIdx += char.length;
      }

      currentInk =
        inkSpots.find((spot) => spot.index === requestedCharIndex) ??
        [...inkSpots].sort((a, b) => b.radius - a.radius || Math.abs(a.x - centerPt.x) - Math.abs(b.x - centerPt.x))[0] ??
        null;

      return true;
    };

    const selectInk = (spot: InkInterior | null) => {
      currentInk = spot;
      zoomScale = currentInk
        ? Math.max(baseScale, Math.hypot(containerWidth, pinHeight) / (currentInk.radius * 1.35))
        : baseScale;

      container.dataset.gpFocus = currentInk ? Array.from(cleanWord.slice(currentInk.index))[0] : '';
      container.dataset.gpFocusIndex = String(currentInk?.index ?? -1);

      for (const btn of letterButtons) {
        const isMatched = Number(btn.dataset.gpLetter) === currentInk?.index;
        btn.disabled = !inkSpots.some((s) => s.index === Number(btn.dataset.gpLetter));
        btn.setAttribute('aria-checked', String(isMatched));
        btn.tabIndex = isMatched ? 0 : -1;
      }

      if (selectEl && selectEl.value !== '') {
        selectEl.value = String(currentInk?.index ?? -1);
      }
      if (selectEl) {
        for (const opt of Array.from(selectEl.options)) {
          opt.disabled = opt.value === '' || !inkSpots.some((s) => s.index === Number(opt.value));
        }
      }

      const invBase = 1 / baseScale;
      const markerY = wordBounds.y + wordBounds.height + 25 * invBase;
      const startX = wordBounds.x;
      const endX = startX + wordBounds.width;
      const crosshair = currentInk
        ? `M${currentInk.x - 9 * invBase} ${currentInk.y}h${18 * invBase}M${currentInk.x} ${currentInk.y - 9 * invBase}v${18 * invBase}`
        : '';

      if (marksPath) {
        marksPath.setAttribute(
          'd',
          `M${startX} ${markerY}H${endX}M${startX} ${markerY - 5 * invBase}v${10 * invBase}M${endX} ${markerY - 5 * invBase}v${10 * invBase}${crosshair}`,
        );
        marksPath.setAttribute('stroke-width', String(invBase));
      }
    };

    const computeScrollProgress = (): number => {
      const parentTop = scrollParent ? scrollParent.getBoundingClientRect().top + scrollParent.clientTop : 0;
      return clamp((parentTop - container.getBoundingClientRect().top) / totalScrollSpan);
    };

    const paint = (progress: number) => {
      const isMotionOff = reducedMotionQuery.matches || !hasRenderedFirstFrame || fontTimeoutOccurred || !currentInk;
      const rawP = isMotionOff ? 0 : progress;
      const normP = clamp(rawP / 0.78);
      const easeP = normP < 0.5 ? 4 * normP ** 3 : 1 - (-2 * normP + 2) ** 3 / 2;

      const scale = Math.exp(Math.log(baseScale) + Math.log(zoomScale / baseScale) * easeP);
      const interpFactor = zoomScale === baseScale ? 0 : (1 / scale - 1 / baseScale) / (1 / zoomScale - 1 / baseScale);

      const targetX = centerPt.x + ((currentInk?.x ?? centerPt.x) - centerPt.x) * interpFactor;
      const targetY = centerPt.y + ((currentInk?.y ?? centerPt.y) - centerPt.y) * interpFactor;
      const rotation = -4 * smooth(0.06, 0.5, normP) * (1 - smooth(0.62, 0.92, normP));

      const transformStr = `translate(${containerWidth / 2} ${pinHeight * 0.46 + pinHeight * 0.04 * easeP}) scale(${scale}) rotate(${rotation}) translate(${-targetX} ${-targetY})`;
      const rad = (rotation * Math.PI) / 180;
      const halfW = containerWidth / 2 / scale;
      const centerH = (pinHeight * 0.46 + pinHeight * 0.04 * easeP) / scale;

      clipEl?.setAttribute('transform', `scale(${scale}) rotate(${rotation})`);
      glyphTextEl?.setAttribute(
        'transform',
        `translate(${Math.cos(rad) * halfW + Math.sin(rad) * centerH - targetX} ${-Math.sin(rad) * halfW + Math.cos(rad) * centerH - targetY})`,
      );

      if (marksGroup) {
        marksGroup.setAttribute('transform', transformStr);
        marksGroup.style.opacity = String(1 - smooth(0.015, 0.17, rawP));
      }

      isChoosingLetter = interactive && !isMotionOff && rawP < 0.04;
      if (choicesEl) {
        choicesEl.inert = !isChoosingLetter;
      }
      container.dataset.gpChoosing = String(isChoosingLetter);

      if (fieldEl) {
        fieldEl.style.clipPath = normP >= 1 ? 'none' : `url(#${clipId})`;
      }

      container.style.setProperty('--gp-caption', String(1 - smooth(0.01, 0.16, rawP)));
      container.style.setProperty('--gp-reveal', String(isMotionOff ? 1 : smooth(0.78, 0.9, rawP)));
      container.style.setProperty('--gp-field-scale', String(1 + 0.16 * smooth(0, 0.82, rawP)));
      container.style.setProperty('--gp-caption-hit', rawP < 0.08 ? 'auto' : 'none');
      container.dataset.gpEntered = String(rawP >= 0.9);
      container.dataset.gpProgress = rawP.toFixed(5);

      if (rawP !== lastProgress) {
        lastProgress = rawP;
        onProgressRef.current?.(rawP);
      }
    };

    const updateLayout = () => {
      if (!container.clientWidth || !pinEl) return;
      containerWidth = pinEl.clientWidth;

      const viewportDiv = container.querySelector<HTMLElement>('[data-gp-viewport]');
      const viewportHeight = viewportDiv?.offsetHeight ?? window.innerHeight;
      const effectiveParentH = Math.max(1, Math.min(scrollParent?.clientHeight ?? viewportHeight, viewportHeight));

      pinHeight = reducedMotionQuery.matches ? Math.min(effectiveParentH * 0.75, 480) : effectiveParentH;
      container.style.setProperty('--gp-height', `${pinHeight}px`);
      totalScrollSpan = pinHeight * clampedScrollLength;

      artEl?.setAttribute('viewBox', `0 0 ${containerWidth} ${pinHeight}`);

      if (shouldReadInk) {
        isInkMeasured = readInk();
        shouldReadInk = false;
      }

      if (!isInkMeasured) return;

      const verticalBudget =
        hasFrontSlot && pinHeight < 480
          ? Math.min(pinHeight * 0.38, Math.max(24, pinHeight - 264))
          : pinHeight * 0.38;

      baseScale = Math.min((containerWidth * 0.84) / wordBounds.width, verticalBudget / wordBounds.height);
      selectInk(currentInk);

      for (const btn of letterButtons) {
        const box = letterBoxes.find((b) => b.index === Number(btn.dataset.gpLetter));
        if (box) {
          Object.assign(btn.style, {
            left: `${containerWidth / 2 + (box.x - centerPt.x) * baseScale}px`,
            top: `${pinHeight * 0.46 + (box.y - centerPt.y) * baseScale - Math.max(0, 44 - box.height * baseScale) / 2}px`,
            width: `${Math.max(1, box.width * baseScale)}px`,
            height: `${Math.max(44, box.height * baseScale)}px`,
          });
        }
      }

      container.style.setProperty('--gp-word-top', `${pinHeight * 0.46 - (wordBounds.height * baseScale) / 2}px`);
      container.style.setProperty('--gp-word-bottom', `${pinHeight * 0.46 + (wordBounds.height * baseScale) / 2}px`);
      container.dataset.gpReady = 'true';
      container.dataset.gpMotion =
        !reducedMotionQuery.matches && hasRenderedFirstFrame && !fontTimeoutOccurred && currentInk ? 'on' : 'off';
    };

    const onFrame = (timestamp?: number) => {
      animFrameId = 0;
      if (isDisposed) return;
      if (timestamp !== undefined && !hasRenderedFirstFrame) {
        hasRenderedFirstFrame = true;
        if (!fontTimeoutOccurred) {
          fontTimeoutOccurred = performance.now() - mountTime > 2500;
        }
        needsMeasure = true;
      }
      if (needsMeasure) {
        needsMeasure = false;
        updateLayout();
      }
      if (isInkMeasured) {
        paint(computeScrollProgress());
      }
    };

    const scheduleFrame = () => {
      if (!animFrameId && isIntersecting) {
        animFrameId = requestAnimationFrame(onFrame);
      }
    };

    const handleResize = () => {
      if (animFrameId) cancelAnimationFrame(animFrameId);
      needsMeasure = true;
      onFrame();
    };

    const handleScroll = () => {
      scheduleFrame();
    };

    const handleLetterInteraction = (e: Event) => {
      if (!isChoosingLetter || computeScrollProgress() >= 0.04) return;
      const targetBtn = (e.target as HTMLElement).closest<HTMLButtonElement>('[data-gp-letter]');
      const spot = inkSpots.find((s) => s.index === Number(targetBtn?.dataset.gpLetter));
      if (!spot || spot === currentInk) return;
      selectInk(spot);
      paint(computeScrollProgress());
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isChoosingLetter || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) {
        return;
      }
      e.preventDefault();
      const currentIdx = currentInk ? inkSpots.indexOf(currentInk) : -1;
      const nextIdx =
        e.key === 'Home'
          ? 0
          : e.key === 'End'
          ? inkSpots.length - 1
          : (currentIdx + (e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1) + inkSpots.length) % inkSpots.length;

      const targetBtn = letterButtons.find((btn) => Number(btn.dataset.gpLetter) === inkSpots[nextIdx]?.index);
      targetBtn?.focus({ preventScroll: true });
    };

    const handleSelectChange = () => {
      if (!isChoosingLetter || !selectEl || computeScrollProgress() >= 0.04) return;
      const spot = inkSpots.find((s) => s.index === Number(selectEl.value));
      if (spot) {
        selectInk(spot);
        paint(computeScrollProgress());
      }
    };

    if (choicesEl) {
      choicesEl.addEventListener('pointerover', handleLetterInteraction);
      choicesEl.addEventListener('click', handleLetterInteraction);
      choicesEl.addEventListener('focusin', handleLetterInteraction);
      choicesEl.addEventListener('keydown', handleKeyDown);
    }
    selectEl?.addEventListener('change', handleSelectChange);

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);
    if (scrollParent) {
      resizeObserver.observe(scrollParent);
    }

    const intersectionObserver = new IntersectionObserver(
      ([entry]) => {
        isIntersecting = entry.isIntersecting;
        if (isIntersecting) {
          needsMeasure = true;
          scheduleFrame();
        } else if (animFrameId) {
          cancelAnimationFrame(animFrameId);
          animFrameId = 0;
        }
      },
      { root: scrollParent, rootMargin: '100% 0px' },
    );
    intersectionObserver.observe(container);

    const scrollTarget = scrollParent ?? window;
    scrollTarget.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize);
    window.visualViewport?.addEventListener('resize', handleResize);
    reducedMotionQuery.addEventListener('change', handleResize);

    onFrame();
    scheduleFrame();

    return () => {
      isDisposed = true;
      if (animFrameId) cancelAnimationFrame(animFrameId);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      scrollTarget.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
      window.visualViewport?.removeEventListener('resize', handleResize);
      reducedMotionQuery.removeEventListener('change', handleResize);

      if (choicesEl) {
        choicesEl.removeEventListener('pointerover', handleLetterInteraction);
        choicesEl.removeEventListener('click', handleLetterInteraction);
        choicesEl.removeEventListener('focusin', handleLetterInteraction);
        choicesEl.removeEventListener('keydown', handleKeyDown);
      }
      selectEl?.removeEventListener('change', handleSelectChange);
    };
  }, [cleanWord, focusChar, interactive, fontFamily, clampedFontWeight, clampedScrollLength, clipId, hasFrontSlot]);

  return (
    <section
      ref={containerRef}
      id={sectionId}
      className={className}
      aria-label={cleanWord}
      style={
        {
          '--gp-length': clampedScrollLength,
          '--gp-characters': Array.from(cleanWord).length,
          ...style,
        } as React.CSSProperties
      }
    >
      <style>{`
        ${scopeSelector}{--gp-paper:var(--bg,#FAF8F5);--gp-ink:var(--ink,#181816);--gp-field:var(--ink,#181816);--gp-foreground:var(--bg,#FAF8F5);position:relative;isolation:isolate;background:var(--gp-paper);color:var(--gp-ink);font-family:var(--font-sans,'Geist Variable',sans-serif);}
        ${scopeSelector}>[data-gp-viewport]{position:absolute;inset:0 auto auto 0;height:100vh;height:100svh;width:0;pointer-events:none;visibility:hidden;}
        ${scopeSelector} [data-gp-pin]{position:relative;height:var(--gp-height,100svh);overflow:clip;isolation:isolate;container-type:size;}
        ${scopeSelector} [data-gp-field]{position:absolute;inset:0;background:var(--gp-field);opacity:0;pointer-events:none;}
        ${scopeSelector}[data-gp-ready] [data-gp-field]{opacity:1;}
        ${scopeSelector} [data-gp-art]{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none;}
        ${scopeSelector} [data-gp-marks]{fill:none;stroke:var(--gp-ink);opacity:.6;}
        ${scopeSelector} [data-gp-choices]{position:absolute;inset:0;visibility:hidden;pointer-events:none;}
        ${scopeSelector}[data-gp-choosing=true] [data-gp-choices]{visibility:visible;}
        ${scopeSelector} [data-gp-letter]{box-sizing:border-box;position:absolute;border:0;padding:0;margin:0;background:transparent;cursor:pointer;pointer-events:auto;touch-action:pan-y;}
        ${scopeSelector} [data-gp-letter]:disabled{pointer-events:none;}
        ${scopeSelector} [data-gp-letter]:focus-visible{outline:2px solid var(--accent,#1A382B);outline-offset:5px;}
        ${scopeSelector} [data-gp-touch-picker]{display:none;position:absolute;top:calc(var(--gp-word-bottom,50%) + 42px);left:50%;transform:translateX(-50%);font:12px/1.4 inherit;align-items:center;gap:12px;visibility:hidden;}
        ${scopeSelector}[data-gp-choosing=true] [data-gp-touch-picker]{visibility:visible;}
        ${scopeSelector} [data-gp-select]{min-height:44px;min-width:90px;border:1px solid var(--border,#DDD7CA);border-radius:0;background:var(--gp-paper);color:var(--gp-ink);padding:0 10px;font:inherit;}
        ${scopeSelector} [data-gp-select]:focus-visible{outline:2px solid var(--accent,#1A382B);outline-offset:4px;}
        @media(any-pointer:coarse){${scopeSelector} [data-gp-touch-picker]{display:flex;}}
        ${scopeSelector} [data-gp-fallback]{position:absolute;inset:0;display:none;place-items:center;font-size:min(calc(100cqw / var(--gp-characters)),38cqh);line-height:1;color:var(--gp-field);}
        ${scopeSelector}[data-gp-ready] [data-gp-fallback]{visibility:hidden;}
        ${scopeSelector} [data-gp-caption]{position:absolute;inset:auto 8% 9%;display:flex;align-items:center;justify-content:space-between;gap:1rem;font:14px/1.4 inherit;opacity:var(--gp-caption,1);pointer-events:var(--gp-caption-hit,auto);}
        ${scopeSelector} [data-gp-caption]{font-family:inherit;}
        ${scopeSelector} [data-gp-front]{position:absolute;inset:0;opacity:var(--gp-caption,1);pointer-events:none;}
        ${scopeSelector} [data-gp-front] a,${scopeSelector} [data-gp-front] button{pointer-events:var(--gp-caption-hit,auto);}
        ${scopeSelector} [data-gp-front]:focus-within{opacity:1;}
        ${scopeSelector} [data-gp-hint]{max-width:30ch;color:var(--gp-ink);font-size:13px;}
        ${scopeSelector} [data-gp-enter]{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:48px;min-height:48px;padding:0 24px;background:var(--accent,#1A382B);color:var(--accent-foreground,#FFFFFF);font-size:15px;font-weight:500;text-decoration:none;border-radius:0;transition:background-color 140ms ease-out;}
        ${scopeSelector} [data-gp-enter]:hover{background:var(--accent-hover,#12281E);}
        ${scopeSelector} [data-gp-enter]:focus-visible{outline:2px solid var(--accent,#1A382B);outline-offset:3px;}
        ${scopeSelector} [data-gp-caption]:focus-within{opacity:1;pointer-events:auto;}
        ${scopeSelector} [data-gp-content]{box-sizing:border-box;position:relative;min-height:var(--gp-height,100svh);padding:clamp(32px,6%,80px) clamp(16px,4%,32px);display:grid;align-content:center;color:var(--gp-foreground);background:var(--gp-field);overflow-wrap:anywhere;}
        ${scopeSelector}[data-gp-motion=on] [data-gp-pin]{position:sticky;top:0;}
        ${scopeSelector}[data-gp-motion=off] [data-gp-hint]{display:none;}
        ${scopeSelector}[data-gp-motion=on] [data-gp-content]{margin-top:calc((var(--gp-length) - 1) * var(--gp-height));background:transparent;opacity:var(--gp-reveal,0);pointer-events:none;}
        ${scopeSelector}[data-gp-motion=on][data-gp-entered=true] [data-gp-content]{pointer-events:auto;}
        ${scopeSelector}[data-gp-motion=on]:has([data-gp-content]:focus-within) [data-gp-field]{clip-path:none!important;}
        ${scopeSelector}[data-gp-motion=on] [data-gp-content]:focus-within{opacity:1;pointer-events:auto;}
        ${scopeSelector}:has([data-gp-content]:focus-within) [data-gp-caption],${scopeSelector}:has([data-gp-content]:focus-within) [data-gp-marks]{opacity:0;}
        @media(prefers-reduced-motion:reduce){${scopeSelector} [data-gp-pin]{position:relative!important;} ${scopeSelector} [data-gp-content]{margin-top:0!important;opacity:1!important;background:var(--gp-field)!important;min-height:0;padding-block:48px;} ${scopeSelector} [data-gp-caption]{opacity:1!important;}}
        @media(prefers-reduced-motion:reduce){${scopeSelector} [data-gp-hint]{display:none;}}
      `}</style>
      <noscript>
        <style>{`${scopeSelector} [data-gp-fallback]{display:grid}${scopeSelector} [data-gp-hint]{display:none}`}</style>
      </noscript>

      <div data-gp-viewport="true" aria-hidden="true" />

      <div data-gp-pin="true">
        <div data-gp-field="true" aria-hidden="true" inert>
          {background ?? (
            <div
              data-gp-default-field="true"
              style={{
                position: 'absolute',
                inset: 0,
                transform: 'scale(var(--gp-field-scale,1))',
                background: 'var(--gp-field)',
              }}
            />
          )}
        </div>

        <svg data-gp-art="true" aria-hidden="true" focusable="false">
          <defs>
            <clipPath id={clipId} clipPathUnits="userSpaceOnUse">
              <text
                data-gp-glyph="true"
                x="0"
                y="0"
                style={{
                  fontFamily,
                  fontWeight: clampedFontWeight,
                  fontSize: 100,
                  fontKerning: 'none',
                  fontVariantLigatures: 'none',
                  letterSpacing: 0,
                }}
              >
                {cleanWord}
              </text>
            </clipPath>
          </defs>
          <g data-gp-marks="true" style={{ visibility: annotations ? 'visible' : 'hidden' }}>
            <path />
          </g>
        </svg>

        <div
          data-gp-choices="true"
          role="radiogroup"
          aria-label="Choose the letter to enter through"
          inert
        >
          {characterList.map(({ char, index }, pos) => (
            <button
              key={index}
              type="button"
              role="radio"
              aria-checked="false"
              tabIndex={-1}
              data-gp-letter={index}
              aria-label={`${char}, letter ${pos + 1} of ${characterList.length}`}
            />
          ))}
        </div>

        <label data-gp-touch-picker="true">
          <span
            style={{
              position: 'absolute',
              width: 1,
              height: 1,
              overflow: 'hidden',
              clipPath: 'inset(50%)',
            }}
          >
            Entry letter
          </span>
          <select data-gp-select="true" defaultValue="">
            <option value="" disabled>
              Choose a letter
            </option>
            {characterList.map(({ char, index }, pos) => (
              <option key={index} value={index}>
                {pos + 1} · {char}
              </option>
            ))}
          </select>
        </label>

        {front && <div data-gp-front="true">{front}</div>}

        <span
          data-gp-fallback="true"
          aria-hidden="true"
          style={{ fontFamily, fontWeight: clampedFontWeight }}
        >
          {cleanWord}
        </span>

        <div data-gp-caption="true">
          <span data-gp-hint="true" aria-hidden="true">
            {interactive ? 'Scroll to look inside' : annotations ? 'A passage through type' : ''}
          </span>
          <a data-gp-enter="true" href={`#${sectionId}-content`}>
            {enterLabel}
            <span aria-hidden="true">↘</span>
          </a>
        </div>
      </div>

      <div data-gp-content="true" id={`${sectionId}-content`} tabIndex={-1}>
        {children ?? (
          <div>
            <h2>What kind of role are you after?</h2>
          </div>
        )}
      </div>
    </section>
  );
};

export default GlyphPortal;
