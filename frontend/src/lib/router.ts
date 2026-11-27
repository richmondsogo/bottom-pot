export type AppRoute =
  | 'home'
  | 'search'
  | 'product'
  | 'sources'
  | 'about'
  | 'contact'
  | 'privacy'
  | 'terms'
  | 'admin';

const WORKSPACE_ENTRY_PARAMS = new Set(['view', 'mock', 'q', 'role', 'k', 'saved']);

export function resolveRoute(pathname: string, search = ''): AppRoute {
  const cleanPath = (pathname || '/').replace(/\/+$/, '') || '/';
  if (cleanPath === '/admin') return 'admin';
  if (cleanPath === '/product') return 'product';
  if (cleanPath === '/sources') return 'sources';
  if (cleanPath === '/about') return 'about';
  if (cleanPath === '/contact') return 'contact';
  if (cleanPath === '/privacy') return 'privacy';
  if (cleanPath === '/terms') return 'terms';
  if (cleanPath === '/app' || cleanPath === '/search') return 'search';

  if (search) {
    const params = new URLSearchParams(search);
    for (const key of WORKSPACE_ENTRY_PARAMS) {
      const val = params.get(key);
      if (key === 'mock' && val !== null) return 'search';
      if (key === 'view' && (val === 'workspace' || val === 'search' || val === 'app')) return 'search';
      if (key === 'saved' && val === '1') return 'search';
      if ((key === 'q' || key === 'role' || key === 'k') && val) return 'search';
    }
  }

  return 'home';
}

export function routeToPath(route: AppRoute): string {
  switch (route) {
    case 'search':
      return '/app';
    case 'product':
      return '/product';
    case 'sources':
      return '/sources';
    case 'about':
      return '/about';
    case 'contact':
      return '/contact';
    case 'privacy':
      return '/privacy';
    case 'terms':
      return '/terms';
    case 'admin':
      return '/admin';
    case 'home':
    default:
      return '/';
  }
}
