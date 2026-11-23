import { useState } from 'react';
import { cn } from '@/lib/utils';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { buildLogoDevUrl, isSafeHttpsLogoUrl } from '../lib/logo';

interface CompanyMarkProps {
  company: string;
  logoUrl?: string | null;
  companyDomain?: string | null;
  logoDevToken?: string | null;
  size: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_CLASSES: Record<CompanyMarkProps['size'], string> = {
  sm: 'size-4 text-[8.5px]',
  md: 'size-7 text-xs',
  lg: 'size-9 text-xs',
};

const SIZE_PIXELS: Record<CompanyMarkProps['size'], number> = {
  sm: 16,
  md: 28,
  lg: 36,
};

interface LogoCandidate {
  source: 'api' | 'logo_dev';
  url: string;
}

export function CompanyMark({
  company,
  logoUrl,
  companyDomain,
  logoDevToken,
  size,
  className,
}: CompanyMarkProps) {
  const [failedUrls, setFailedUrls] = useState<Record<string, boolean>>({});

  const safeApiUrl = isSafeHttpsLogoUrl(logoUrl) ? logoUrl.trim() : null;
  const logoDevUrl = buildLogoDevUrl(companyDomain, logoDevToken, 128);
  const candidates: LogoCandidate[] = [];
  if (safeApiUrl) {
    candidates.push({ source: 'api', url: safeApiUrl });
  }
  if (logoDevUrl && logoDevUrl !== safeApiUrl) {
    candidates.push({ source: 'logo_dev', url: logoDevUrl });
  }

  const activeCandidate = candidates.find((candidate) => !failedUrls[candidate.url]) ?? null;
  const sizeClass = SIZE_CLASSES[size];
  const px = SIZE_PIXELS[size];

  if (activeCandidate) {
    return (
      <div
        data-testid="company-mark"
        data-logo-source={activeCandidate.source}
        className={cn(
          sizeClass,
          'rounded-none flex items-center justify-center shrink-0 border border-[var(--border)] bg-[#FAF8F5] overflow-hidden p-0.5',
          className
        )}
      >
        <img
          src={activeCandidate.url}
          alt={company || 'Company'}
          width={px}
          height={px}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="size-full object-contain rounded-none"
          onError={() =>
            setFailedUrls((prev) =>
              prev[activeCandidate.url] ? prev : { ...prev, [activeCandidate.url]: true }
            )
          }
        />
      </div>
    );
  }

  const initials = getCompanyInitials(company);
  const tileColor = getCompanyTileColor(company);

  return (
    <div
      data-testid="company-mark"
      data-logo-source="monogram"
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
