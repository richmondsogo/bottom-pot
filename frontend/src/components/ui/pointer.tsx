'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  type HTMLMotionProps,
} from 'motion/react';
import { cn } from '@/lib/utils';

const SPRING_CONFIG = {
  stiffness: 520,
  damping: 36,
  mass: 0.4,
};

/**
 * Custom registry pointer (@magicui/pointer adapted for parent-relative overlay coordinates).
 * Hides the native cursor over its direct parent container on fine-pointer, motion-allowed devices.
 */
export function Pointer({
  className,
  style,
  children,
  ...props
}: HTMLMotionProps<'div'>): React.ReactNode {
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const x = useSpring(rawX, SPRING_CONFIG);
  const y = useSpring(rawY, SPRING_CONFIG);
  const [isActive, setIsActive] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const finePointer = window.matchMedia('(pointer: fine)').matches;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!finePointer || reducedMotion) return;

    const parentElement = containerRef.current?.parentElement ?? null;
    if (!parentElement) return;

    const prevCursor = parentElement.style.cursor;
    parentElement.style.cursor = 'none';

    const updateCoords = (e: MouseEvent) => {
      const rect = parentElement.getBoundingClientRect();
      rawX.set(e.clientX - rect.left);
      rawY.set(e.clientY - rect.top);
      setIsActive(true);
    };

    const handleMouseLeave = () => {
      setIsActive(false);
    };

    parentElement.addEventListener('mousemove', updateCoords);
    parentElement.addEventListener('mouseenter', updateCoords);
    parentElement.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      parentElement.style.cursor = prevCursor;
      parentElement.removeEventListener('mousemove', updateCoords);
      parentElement.removeEventListener('mouseenter', updateCoords);
      parentElement.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [rawX, rawY]);

  return (
    <>
      <div ref={containerRef} className="hidden" aria-hidden="true" />
      <AnimatePresence>
        {isActive && (
          <motion.div
            className={cn('pointer-events-none absolute top-0 left-0 z-20 -translate-x-1/2 -translate-y-1/2', className)}
            style={{
              x,
              y,
              ...style,
            }}
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.4, opacity: 0 }}
            transition={{ duration: 0.14 }}
            {...props}
          >
            {children || (
              <div className="size-4 border border-[var(--accent)] bg-[var(--accent)]/15" style={{ borderRadius: 0 }} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
