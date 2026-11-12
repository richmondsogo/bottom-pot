import { useState } from 'react';
import { cn } from '@/lib/utils';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';

interface CompanyMarkProps {
  company: string;
  logoUrl?: string | null;
  size: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_CLASSES: Record<CompanyMarkProps['size'], string> = {
  sm: 'size-4 text-[8.5px]',
  md: 'size-7 text-xs',
  lg: 'size-9 text-xs',
};

function isSafeHttpsLogoUrl(url?: string | null): url is string {
  if (!url) return false;
  const trimmed = url.trim();
  if (!trimmed.startsWith('https://')) return false;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function CompanyMark({ company, logoUrl, size, className }: CompanyMarkProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);

  const safeUrl = isSafeHttpsLogoUrl(logoUrl) ? logoUrl.trim() : null;
  const showImage = Boolean(safeUrl && failedUrl !== safeUrl);
  const sizeClass = SIZE_CLASSES[size];

  if (showImage && safeUrl) {
    return (
      <div
        data-testid="company-mark"
        className={cn(
          sizeClass,
          'rounded-none flex items-center justify-center shrink-0 border border-[var(--border)] bg-[#FAF8F5] overflow-hidden p-0.5',
          className
        )}
        aria-hidden="true"
      >
        <img
          src={safeUrl}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="size-full object-contain rounded-none"
          onError={() => setFailedUrl(safeUrl)}
        />
      </div>
    );
  }

  const initials = getCompanyInitials(company);
  const tileColor = getCompanyTileColor(company);

  return (
    <div
      data-testid="company-mark"
      className={cn(
        sizeClass,
        'rounded-none flex items-center justify-center font-bold shrink-0 border',
        className
      )}
      style={{
        backgroundColor: tileColor.bg,
        color: tileColor.color,
        borderColor: tileColor.border,
      }}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}
