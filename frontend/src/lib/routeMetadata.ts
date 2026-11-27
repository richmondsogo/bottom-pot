import type { AppRoute } from './router.ts';

export const DEFAULT_SITE_ORIGIN = 'https://bottom-pot-puce.vercel.app';
export const OG_IMAGE_PATH = '/og-image.png';

export interface RouteMetadataEntry {
  route: AppRoute;
  path: string;
  title: string;
  description: string;
  robots: string;
  includeInSitemap: boolean;
  omitCanonical?: boolean;
}

export const ROUTE_METADATA: Record<AppRoute, RouteMetadataEntry> = {
  home: {
    route: 'home',
    path: '/',
    title: 'Find Jobs You Can Actually Apply To · Bottom Pot',
    description:
      'Search company career pages and selected job boards. Check the work setup and country eligibility, then open the original listing.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  product: {
    route: 'product',
    path: '/product',
    title: 'How Bottom Pot Works · Search and Apply at the Source',
    description:
      'See how to search for jobs, review work arrangements and applicant-country eligibility, and continue to the original employer listing.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  about: {
    route: 'about',
    path: '/about',
    title: 'About Bottom Pot · Search-First Job Discovery',
    description:
      'Bottom Pot helps people find relevant opportunities and reach the original employer listing.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  sources: {
    route: 'sources',
    path: '/sources',
    title: 'Job Search Sources · Bottom Pot',
    description:
      'Explore the hiring platforms and selected job boards Bottom Pot searches for job opportunities.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  contact: {
    route: 'contact',
    path: '/contact',
    title: 'Contact Bottom Pot',
    description:
      'Contact Bottom Pot with feedback, broken links, incorrect job details or questions about the search experience.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  privacy: {
    route: 'privacy',
    path: '/privacy',
    title: 'Privacy Policy · Bottom Pot',
    description:
      'Learn what information Bottom Pot receives, what stays in your browser and which services help run the site.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  terms: {
    route: 'terms',
    path: '/terms',
    title: 'Terms of Service · Bottom Pot',
    description:
      'Read the terms for using Bottom Pot, including important information about job listings, eligibility labels and external links.',
    robots: 'index,follow',
    includeInSitemap: true,
  },
  search: {
    route: 'search',
    path: '/app',
    title: 'Search Jobs · Bottom Pot',
    description:
      'Search job listings across supported hiring platforms and selected job boards with Bottom Pot.',
    robots: 'noindex,follow',
    includeInSitemap: false,
  },
  admin: {
    route: 'admin',
    path: '/admin',
    title: 'Admin · Bottom Pot',
    description: 'Administrator workspace for Bottom Pot.',
    robots: 'noindex,nofollow',
    includeInSitemap: false,
    omitCanonical: true,
  },
};

export const PRERENDERED_SUBROUTES: Array<{ slug: string; route: AppRoute }> = [
  { slug: 'product', route: 'product' },
  { slug: 'about', route: 'about' },
  { slug: 'sources', route: 'sources' },
  { slug: 'contact', route: 'contact' },
  { slug: 'privacy', route: 'privacy' },
  { slug: 'terms', route: 'terms' },
  { slug: 'app', route: 'search' },
  { slug: 'admin', route: 'admin' },
];

export const ROUTE_META_START_MARKER = '<!-- bp:route-meta:start -->';
export const ROUTE_META_END_MARKER = '<!-- bp:route-meta:end -->';

function normalizeOrigin(raw?: string, assumeHttps = false): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const candidate =
    assumeHttps && !/^https?:\/\//i.test(trimmed) ? `https://${trimmed}` : trimmed;
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

export function resolveSiteOrigin(env?: {
  VITE_SITE_URL?: string;
  VERCEL_PROJECT_PRODUCTION_URL?: string;
}): string {
  return (
    normalizeOrigin(env?.VITE_SITE_URL, false) ||
    normalizeOrigin(env?.VERCEL_PROJECT_PRODUCTION_URL, true) ||
    DEFAULT_SITE_ORIGIN
  );
}

export function buildCanonicalUrl(route: AppRoute, siteOrigin: string): string | null {
  const entry = ROUTE_METADATA[route];
  if (entry.omitCanonical) return null;
  return entry.path === '/' ? `${siteOrigin}/` : `${siteOrigin}${entry.path}`;
}

function escapeHtmlAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeHtmlText(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function renderRouteMetadataTags(route: AppRoute, siteOrigin: string): string {
  const entry = ROUTE_METADATA[route];
  const canonicalUrl = buildCanonicalUrl(route, siteOrigin);
  const ogImageUrl = `${siteOrigin}${OG_IMAGE_PATH}`;

  const lines: string[] = [
    `    <meta name="description" content="${escapeHtmlAttr(entry.description)}" />`,
    `    <meta name="robots" content="${escapeHtmlAttr(entry.robots)}" />`,
  ];

  if (canonicalUrl) {
    lines.push(`    <link rel="canonical" href="${escapeHtmlAttr(canonicalUrl)}" />`);
  }

  lines.push(
    '    <meta property="og:type" content="website" />',
    '    <meta property="og:site_name" content="Bottom Pot" />',
    `    <meta property="og:title" content="${escapeHtmlAttr(entry.title)}" />`,
    `    <meta property="og:description" content="${escapeHtmlAttr(entry.description)}" />`
  );

  if (canonicalUrl) {
    lines.push(`    <meta property="og:url" content="${escapeHtmlAttr(canonicalUrl)}" />`);
  }

  lines.push(
    `    <meta property="og:image" content="${escapeHtmlAttr(ogImageUrl)}" />`,
    '    <meta name="twitter:card" content="summary_large_image" />',
    `    <meta name="twitter:title" content="${escapeHtmlAttr(entry.title)}" />`,
    `    <meta name="twitter:description" content="${escapeHtmlAttr(entry.description)}" />`,
    `    <meta name="twitter:image" content="${escapeHtmlAttr(ogImageUrl)}" />`,
    `    <title>${escapeHtmlText(entry.title)}</title>`
  );

  return lines.join('\n');
}

export function injectRouteMetadata(
  htmlTemplate: string,
  route: AppRoute,
  siteOrigin: string
): string {
  const startIdx = htmlTemplate.indexOf(ROUTE_META_START_MARKER);
  const endIdx = htmlTemplate.indexOf(ROUTE_META_END_MARKER);
  if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
    throw new Error('Missing bp:route-meta markers in HTML template.');
  }

  const before = htmlTemplate.slice(0, startIdx);
  const after = htmlTemplate.slice(endIdx + ROUTE_META_END_MARKER.length);
  const renderedBlock = [
    ROUTE_META_START_MARKER,
    renderRouteMetadataTags(route, siteOrigin),
    `    ${ROUTE_META_END_MARKER}`,
  ].join('\n');

  return `${before}${renderedBlock}${after}`;
}

export function buildRobotsTxt(siteOrigin: string): string {
  return [
    'User-agent: *',
    'Allow: /',
    'Disallow: /admin',
    'Disallow: /api/',
    '',
    `Sitemap: ${siteOrigin}/sitemap.xml`,
    '',
  ].join('\n');
}

export function buildSitemapXml(siteOrigin: string): string {
  const publicRoutes = Object.values(ROUTE_METADATA).filter((entry) => entry.includeInSitemap);
  const urlNodes = publicRoutes.map((entry) => {
    const loc = entry.path === '/' ? `${siteOrigin}/` : `${siteOrigin}${entry.path}`;
    return `  <url>\n    <loc>${escapeHtmlText(loc)}</loc>\n  </url>`;
  });
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urlNodes,
    '</urlset>',
    '',
  ].join('\n');
}
