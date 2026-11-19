export interface CountryEntry {
  code: string;
  name: string;
  region: string;
}

export const PRIORITY_COUNTRY_CODES: readonly string[] = [
  'NG',
  'GH',
  'KE',
  'ZA',
  'EG',
  'GB',
  'DE',
  'US',
  'CA',
  'IN',
  'SG',
  'AU',
];

export const COUNTRIES: readonly CountryEntry[] = [
  { code: 'AF', name: 'Afghanistan', region: 'APAC' },
  { code: 'AL', name: 'Albania', region: 'Europe' },
  { code: 'DZ', name: 'Algeria', region: 'Africa' },
  { code: 'AD', name: 'Andorra', region: 'Europe' },
  { code: 'AO', name: 'Angola', region: 'Africa' },
  { code: 'AG', name: 'Antigua and Barbuda', region: 'Americas' },
  { code: 'AR', name: 'Argentina', region: 'LATAM' },
  { code: 'AM', name: 'Armenia', region: 'Europe' },
  { code: 'AU', name: 'Australia', region: 'APAC' },
  { code: 'AT', name: 'Austria', region: 'EU' },
  { code: 'AZ', name: 'Azerbaijan', region: 'Europe' },
  { code: 'BS', name: 'Bahamas', region: 'Americas' },
  { code: 'BH', name: 'Bahrain', region: 'MENA' },
  { code: 'BD', name: 'Bangladesh', region: 'APAC' },
  { code: 'BB', name: 'Barbados', region: 'Americas' },
  { code: 'BY', name: 'Belarus', region: 'Europe' },
  { code: 'BE', name: 'Belgium', region: 'EU' },
  { code: 'BZ', name: 'Belize', region: 'LATAM' },
  { code: 'BJ', name: 'Benin', region: 'Africa' },
  { code: 'BT', name: 'Bhutan', region: 'APAC' },
  { code: 'BO', name: 'Bolivia', region: 'LATAM' },
  { code: 'BA', name: 'Bosnia and Herzegovina', region: 'Europe' },
  { code: 'BW', name: 'Botswana', region: 'Africa' },
  { code: 'BR', name: 'Brazil', region: 'LATAM' },
  { code: 'BN', name: 'Brunei', region: 'APAC' },
  { code: 'BG', name: 'Bulgaria', region: 'EU' },
  { code: 'BF', name: 'Burkina Faso', region: 'Africa' },
  { code: 'BI', name: 'Burundi', region: 'Africa' },
  { code: 'CV', name: 'Cabo Verde', region: 'Africa' },
  { code: 'KH', name: 'Cambodia', region: 'APAC' },
  { code: 'CM', name: 'Cameroon', region: 'Africa' },
  { code: 'CA', name: 'Canada', region: 'North America' },
  { code: 'CF', name: 'Central African Republic', region: 'Africa' },
  { code: 'TD', name: 'Chad', region: 'Africa' },
  { code: 'CL', name: 'Chile', region: 'LATAM' },
  { code: 'CN', name: 'China', region: 'APAC' },
  { code: 'CO', name: 'Colombia', region: 'LATAM' },
  { code: 'KM', name: 'Comoros', region: 'Africa' },
  { code: 'CG', name: 'Congo', region: 'Africa' },
  { code: 'CD', name: 'DR Congo', region: 'Africa' },
  { code: 'CR', name: 'Costa Rica', region: 'LATAM' },
  { code: 'CI', name: "Côte d'Ivoire", region: 'Africa' },
  { code: 'HR', name: 'Croatia', region: 'EU' },
  { code: 'CU', name: 'Cuba', region: 'LATAM' },
  { code: 'CY', name: 'Cyprus', region: 'EU' },
  { code: 'CZ', name: 'Czech Republic', region: 'EU' },
  { code: 'DK', name: 'Denmark', region: 'EU' },
  { code: 'DJ', name: 'Djibouti', region: 'Africa' },
  { code: 'DM', name: 'Dominica', region: 'Americas' },
  { code: 'DO', name: 'Dominican Republic', region: 'LATAM' },
  { code: 'EC', name: 'Ecuador', region: 'LATAM' },
  { code: 'EG', name: 'Egypt', region: 'Africa' },
  { code: 'SV', name: 'El Salvador', region: 'LATAM' },
  { code: 'GQ', name: 'Equatorial Guinea', region: 'Africa' },
  { code: 'ER', name: 'Eritrea', region: 'Africa' },
  { code: 'EE', name: 'Estonia', region: 'EU' },
  { code: 'SZ', name: 'Eswatini', region: 'Africa' },
  { code: 'ET', name: 'Ethiopia', region: 'Africa' },
  { code: 'FJ', name: 'Fiji', region: 'APAC' },
  { code: 'FI', name: 'Finland', region: 'EU' },
  { code: 'FR', name: 'France', region: 'EU' },
  { code: 'GA', name: 'Gabon', region: 'Africa' },
  { code: 'GM', name: 'Gambia', region: 'Africa' },
  { code: 'GE', name: 'Georgia', region: 'Europe' },
  { code: 'DE', name: 'Germany', region: 'EU' },
  { code: 'GH', name: 'Ghana', region: 'Africa' },
  { code: 'GR', name: 'Greece', region: 'EU' },
  { code: 'GD', name: 'Grenada', region: 'Americas' },
  { code: 'GT', name: 'Guatemala', region: 'LATAM' },
  { code: 'GN', name: 'Guinea', region: 'Africa' },
  { code: 'GW', name: 'Guinea-Bissau', region: 'Africa' },
  { code: 'GY', name: 'Guyana', region: 'LATAM' },
  { code: 'HT', name: 'Haiti', region: 'LATAM' },
  { code: 'HN', name: 'Honduras', region: 'LATAM' },
  { code: 'HK', name: 'Hong Kong', region: 'APAC' },
  { code: 'HU', name: 'Hungary', region: 'EU' },
  { code: 'IS', name: 'Iceland', region: 'EEA' },
  { code: 'IN', name: 'India', region: 'APAC' },
  { code: 'ID', name: 'Indonesia', region: 'APAC' },
  { code: 'IR', name: 'Iran', region: 'MENA' },
  { code: 'IQ', name: 'Iraq', region: 'MENA' },
  { code: 'IE', name: 'Ireland', region: 'EU' },
  { code: 'IL', name: 'Israel', region: 'MENA' },
  { code: 'IT', name: 'Italy', region: 'EU' },
  { code: 'JM', name: 'Jamaica', region: 'Americas' },
  { code: 'JP', name: 'Japan', region: 'APAC' },
  { code: 'JO', name: 'Jordan', region: 'MENA' },
  { code: 'KZ', name: 'Kazakhstan', region: 'APAC' },
  { code: 'KE', name: 'Kenya', region: 'Africa' },
  { code: 'KI', name: 'Kiribati', region: 'APAC' },
  { code: 'KW', name: 'Kuwait', region: 'MENA' },
  { code: 'KG', name: 'Kyrgyzstan', region: 'APAC' },
  { code: 'LA', name: 'Laos', region: 'APAC' },
  { code: 'LV', name: 'Latvia', region: 'EU' },
  { code: 'LB', name: 'Lebanon', region: 'MENA' },
  { code: 'LS', name: 'Lesotho', region: 'Africa' },
  { code: 'LR', name: 'Liberia', region: 'Africa' },
  { code: 'LY', name: 'Libya', region: 'Africa' },
  { code: 'LI', name: 'Liechtenstein', region: 'EEA' },
  { code: 'LT', name: 'Lithuania', region: 'EU' },
  { code: 'LU', name: 'Luxembourg', region: 'EU' },
  { code: 'MG', name: 'Madagascar', region: 'Africa' },
  { code: 'MW', name: 'Malawi', region: 'Africa' },
  { code: 'MY', name: 'Malaysia', region: 'APAC' },
  { code: 'MV', name: 'Maldives', region: 'APAC' },
  { code: 'ML', name: 'Mali', region: 'Africa' },
  { code: 'MT', name: 'Malta', region: 'EU' },
  { code: 'MH', name: 'Marshall Islands', region: 'APAC' },
  { code: 'MR', name: 'Mauritania', region: 'Africa' },
  { code: 'MU', name: 'Mauritius', region: 'Africa' },
  { code: 'MX', name: 'Mexico', region: 'North America' },
  { code: 'FM', name: 'Micronesia', region: 'APAC' },
  { code: 'MD', name: 'Moldova', region: 'Europe' },
  { code: 'MC', name: 'Monaco', region: 'Europe' },
  { code: 'MN', name: 'Mongolia', region: 'APAC' },
  { code: 'ME', name: 'Montenegro', region: 'Europe' },
  { code: 'MA', name: 'Morocco', region: 'Africa' },
  { code: 'MZ', name: 'Mozambique', region: 'Africa' },
  { code: 'MM', name: 'Myanmar', region: 'APAC' },
  { code: 'NA', name: 'Namibia', region: 'Africa' },
  { code: 'NR', name: 'Nauru', region: 'APAC' },
  { code: 'NP', name: 'Nepal', region: 'APAC' },
  { code: 'NL', name: 'Netherlands', region: 'EU' },
  { code: 'NZ', name: 'New Zealand', region: 'APAC' },
  { code: 'NI', name: 'Nicaragua', region: 'LATAM' },
  { code: 'NE', name: 'Niger', region: 'Africa' },
  { code: 'NG', name: 'Nigeria', region: 'Africa' },
  { code: 'MK', name: 'North Macedonia', region: 'Europe' },
  { code: 'NO', name: 'Norway', region: 'EEA' },
  { code: 'OM', name: 'Oman', region: 'MENA' },
  { code: 'PK', name: 'Pakistan', region: 'APAC' },
  { code: 'PW', name: 'Palau', region: 'APAC' },
  { code: 'PS', name: 'Palestine', region: 'MENA' },
  { code: 'PA', name: 'Panama', region: 'LATAM' },
  { code: 'PG', name: 'Papua New Guinea', region: 'APAC' },
  { code: 'PY', name: 'Paraguay', region: 'LATAM' },
  { code: 'PE', name: 'Peru', region: 'LATAM' },
  { code: 'PH', name: 'Philippines', region: 'APAC' },
  { code: 'PL', name: 'Poland', region: 'EU' },
  { code: 'PT', name: 'Portugal', region: 'EU' },
  { code: 'PR', name: 'Puerto Rico', region: 'LATAM' },
  { code: 'QA', name: 'Qatar', region: 'MENA' },
  { code: 'RO', name: 'Romania', region: 'EU' },
  { code: 'RU', name: 'Russia', region: 'Europe' },
  { code: 'RW', name: 'Rwanda', region: 'Africa' },
  { code: 'KN', name: 'Saint Kitts and Nevis', region: 'Americas' },
  { code: 'LC', name: 'Saint Lucia', region: 'Americas' },
  { code: 'VC', name: 'Saint Vincent and the Grenadines', region: 'Americas' },
  { code: 'WS', name: 'Samoa', region: 'APAC' },
  { code: 'SM', name: 'San Marino', region: 'Europe' },
  { code: 'ST', name: 'São Tomé and Príncipe', region: 'Africa' },
  { code: 'SA', name: 'Saudi Arabia', region: 'MENA' },
  { code: 'SN', name: 'Senegal', region: 'Africa' },
  { code: 'RS', name: 'Serbia', region: 'Europe' },
  { code: 'SC', name: 'Seychelles', region: 'Africa' },
  { code: 'SL', name: 'Sierra Leone', region: 'Africa' },
  { code: 'SG', name: 'Singapore', region: 'APAC' },
  { code: 'SK', name: 'Slovakia', region: 'EU' },
  { code: 'SI', name: 'Slovenia', region: 'EU' },
  { code: 'SB', name: 'Solomon Islands', region: 'APAC' },
  { code: 'SO', name: 'Somalia', region: 'Africa' },
  { code: 'ZA', name: 'South Africa', region: 'Africa' },
  { code: 'KR', name: 'South Korea', region: 'APAC' },
  { code: 'SS', name: 'South Sudan', region: 'Africa' },
  { code: 'ES', name: 'Spain', region: 'EU' },
  { code: 'LK', name: 'Sri Lanka', region: 'APAC' },
  { code: 'SD', name: 'Sudan', region: 'Africa' },
  { code: 'SR', name: 'Suriname', region: 'LATAM' },
  { code: 'SE', name: 'Sweden', region: 'EU' },
  { code: 'CH', name: 'Switzerland', region: 'Europe' },
  { code: 'SY', name: 'Syria', region: 'MENA' },
  { code: 'TW', name: 'Taiwan', region: 'APAC' },
  { code: 'TJ', name: 'Tajikistan', region: 'APAC' },
  { code: 'TZ', name: 'Tanzania', region: 'Africa' },
  { code: 'TH', name: 'Thailand', region: 'APAC' },
  { code: 'TL', name: 'Timor-Leste', region: 'APAC' },
  { code: 'TG', name: 'Togo', region: 'Africa' },
  { code: 'TO', name: 'Tonga', region: 'APAC' },
  { code: 'TT', name: 'Trinidad and Tobago', region: 'Americas' },
  { code: 'TN', name: 'Tunisia', region: 'Africa' },
  { code: 'TR', name: 'Turkey', region: 'Europe' },
  { code: 'TM', name: 'Turkmenistan', region: 'APAC' },
  { code: 'TV', name: 'Tuvalu', region: 'APAC' },
  { code: 'UG', name: 'Uganda', region: 'Africa' },
  { code: 'UA', name: 'Ukraine', region: 'Europe' },
  { code: 'AE', name: 'United Arab Emirates', region: 'MENA' },
  { code: 'GB', name: 'United Kingdom', region: 'Europe' },
  { code: 'US', name: 'United States', region: 'North America' },
  { code: 'UY', name: 'Uruguay', region: 'LATAM' },
  { code: 'UZ', name: 'Uzbekistan', region: 'APAC' },
  { code: 'VU', name: 'Vanuatu', region: 'APAC' },
  { code: 'VA', name: 'Vatican City', region: 'Europe' },
  { code: 'VE', name: 'Venezuela', region: 'LATAM' },
  { code: 'VN', name: 'Vietnam', region: 'APAC' },
  { code: 'YE', name: 'Yemen', region: 'MENA' },
  { code: 'ZM', name: 'Zambia', region: 'Africa' },
  { code: 'ZW', name: 'Zimbabwe', region: 'Africa' },
];

const COUNTRY_BY_CODE = new Map<string, CountryEntry>(
  COUNTRIES.map((c) => [c.code, c])
);

const COUNTRY_NAME_TO_CODE = new Map<string, string>(
  COUNTRIES.map((c) => [c.name.toLowerCase(), c.code])
);

const EXTRA_ALIASES_TO_CODE: Record<string, string> = {
  uk: 'GB',
  'u.k': 'GB',
  'u.k.': 'GB',
  'great britain': 'GB',
  britain: 'GB',
  england: 'GB',
  scotland: 'GB',
  wales: 'GB',
  us: 'US',
  'u.s': 'US',
  'u.s.': 'US',
  usa: 'US',
  'u.s.a': 'US',
  'u.s.a.': 'US',
  'united states of america': 'US',
  deutschland: 'DE',
  españa: 'ES',
  espana: 'ES',
  espagne: 'ES',
  tunisie: 'TN',
  brasil: 'BR',
  uae: 'AE',
  czechia: 'CZ',
  holland: 'NL',
  'ivory coast': 'CI',
  "cote d'ivoire": 'CI',
};

const REGION_ALIASES: Record<string, string> = {
  worldwide: 'Worldwide',
  global: 'Worldwide',
  anywhere: 'Worldwide',
  africa: 'Africa',
  'sub-saharan africa': 'Sub-Saharan Africa',
  'sub saharan africa': 'Sub-Saharan Africa',
  ssa: 'Sub-Saharan Africa',
  eu: 'EU',
  'european union': 'EU',
  eea: 'EEA',
  'european economic area': 'EEA',
  europe: 'Europe',
  emea: 'EMEA',
  latam: 'LATAM',
  'latin america': 'LATAM',
  apac: 'APAC',
  'asia pacific': 'APAC',
  'asia-pacific': 'APAC',
  'north america': 'North America',
  americas: 'Americas',
  mena: 'MENA',
};

const AFRICA_CODES = new Set([
  'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD',
  'CI', 'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'KE',
  'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ', 'NA', 'NE', 'NG',
  'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG',
  'ZM', 'ZW',
]);
const NORTH_AFRICA_CODES = new Set(['DZ', 'EG', 'LY', 'MA', 'TN']);
const EU_CODES = new Set([
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU',
  'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES',
  'SE',
]);
const EEA_CODES = new Set([...EU_CODES, 'IS', 'LI', 'NO']);
const EUROPE_CODES = new Set([
  ...EEA_CODES,
  'AL', 'AD', 'AM', 'AZ', 'BA', 'BY', 'CH', 'GB', 'GE', 'MC', 'MD', 'ME', 'MK',
  'RS', 'RU', 'SM', 'TR', 'UA', 'VA',
]);
const MENA_CODES = new Set([
  ...NORTH_AFRICA_CODES,
  'AE', 'BH', 'IL', 'IQ', 'IR', 'JO', 'KW', 'LB', 'OM', 'PS', 'QA', 'SA', 'SY', 'YE',
]);
const NORTH_AMERICA_CODES = new Set(['CA', 'MX', 'US']);
const LATAM_CODES = new Set([
  'AR', 'BO', 'BR', 'BZ', 'CL', 'CO', 'CR', 'CU', 'DO', 'EC', 'GT', 'HN', 'HT',
  'MX', 'NI', 'PA', 'PE', 'PR', 'PY', 'SV', 'UY', 'VE',
]);
const APAC_CODES = new Set([
  'AU', 'BD', 'BN', 'CN', 'FJ', 'HK', 'ID', 'IN', 'JP', 'KH', 'KR', 'LA', 'LK',
  'MM', 'MY', 'NP', 'NZ', 'PG', 'PH', 'PK', 'SG', 'TH', 'TW', 'VN',
]);

export const REGION_MEMBERS: Record<string, Set<string>> = {
  Africa: AFRICA_CODES,
  'Sub-Saharan Africa': new Set([...AFRICA_CODES].filter((c) => !NORTH_AFRICA_CODES.has(c))),
  EU: EU_CODES,
  EEA: EEA_CODES,
  Europe: EUROPE_CODES,
  MENA: MENA_CODES,
  EMEA: new Set([...EUROPE_CODES, ...MENA_CODES, ...AFRICA_CODES]),
  'North America': NORTH_AMERICA_CODES,
  LATAM: LATAM_CODES,
  Americas: new Set([...NORTH_AMERICA_CODES, ...LATAM_CODES]),
  APAC: APAC_CODES,
};

export const UNIFORM_CAPABLE_REGIONS = new Set([
  'Africa',
  'Sub-Saharan Africa',
  'EU',
  'EEA',
]);

export function getCountryByCode(code?: string | null): CountryEntry | null {
  const norm = normalizeCountryCode(code);
  if (!norm) return null;
  return COUNTRY_BY_CODE.get(norm) ?? null;
}

export function normalizeRegionName(raw?: string | null): string | null {
  if (!raw || typeof raw !== 'string') return null;
  const cleaned = raw.trim().replace(/\s+/g, ' ').toLowerCase();
  if (!cleaned) return null;
  return REGION_ALIASES[cleaned] ?? null;
}

export function normalizeCountryCode(raw?: string | null): string | null {
  if (!raw || typeof raw !== 'string') return null;
  const cleaned = raw.trim().replace(/\s+/g, ' ').replace(/^[ ,.;:-]+|[ ,.;:-]+$/g, '');
  if (!cleaned) return null;
  const upper = cleaned.toUpperCase();
  if (upper === 'UK') return 'GB';
  if (COUNTRY_BY_CODE.has(upper)) return upper;
  const low = cleaned.toLowerCase();
  if (low in REGION_ALIASES) return null;
  return COUNTRY_NAME_TO_CODE.get(low) ?? EXTRA_ALIASES_TO_CODE[low] ?? null;
}

export function isCountryInRegion(countryCode: string, region: string): boolean {
  const code = normalizeCountryCode(countryCode);
  const canonicalRegion = normalizeRegionName(region) ?? region;
  if (!code) return false;
  if (canonicalRegion === 'Worldwide') return true;
  const members = REGION_MEMBERS[canonicalRegion];
  return Boolean(members && members.has(code));
}
