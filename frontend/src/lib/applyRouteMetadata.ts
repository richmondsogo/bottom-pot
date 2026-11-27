import type { AppRoute } from './router';
import {
  OG_IMAGE_PATH,
  ROUTE_METADATA,
  buildCanonicalUrl,
  resolveSiteOrigin,
} from './routeMetadata';

function upsertMetaTag(
  attrName: 'name' | 'property',
  attrValue: string,
  content: string | null
): void {
  if (typeof document === 'undefined') return;
  const selector = `meta[${attrName}="${attrValue}"]`;
  const existing = document.head.querySelector(selector);
  if (content === null) {
    existing?.remove();
    return;
  }
  if (existing) {
    existing.setAttribute('content', content);
    return;
  }
  const el = document.createElement('meta');
  el.setAttribute(attrName, attrValue);
  el.setAttribute('content', content);
  document.head.appendChild(el);
}

function upsertCanonicalLink(href: string | null): void {
  if (typeof document === 'undefined') return;
  const existing = document.head.querySelector('link[rel="canonical"]');
  if (href === null) {
    existing?.remove();
    return;
  }
  if (existing) {
    existing.setAttribute('href', href);
    return;
  }
  const el = document.createElement('link');
  el.setAttribute('rel', 'canonical');
  el.setAttribute('href', href);
  document.head.appendChild(el);
}

export function applyRouteMetadata(
  route: AppRoute,
  siteOriginOverride?: string
): void {
  if (typeof document === 'undefined') return;

  const entry = ROUTE_METADATA[route];
  const siteOrigin =
    siteOriginOverride ||
    resolveSiteOrigin({
      VITE_SITE_URL:
        typeof import.meta !== 'undefined' && import.meta.env
          ? (import.meta.env.VITE_SITE_URL as string | undefined)
          : undefined,
    });
  const canonicalUrl = buildCanonicalUrl(route, siteOrigin);
  const ogImageUrl = `${siteOrigin}${OG_IMAGE_PATH}`;

  document.title = entry.title;
  upsertMetaTag('name', 'description', entry.description);
  upsertMetaTag('name', 'robots', entry.robots);
  upsertCanonicalLink(canonicalUrl);
  upsertMetaTag('property', 'og:site_name', 'Bottom Pot');
  upsertMetaTag('property', 'og:title', entry.title);
  upsertMetaTag('property', 'og:description', entry.description);
  upsertMetaTag('property', 'og:url', canonicalUrl);
  upsertMetaTag('property', 'og:image', ogImageUrl);
  upsertMetaTag('name', 'twitter:title', entry.title);
  upsertMetaTag('name', 'twitter:description', entry.description);
  upsertMetaTag('name', 'twitter:image', ogImageUrl);
}
