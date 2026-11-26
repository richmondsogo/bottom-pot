import React, { useEffect, useRef, useState } from 'react';
import { X, Flame } from 'lucide-react';
import { Button } from './ui/button';
import { Pointer } from './ui/pointer';

interface BottomPotEasterEggProps {
  open: boolean;
  onClose: () => void;
  theme: 'light' | 'dark';
}

interface EmberCell {
  x: number;
  y: number;
  vx: number;
  vy: number;
  phase: number;
  speed: number;
  hot: boolean;
}

export const BottomPotEasterEgg: React.FC<BottomPotEasterEggProps> = ({
  open,
  onClose,
  theme,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerRef = useRef<{ x: number; y: number; active: boolean }>({
    x: -999,
    y: -999,
    active: false,
  });
  const themeRef = useRef(theme);
  const [jollofAccent, setJollofAccent] = useState<boolean>(() => {
    if (typeof document !== 'undefined') {
      return document.documentElement.dataset.easterTheme === 'jollof';
    }
    return false;
  });
  const jollofRef = useRef(jollofAccent);

  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);

  useEffect(() => {
    jollofRef.current = jollofAccent;
  }, [jollofAccent]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const toggleJollofAccent = () => {
    setJollofAccent((prev) => {
      const next = !prev;
      if (typeof document !== 'undefined') {
        if (next) {
          document.documentElement.dataset.easterTheme = 'jollof';
        } else {
          delete document.documentElement.dataset.easterTheme;
        }
      }
      return next;
    });
  };

  useEffect(() => {
    if (!open) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = canvas.clientWidth || 360;
    const height = canvas.clientHeight || 132;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const step = 10;
    const cols = Math.floor(width / step);
    const rows = Math.floor(height / step);
    const embers: EmberCell[] = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        // Higher density near the bottom edge of the pot
        const bottomWeight = (r + 1) / Math.max(rows, 1);
        if (Math.random() < 0.22 + bottomWeight * 0.45) {
          embers.push({
            x: c * step + 2,
            y: r * step + 2,
            vx: 0,
            vy: -(0.12 + bottomWeight * 0.28),
            phase: Math.random() * Math.PI * 2,
            speed: 0.02 + Math.random() * 0.035,
            hot: bottomWeight > 0.6 && Math.random() < 0.42,
          });
        }
      }
    }

    const drawFrame = (t: number) => {
      const isDark = themeRef.current === 'dark';
      const isJollof = jollofRef.current;
      ctx.fillStyle = isDark ? '#111211' : '#F4F0E8';
      ctx.fillRect(0, 0, width, height);

      // Subtle architectural grid
      ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(24,24,22,0.05)';
      ctx.lineWidth = 1;
      for (let gx = 0; gx < width; gx += step * 2) {
        ctx.beginPath();
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, height);
        ctx.stroke();
      }

      const ptr = pointerRef.current;

      for (const cell of embers) {
        if (!prefersReduced) {
          cell.phase += cell.speed;
          cell.y += cell.vy * (0.65 + 0.35 * Math.sin(cell.phase));
          if (cell.y < -6) {
            cell.y = height - 6;
          }

          if (ptr.active) {
            const dx = cell.x - ptr.x;
            const dy = cell.y - ptr.y;
            const distSq = dx * dx + dy * dy;
            if (distSq < 2800 && distSq > 1) {
              const push = (1 - distSq / 2800) * 1.4;
              cell.vx += (dx / Math.sqrt(distSq)) * push;
            }
          }
          cell.vx *= 0.9;
          cell.x += cell.vx;
          if (cell.x < 0) cell.x += width;
          if (cell.x > width) cell.x -= width;
        }

        const heat = 0.35 + 0.55 * (0.5 + 0.5 * Math.sin(cell.phase + t * 0.001));
        if (cell.hot) {
          ctx.fillStyle = isJollof
            ? isDark
              ? `rgba(251, 146, 60, ${heat.toFixed(2)})`
              : `rgba(154, 52, 18, ${heat.toFixed(2)})`
            : isDark
              ? `rgba(74, 222, 128, ${(heat * 0.85).toFixed(2)})`
              : `rgba(26, 56, 43, ${heat.toFixed(2)})`;
        } else {
          ctx.fillStyle = isDark
            ? `rgba(163, 162, 155, ${(heat * 0.42).toFixed(2)})`
            : `rgba(87, 86, 79, ${(heat * 0.38).toFixed(2)})`;
        }
        const size = cell.hot ? 5 : 4;
        ctx.fillRect(Math.round(cell.x), Math.round(cell.y), size, size);
      }
    };

    if (prefersReduced) {
      drawFrame(0);
      return;
    }

    let rafId = 0;
    const loop = (now: number) => {
      drawFrame(now);
      rafId = window.requestAnimationFrame(loop);
    };
    rafId = window.requestAnimationFrame(loop);

    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-label="Bottom of the Pot easter egg"
      data-testid="easter-egg-panel"
      className="fixed bottom-4 right-4 z-50 w-[min(24rem,calc(100vw-2rem))] rounded-lg overflow-hidden border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] bp-fade-up"
    >
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] bg-[var(--surface-subtle)]">
        <span className="font-mono text-[11px] font-medium tracking-wider text-[var(--ink)]">
          Bottom of the Pot
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close Bottom of the Pot panel"
          className="size-7 rounded-md inline-flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)] cursor-pointer"
        >
          <X className="size-3.5" aria-hidden="true" />
        </button>
      </div>

      <div className="relative overflow-hidden border-b border-[var(--border)]">
        <canvas
          ref={canvasRef}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            pointerRef.current = {
              x: e.clientX - rect.left,
              y: e.clientY - rect.top,
              active: true,
            };
          }}
          onMouseLeave={() => {
            pointerRef.current.active = false;
          }}
          className="w-full h-[128px] block"
          aria-hidden="true"
        />
        <Pointer aria-hidden="true">
          <div
            className="size-6 rounded-sm border border-[var(--accent)] bg-[var(--surface)]/90 flex items-center justify-center shadow-xs"
          >
            <Flame className="size-3.5 text-[var(--accent)]" aria-hidden="true" />
          </div>
        </Pointer>
      </div>

      <div className="p-4 flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--ink)]">
            You scraped all the way to the bottom.
          </h3>
          <p className="text-xs text-[var(--ink-muted)] mt-1.5 leading-relaxed">
            In West African cooking, the smoky crust at the bottom of the pot holds the deepest flavor. Most people stop at the top scoop. You stayed for the good part.
          </p>
        </div>

        <div className="flex items-center justify-start gap-2 pt-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={toggleJollofAccent}
            className="h-8 px-3 text-xs border-[var(--border-strong)] bg-[var(--bg)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer"
          >
            <Flame className="size-3.5 mr-1.5 text-[var(--accent)]" aria-hidden="true" />
            <span>{jollofAccent ? 'Restore Forest Green' : 'Try Party Jollof accent'}</span>
          </Button>
        </div>
      </div>
    </div>
  );
};
