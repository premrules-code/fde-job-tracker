import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string | null;
  job_url: string;
  apply_url: string | null;
  source: string | null;
  date_posted: string | null;
  date_scraped: string | null;
  raw_description: string | null;
  responsibilities: string | null;
  qualifications: string | null;
  nice_to_have: string | null;
  about_role: string | null;
  about_company: string | null;
  required_skills: string[] | null;
  bonus_skills: string[] | null;
  technologies: string[] | null;
  ai_ml_keywords: string[] | null;
  salary_range: string | null;
  employment_type: string | null;
  remote_status: string | null;
  relevance_score: number | null;
}

export interface SkillFrequency {
  skill: string;
  category: string;
  frequency: number;
}

export interface HeatmapData {
  category: string;
  skills: { skill: string; frequency: number }[];
}

export interface DailySummary {
  date: string;
  total_jobs: number;
  new_jobs: number;
  jobs_by_source: Record<string, number>;
  jobs_by_company: Record<string, number>;
  top_skills: { skill: string; count: number }[];
}

export interface CompanyCount {
  company: string;
  count: number;
}

export interface SourceCount {
  source: string;
  count: number;
}

// API functions
export async function getJobs(params?: {
  search?: string;
  source?: string;
  company?: string;
  days?: number;
  min_relevance?: number;
  limit?: number;
  offset?: number;
}): Promise<Job[]> {
  const { data } = await api.get('/jobs', { params });
  return data;
}

export async function getJob(id: number): Promise<Job> {
  const { data } = await api.get(`/jobs/${id}`);
  return data;
}

export async function searchJobs(query: string, limit = 50): Promise<Job[]> {
  const { data } = await api.get('/search', { params: { q: query, limit } });
  return data;
}

export async function getSkillFrequencies(category?: string, limit = 50): Promise<SkillFrequency[]> {
  const { data } = await api.get('/skills/frequencies', { params: { category, limit } });
  return data;
}

export async function getSkillsHeatmap(): Promise<HeatmapData[]> {
  const { data } = await api.get('/skills/heatmap');
  return data;
}

export async function getDailySummary(days = 7): Promise<DailySummary[]> {
  const { data } = await api.get('/summary/daily', { params: { days } });
  return data;
}

export async function getCompanies(): Promise<CompanyCount[]> {
  const { data } = await api.get('/companies');
  return data;
}

export async function getSources(): Promise<SourceCount[]> {
  const { data } = await api.get('/sources');
  return data;
}

export async function triggerScrape(days = 30): Promise<{ status: string; message: string }> {
  const { data } = await api.post('/scrape', null, { params: { days } });
  return data;
}

export async function getScrapeStatus(): Promise<any[]> {
  const { data } = await api.get('/scrape/status');
  return data;
}

export interface ScrapeProgress {
  status: 'idle' | 'running' | 'completed' | 'failed';
  step: string;
  progress: number;
  total: number;
  jobs_found: number;
  jobs_added: number;
  current_job: string;
}

export async function getScrapeProgress(): Promise<ScrapeProgress> {
  const { data } = await api.get('/scrape/progress');
  return data;
}

// RSS Feed Scraping
export interface RSSFeed {
  url: string;
  source: string;
  name: string;
}

export interface RSSFeedsResponse {
  rss_app_feeds: RSSFeed[];
  custom_feeds: string[];
}

export async function getRSSFeeds(): Promise<RSSFeedsResponse> {
  const { data } = await api.get('/rss/feeds');
  return data;
}

export async function addRSSFeed(feedUrl: string, sourceName = 'linkedin_rss'): Promise<{ status: string; message: string }> {
  const { data } = await api.post('/rss/feeds', { feed_url: feedUrl, source_name: sourceName });
  return data;
}

export async function triggerRSSScrape(days = 30, location = 'San Francisco'): Promise<{ status: string; message: string }> {
  const { data } = await api.post('/rss/scrape', null, { params: { days, location } });
  return data;
}
