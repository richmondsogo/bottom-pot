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
    description: 'Company hiring boards with clear locations and team details.',
  },
  {
    id: 'lever',
    name: 'Lever',
    category: 'monitored_ats',
    description: 'Company career pages with work style rules, teams, and compensation.',
  },
  {
    id: 'ashby',
    name: 'Ashby',
    category: 'monitored_ats',
    description: 'Growing product and engineering teams listing upfront salary ranges.',
  },
  {
    id: 'workable',
    name: 'Workable',
    category: 'monitored_ats',
    description: 'Company career sites with clear remote, hybrid, and in-person roles.',
  },
  {
    id: 'recruitee',
    name: 'Recruitee',
    category: 'monitored_ats',
    description: 'European and distributed teams with clear country eligibility.',
  },
  {
    id: 'smartrecruiters',
    name: 'SmartRecruiters',
    category: 'monitored_ats',
    description: 'Global hiring pages across mid-size and established technology teams.',
  },
  {
    id: 'teamtailor',
    name: 'Teamtailor',
    category: 'monitored_ats',
    description: 'Company career pages with structured role summaries and employer logos.',
  },
  {
    id: 'personio',
    name: 'Personio',
    category: 'monitored_ats',
    description: 'European companies listing office hubs, flexibility, and contract terms.',
  },
  {
    id: 'pinpointhq',
    name: 'Pinpoint',
    category: 'monitored_ats',
    description: 'Structured employer boards with pay bands and workplace labels.',
  },
  {
    id: 'workday',
    name: 'Workday',
    category: 'enterprise_ats',
    description: 'Large enterprise career portals checked live when needed.',
  },
  {
    id: 'jobberman',
    name: 'Jobberman (NG)',
    category: 'nigerian_board',
    description: 'Nigerian roles with company logos and direct employer application links.',
  },
  {
    id: 'myjobmag',
    name: 'MyJobMag (NG)',
    category: 'nigerian_board',
    description: 'Nigerian listings cleaned up with full descriptions and company logos.',
  },
  {
    id: 'hotnigerianjobs',
    name: 'HotNigerianJobs (NG)',
    category: 'nigerian_board',
    description: 'Fresh Nigerian hiring roundups matched to employer domains.',
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
