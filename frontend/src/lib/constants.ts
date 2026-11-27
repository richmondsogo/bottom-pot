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
    description: 'Employer career pages and job listings hosted on Greenhouse.',
  },
  {
    id: 'lever',
    name: 'Lever',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Lever.',
  },
  {
    id: 'ashby',
    name: 'Ashby',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Ashby.',
  },
  {
    id: 'workable',
    name: 'Workable',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Workable.',
  },
  {
    id: 'recruitee',
    name: 'Recruitee',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Recruitee.',
  },
  {
    id: 'smartrecruiters',
    name: 'SmartRecruiters',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on SmartRecruiters.',
  },
  {
    id: 'teamtailor',
    name: 'Teamtailor',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Teamtailor.',
  },
  {
    id: 'personio',
    name: 'Personio',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Personio.',
  },
  {
    id: 'pinpointhq',
    name: 'Pinpoint',
    category: 'monitored_ats',
    description: 'Employer career pages and job listings hosted on Pinpoint.',
  },
  {
    id: 'workday',
    name: 'Workday',
    category: 'enterprise_ats',
    description: 'Enterprise career pages searched when broader coverage is needed.',
  },
  {
    id: 'jobberman',
    name: 'Jobberman',
    category: 'nigerian_board',
    description: 'Selected job listings from Jobberman.',
  },
  {
    id: 'myjobmag',
    name: 'MyJobMag',
    category: 'nigerian_board',
    description: 'Selected job listings from MyJobMag.',
  },
  {
    id: 'hotnigerianjobs',
    name: 'HotNigerianJobs',
    category: 'nigerian_board',
    description: 'Selected job listings from HotNigerianJobs.',
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
