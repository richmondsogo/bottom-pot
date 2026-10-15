export interface StructuredSalary {
  minimum?: number | null;
  maximum?: number | null;
  currency?: string | null;
  period?: string | null;
}

export type JobSalary = StructuredSalary | string | null;

export interface JobListing {
  id: string;
  title: string;
  company: string;
  company_slug?: string | null;
  location?: string | null;
  is_remote?: boolean | null;
  work_model?: 'remote' | 'hybrid' | 'in_person' | string | null;
  employment_type?: 'full_time' | 'part_time' | 'contract' | 'internship' | string | null;
  salary?: JobSalary;
  description?: string | null;
  requirements?: string | null;
  summary?: string | null;
  department?: string | null;
  posted_at?: string | null;
  scraped_at?: string | null;
  apply_url: string;
  source_url: string;
  provider: string;
  data_source: string;
  query_used?: string | null;
  ats_source?: string | null;
  confidence?: number | null;
}

export interface NormalizedJob extends JobListing {
  displayTitle: string;
  displayLocation: string;
  displaySalary: string;
  displayEmployment: string;
  displayLocationType: string;
  displayPostedDate: string;
}

export interface DoneMetrics {
  total: number;
  search_time_ms: number;
  serper_queries_used?: number;
  providers_searched: string[];
  providers_skipped?: string[];
  cached?: boolean;
}

export interface SearchParams {
  keywords: string;
  location: string;
  workModel: string;
  postAge: string;
  includeNigerian: boolean;
  deepScrape: boolean;
}
