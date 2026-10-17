import type { JobListing, DoneMetrics } from '../types';

/**
 * Checks whether mock data mode is active.
 * Only allowed in dev mode or when explicit VITE_ENABLE_MOCK flag is present.
 */
export function isMockModeActive(): boolean {
  if (typeof window === 'undefined') return false;

  // Never active in production builds unless VITE_ENABLE_MOCK is set
  if (!import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK !== 'true') {
    return false;
  }

  const params = new URLSearchParams(window.location.search);
  const mockParam = params.get('mock');
  if (mockParam !== null) return true;

  try {
    return localStorage.getItem('bp.mock') === 'true';
  } catch {
    return false;
  }
}

export function getMockScenario(): 'default' | 'empty' | 'error' | 'slow' {
  if (typeof window === 'undefined') return 'default';
  const params = new URLSearchParams(window.location.search);
  const val = params.get('mock')?.toLowerCase();
  if (val === 'empty' || val === 'no_results' || val === '0') return 'empty';
  if (val === 'error' || val === '500') return 'error';
  if (val === 'slow') return 'slow';
  return 'default';
}

export const getMockModeType = getMockScenario;

/**
 * Deterministic generation of 150+ realistic job listings with specific edge cases:
 * - 150+ rows
 * - Very long titles (150+ chars)
 * - Non-Latin characters (Japanese)
 * - Missing location / salary / job type / work model
 * - Odd company casing (e.e. cummings tech, ALLCAPS INC, lowercaseworks)
 * - Varied work models (remote, hybrid, in_person, unknown)
 */
export function generateMockJobs(): JobListing[] {
  const jobs: JobListing[] = [];

  const providers = ['greenhouse', 'lever', 'ashby', 'workable', 'recruitee', 'smartrecruiters', 'teamtailor', 'jobberman'];
  const titles = [
    'Senior Full-Stack Engineer',
    'Distributed Systems Architect',
    'Staff Backend Developer',
    'Frontend Infrastructure Engineer',
    'Cloud Security Specialist',
    'Site Reliability Engineer',
    'Product Designer',
    'Mobile Application Engineer (React Native)',
    'Data Platform Engineer',
    'DevOps Automation Lead',
    'Technical Solutions Consultant',
    'Machine Learning Systems Engineer',
    'Core Platform Developer',
    'Engineering Manager - Payments',
  ];

  const companies = [
    'Stripe Global',
    'Moniepoint Nigeria',
    'PiggyVest',
    'Interswitch Group',
    'Andela',
    'Paystack Inc',
    'Shopify',
    'GitHub',
    'Linear',
    'Vercel Core',
    'Supabase',
    'Tailscale Networks',
    'Canva',
    'Figma Systems',
  ];

  const locations = [
    'Lagos, Nigeria',
    'Remote (Worldwide)',
    'Remote (EMEA)',
    'Abuja, Nigeria',
    'London, UK',
    'San Francisco, CA',
    'Remote (US/Canada)',
    'Berlin, Germany',
    'Amsterdam, Netherlands',
    null, // Missing location edge case
  ];

  const workModels: ('remote' | 'hybrid' | 'in_person' | null)[] = ['remote', 'hybrid', 'in_person', null];
  const employmentTypes: ('full_time' | 'contract' | 'part_time' | 'internship' | null)[] = [
    'full_time',
    'contract',
    'part_time',
    'internship',
    null,
  ];

  // Specific Edge Cases Required by Spec:
  jobs.push({
    id: 'edge:long-title:1',
    provider: 'greenhouse',
    data_source: 'api',
    title:
      'Principal Distributed Systems & Multi-Cloud Infrastructure Security Architect [U.S. Citizenship Required, Top Secret / SCI Polygraph Clearance Mandated for Critical Operations]',
    company: 'Lockheed Tech Labs',
    company_slug: 'lockheed-tech',
    location: 'Remote (United States)',
    is_remote: true,
    employment_type: 'full_time',
    work_model: 'remote',
    salary: { minimum: 210000, maximum: 285000, currency: 'USD', period: 'year' },
    description: 'Lead architecture for resilient federal mission operations.',
    requirements: '10+ years distributed systems, Go, Kubernetes, clearance.',
    posted_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    scraped_at: new Date().toISOString(),
    apply_url: 'https://job-boards.greenhouse.io/lockheed/jobs/1',
    source_url: 'https://job-boards.greenhouse.io/lockheed/jobs/1',
    ats_source: 'greenhouse',
  });

  jobs.push({
    id: 'edge:japanese:2',
    provider: 'lever',
    data_source: 'api',
    title: 'シニアソフトウェアエンジニア (Senior Software Engineer - Global Platform)',
    company: 'Rakuten International',
    company_slug: 'rakuten',
    location: 'Tokyo / Remote (Japan)',
    is_remote: true,
    employment_type: 'full_time',
    work_model: 'remote',
    salary: { minimum: 9000000, maximum: 14000000, currency: 'JPY', period: 'year' },
    description: '次世代の大規模Eコマース基盤およびマイクロサービスの設計・開発を担うシニアエンジニアを募集しています。',
    requirements: 'Go言語またはTypeScriptを用いたバックエンド開発経験5年以上。',
    posted_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    scraped_at: new Date().toISOString(),
    apply_url: 'https://jobs.lever.co/rakuten/2',
    source_url: 'https://jobs.lever.co/rakuten/2',
    ats_source: 'lever',
  });

  jobs.push({
    id: 'edge:odd-casing-1:3',
    provider: 'ashby',
    data_source: 'api',
    title: 'creative systems programmer',
    company: 'e.e. cummings tech',
    company_slug: 'ee-cummings',
    location: null,
    is_remote: null,
    employment_type: null,
    work_model: null,
    salary: null,
    description: 'we build poetic software without capital letters or unnecessary boundaries.',
    requirements: 'intuition and deep algorithmic knowledge.',
    posted_at: null,
    scraped_at: new Date().toISOString(),
    apply_url: 'https://jobs.ashbyhq.com/ee-cummings/3',
    source_url: 'https://jobs.ashbyhq.com/ee-cummings/3',
    ats_source: 'ashby',
  });

  jobs.push({
    id: 'edge:odd-casing-2:4',
    provider: 'workable',
    data_source: 'api',
    title: 'QUANTITATIVE PROTOCOL RESEARCHER',
    company: 'ALLCAPS DYNAMICS CORP',
    company_slug: 'allcaps',
    location: 'New York, NY',
    is_remote: false,
    employment_type: 'contract',
    work_model: 'in_person',
    salary: 'USD 180,000 - 240,000 / year',
    description: 'HIGH FREQUENCY ARBITRAGE SYSTEM MODELING.',
    requirements: 'C++, RUST, APPLIED STOCHASTIC CALCULUS.',
    posted_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    scraped_at: new Date().toISOString(),
    apply_url: 'https://apply.workable.com/allcaps/4',
    source_url: 'https://apply.workable.com/allcaps/4',
    ats_source: 'workable',
  });

  jobs.push({
    id: 'edge:hybrid-nigeria:5',
    provider: 'jobberman',
    data_source: 'scrape',
    title: 'Mobile Banking Core Engineer',
    company: 'Kuda Microfinance Bank',
    company_slug: 'kuda',
    location: 'Victoria Island, Lagos',
    is_remote: false,
    employment_type: 'full_time',
    work_model: 'hybrid',
    salary: 'NGN 1,200,000 - 1,800,000 / month',
    description: 'Build robust core banking transaction workflows for millions of retail users.',
    requirements: 'Kotlin, Java, Spring Boot, high-reliability event systems.',
    posted_at: new Date(Date.now() - 86400000 * 1).toISOString(),
    scraped_at: new Date().toISOString(),
    apply_url: 'https://www.jobberman.com/listings/kuda-core-banking-5',
    source_url: 'https://www.jobberman.com/listings/kuda-core-banking-5',
    ats_source: 'jobberman',
  });

  // Generate up to 160 realistic diverse listings
  for (let i = 6; i <= 165; i++) {
    const provider = providers[i % providers.length];
    const company = companies[i % companies.length];
    const baseTitle = titles[i % titles.length];
    const location = locations[i % locations.length];
    const workModel = workModels[i % workModels.length];
    const employmentType = employmentTypes[i % employmentTypes.length];
    const daysAgo = (i % 28) + 1;
    const hasCompensation = i % 3 !== 0;

    jobs.push({
      id: `${provider}:${company.toLowerCase().replace(/[^a-z0-9]/g, '')}:${i}`,
      provider,
      data_source: provider === 'jobberman' ? 'scrape' : 'api',
      title: `${baseTitle}${i % 4 === 0 ? ' (Lead)' : ''}`,
      company: i % 11 === 0 ? company.toLowerCase() : company,
      company_slug: company.toLowerCase().replace(/[^a-z0-9]/g, '-'),
      location,
      is_remote: workModel === 'remote' ? true : workModel === 'in_person' ? false : null,
      employment_type: employmentType,
      work_model: workModel,
      salary: hasCompensation
        ? {
            minimum: 85000 + (i % 10) * 12000,
            maximum: 120000 + (i % 10) * 18000,
            currency: i % 5 === 0 ? 'GBP' : i % 7 === 0 ? 'EUR' : 'USD',
            period: 'year',
          }
        : null,
      description: `Join ${company} as a ${baseTitle}. We solve complex problems in cloud software, infrastructure, and user experiences across worldwide distributed teams.`,
      requirements: 'Demonstrated experience in modern engineering practices, clean code, and team collaboration.',
      posted_at: new Date(Date.now() - 86400000 * daysAgo).toISOString(),
      scraped_at: new Date().toISOString(),
      apply_url: `https://jobs.example.test/${company.toLowerCase().replace(/[^a-z0-9]/g, '')}/${i}`,
      source_url: `https://boards.${provider}.io/${company.toLowerCase().replace(/[^a-z0-9]/g, '')}/jobs/${i}`,
      ats_source: provider,
    });
  }

  return jobs;
}

export function generateMockMetrics(totalCount: number): DoneMetrics {
  return {
    total: totalCount,
    search_time_ms: 1240,
    serper_queries_used: 18,
    serper_calls: 18,
    serper_cache_hits: 4,
    pages_fetched: 26,
    providers_searched: [
      'greenhouse',
      'lever',
      'ashby',
      'workable',
      'recruitee',
      'smartrecruiters',
      'teamtailor',
      'jobberman',
    ],
    providers_skipped: [],
    cached: false,
  };
}

export const getMockMetrics = generateMockMetrics;
