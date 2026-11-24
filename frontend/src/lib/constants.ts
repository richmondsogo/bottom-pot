export type PlatformCategory = 'monitored_ats' | 'enterprise_ats' | 'nigerian_board';

export interface PlatformDef {
  id: string;
  name: string;
  category: PlatformCategory;
  description: string;
}

export const ALL_PLATFORMS: PlatformDef[] = [
  {
    id: 'greenhouse',
    name: 'Greenhouse',
    category: 'monitored_ats',
    description: 'Direct public board JSON APIs with structured locations and departments.',
  },
  {
    id: 'lever',
    name: 'Lever',
    category: 'monitored_ats',
    description: 'Postings API covering workplace types, teams, and compensation blocks.',
  },
  {
    id: 'ashby',
    name: 'Ashby',
    category: 'monitored_ats',
    description: 'GraphQL and board JSON feeds with verified salary and workplace enums.',
  },
  {
    id: 'workable',
    name: 'Workable',
    category: 'monitored_ats',
    description: 'Company career widgets and job pages with explicit remote classifications.',
  },
  {
    id: 'recruitee',
    name: 'Recruitee',
    category: 'monitored_ats',
    description: 'Offers API with country codes, remote flags, and direct application links.',
  },
  {
    id: 'smartrecruiters',
    name: 'SmartRecruiters',
    category: 'monitored_ats',
    description: 'Public postings API indexed across mid-market and global tech teams.',
  },
  {
    id: 'teamtailor',
    name: 'Teamtailor',
    category: 'monitored_ats',
    description: 'Career sites and RSS/JSON-LD feeds across European and remote companies.',
  },
  {
    id: 'personio',
    name: 'Personio',
    category: 'monitored_ats',
    description: 'XML position feeds with verified office locations and employment types.',
  },
  {
    id: 'pinpointhq',
    name: 'Pinpoint',
    category: 'monitored_ats',
    description: 'Structured JSON career endpoints with compensation and remote labels.',
  },
  {
    id: 'workday',
    name: 'Workday',
    category: 'enterprise_ats',
    description: 'Enterprise tenant postings discovered on demand via web fallback.',
  },
  {
    id: 'jobberman',
    name: 'Jobberman (NG)',
    category: 'nigerian_board',
    description: 'Nigerian employer listings with verified company marks and external apply resolution.',
  },
  {
    id: 'myjobmag',
    name: 'MyJobMag (NG)',
    category: 'nigerian_board',
    description: 'Local career postings parsed for authentic descriptions and employer logos.',
  },
  {
    id: 'hotnigerianjobs',
    name: 'HotNigerianJobs (NG)',
    category: 'nigerian_board',
    description: 'Direct employer roundup and single-role feeds with corporate domain resolution.',
  },
];

export const NIGERIAN_PLATFORM_IDS = ['jobberman', 'myjobmag', 'hotnigerianjobs'] as const;

export const ROLE_SUGGESTIONS = [
  'Backend Engineer',
  'Full-Stack Developer',
  'Python / FastAPI',
  'Frontend React',
  'DevOps / SRE',
  'Data Engineer',
];

export const DEFAULT_PAGE_SIZE = 20;
