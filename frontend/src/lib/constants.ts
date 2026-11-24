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
    description: 'Direct company hiring boards with clear role locations and team details.',
  },
  {
    id: 'lever',
    name: 'Lever',
    category: 'monitored_ats',
    description: 'Company career pages with clear remote rules, teams, and compensation.',
  },
  {
    id: 'ashby',
    name: 'Ashby',
    category: 'monitored_ats',
    description: 'Fast-growing product and engineering teams with upfront salary ranges and work styles.',
  },
  {
    id: 'workable',
    name: 'Workable',
    category: 'monitored_ats',
    description: 'Direct company career portals with verified remote and hybrid classifications.',
  },
  {
    id: 'recruitee',
    name: 'Recruitee',
    category: 'monitored_ats',
    description: 'European and distributed teams with clear country eligibility and direct apply links.',
  },
  {
    id: 'smartrecruiters',
    name: 'SmartRecruiters',
    category: 'monitored_ats',
    description: 'Global hiring pages across mid-size and established technology companies.',
  },
  {
    id: 'teamtailor',
    name: 'Teamtailor',
    category: 'monitored_ats',
    description: 'Modern company career sites with clean role overviews and company marks.',
  },
  {
    id: 'personio',
    name: 'Personio',
    category: 'monitored_ats',
    description: 'European growth companies listing office hubs, flexibility, and contract types.',
  },
  {
    id: 'pinpointhq',
    name: 'Pinpoint',
    category: 'monitored_ats',
    description: 'Structured company job boards with salary bands and clear workplace labels.',
  },
  {
    id: 'workday',
    name: 'Workday',
    category: 'enterprise_ats',
    description: 'Large global enterprise career portals searched on demand when needed.',
  },
  {
    id: 'jobberman',
    name: 'Jobberman (NG)',
    category: 'nigerian_board',
    description: 'Verified Nigerian openings with employer marks and direct company application links.',
  },
  {
    id: 'myjobmag',
    name: 'MyJobMag (NG)',
    category: 'nigerian_board',
    description: 'Nigerian career listings cleaned up to keep full descriptions and verified company logos.',
  },
  {
    id: 'hotnigerianjobs',
    name: 'HotNigerianJobs (NG)',
    category: 'nigerian_board',
    description: 'Fresh local hiring roundups matched directly to verified employer domains.',
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
