import React, { useEffect, useRef, useState } from 'react';
import { FlickeringGrid } from './ui/flickering-grid';

function resolveInkColor(): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return '#181816';
  }
  const computed = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim();
  if (computed) return computed;
  return document.documentElement.classList.contains('dark') ? '#EDEDEA' : '#181816';
}

function parseColorPrefix(color: string): string {
  if (typeof document === 'undefined') return 'rgba(24, 24, 22,';
  const canvas = document.createElement('canvas');
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext('2d');
  if (!ctx) return 'rgba(24, 24, 22,';
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = Array.from(ctx.getImageData(0, 0, 1, 1).data);
  return `rgba(${r}, ${g}, ${b},`;
}

interface CappedCanvasProps {
  color: string;
  reducedMotion: boolean;
  squareSize: number;
  gridGap: number;
  flickerChance: number;
  maxOpacity: number;
}

const CappedFlickeringCanvas: React.FC<CappedCanvasProps> = ({
  color,
  reducedMotion,
  squareSize,
  gridGap,
  flickerChance,
  maxOpacity,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d') ?? null;
    if (!container || !canvas || !ctx) return;

    const colorPrefix = parseColorPrefix(color);
    let isInView = false;
    let rafId: number | null = null;
    let lastTime = 0;

    let cols = 0;
    let rows = 0;
    let dpr = 1;
    let squares = new Float32Array(0);

    const setup = () => {
      const isMobile = window.innerWidth < 768;
      const maxW = isMobile ? 640 : 1600;
      const maxH = isMobile ? 420 : 480;
      const w = Math.min(container.clientWidth || 0, maxW);
      const h = Math.min(container.clientHeight || 0, maxH);
      dpr = Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2);

      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      cols = Math.ceil(w / (squareSize + gridGap));
      rows = Math.ceil(h / (squareSize + gridGap));
      squares = new Float32Array(cols * rows);
      for (let i = 0; i < squares.length; i++) {
        // Deterministic seed pattern for calm static reduced-motion frame
        const seed = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
        const frac = reducedMotion ? seed - Math.floor(seed) : Math.random();
        squares[i] = frac * maxOpacity;
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const opacity = squares[i * rows + j];
          ctx.fillStyle = `${colorPrefix}${opacity})`;
          ctx.fillRect(
            i * (squareSize + gridGap) * dpr,
            j * (squareSize + gridGap) * dpr,
            squareSize * dpr,
            squareSize * dpr
          );
        }
      }
    };

    const step = (time: number) => {
      if (reducedMotion || !isInView) {
        rafId = null;
        return;
      }
      const deltaTime = lastTime ? Math.min((time - lastTime) / 1000, 0.1) : 0.016;
      lastTime = time;
      for (let i = 0; i < squares.length; i++) {
        if (Math.random() < flickerChance * deltaTime) {
          squares[i] = Math.random() * maxOpacity;
        }
      }
      draw();
      rafId = requestAnimationFrame(step);
    };

    setup();
    draw();

    const resizeObserver = new ResizeObserver(() => {
      setup();
      draw();
    });
    resizeObserver.observe(container);

    let intersectionObserver: IntersectionObserver | null = null;
    if (!reducedMotion && typeof IntersectionObserver !== 'undefined') {
      intersectionObserver = new IntersectionObserver(
        ([entry]) => {
          isInView = Boolean(entry?.isIntersecting);
          if (isInView && rafId === null) {
            lastTime = 0;
            rafId = requestAnimationFrame(step);
          } else if (!isInView && rafId !== null) {
            cancelAnimationFrame(rafId);
            rafId = null;
          }
        },
        { threshold: 0 }
      );
      intersectionObserver.observe(canvas);
    }

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      intersectionObserver?.disconnect();
    };
  }, [color, reducedMotion, squareSize, gridGap, flickerChance, maxOpacity]);

  return (
    <div ref={containerRef} className="h-full w-full">
      <canvas ref={canvasRef} className="pointer-events-none block" />
    </div>
  );
};

export const FooterFlickeringGrid: React.FC = () => {
  const [inkColor, setInkColor] = useState<string>(() => resolveInkColor());
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  const [useCappedCanvas, setUseCappedCanvas] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 768 && (window.devicePixelRatio || 1) > 2;
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setInkColor(resolveInkColor());
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-easter-theme'],
    });

    const mql = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const handleMotionChange = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };
    mql?.addEventListener?.('change', handleMotionChange);

    const handleResize = () => {
      setUseCappedCanvas(window.innerWidth < 768 && (window.devicePixelRatio || 1) > 2);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      observer.disconnect();
      mql?.removeEventListener?.('change', handleMotionChange);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const maskStyle: React.CSSProperties = {
    maskImage:
      'radial-gradient(ellipse 74% 78% at 50% 44%, transparent 32%, rgba(0, 0, 0, 0.45) 72%, rgba(0, 0, 0, 0.95) 100%)',
    WebkitMaskImage:
      'radial-gradient(ellipse 74% 78% at 50% 44%, transparent 32%, rgba(0, 0, 0, 0.45) 72%, rgba(0, 0, 0, 0.95) 100%)',
  };

  return (
    <div
      aria-hidden="true"
      data-testid="footer-flickering-grid"
      className="pointer-events-none select-none absolute inset-0 overflow-hidden z-0 opacity-[0.37]"
      style={maskStyle}
    >
      {prefersReducedMotion || useCappedCanvas ? (
        <CappedFlickeringCanvas
          color={inkColor}
          reducedMotion={prefersReducedMotion}
          squareSize={2}
          gridGap={7}
          flickerChance={0.14}
          maxOpacity={0.22}
        />
      ) : (
        <FlickeringGrid
          className="h-full w-full"
          squareSize={2}
          gridGap={7}
          flickerChance={0.14}
          color={inkColor}
          maxOpacity={0.22}
        />
      )}
    </div>
  );
};
