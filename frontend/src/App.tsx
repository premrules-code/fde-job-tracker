import { useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { Box, Flex, Heading, Text, Button, TextField, Tabs, Container, Badge, Spinner } from '@radix-ui/themes';
import {
  Search,
  RefreshCw,
  Briefcase,
  BarChart3,
  Calendar,
  Command,
} from 'lucide-react';
import {
  getJobs,
  getSkillsHeatmap,
  getDailySummary,
  getCompanies,
  getSources,
  triggerScrape,
  type Job,
} from './api';
import { JobCard } from './components/JobCard';
import { SkillHeatmap } from './components/SkillHeatmap';
import { DailySummary } from './components/DailySummary';
import { CommandPalette } from './components/CommandPalette';
import { Filters } from './components/Filters';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
    },
  },
});

type Tab = 'jobs' | 'heatmap' | 'summary';

function AppContent() {
  const [activeTab, setActiveTab] = useState<Tab>('jobs');
  const [commandOpen, setCommandOpen] = useState(false);
  const [, setSelectedJob] = useState<Job | null>(null);
  const [scraping, setScraping] = useState(false);

  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [daysFilter, setDaysFilter] = useState(30);
  const [searchQuery, setSearchQuery] = useState('');

  const jobsQuery = useQuery({
    queryKey: ['jobs', selectedSource, selectedCompany, daysFilter, searchQuery],
    queryFn: () =>
      getJobs({
        source: selectedSource || undefined,
        company: selectedCompany || undefined,
        days: daysFilter,
        search: searchQuery || undefined,
        limit: 100,
      }),
  });

  const heatmapQuery = useQuery({
    queryKey: ['heatmap'],
    queryFn: getSkillsHeatmap,
  });

  const summaryQuery = useQuery({
    queryKey: ['summary'],
    queryFn: () => getDailySummary(7),
  });

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: getCompanies,
  });

  const sourcesQuery = useQuery({
    queryKey: ['sources'],
    queryFn: getSources,
  });

  const handleScrape = async () => {
    setScraping(true);
    try {
      await triggerScrape(30);
      setTimeout(() => {
        queryClient.invalidateQueries();
      }, 5000);
    } catch (error) {
      console.error('Scrape failed:', error);
    } finally {
      setScraping(false);
    }
  };

  const handleSkillClick = (skill: string) => {
    setSearchQuery(skill);
    setActiveTab('jobs');
  };

  const handleCompanyClick = (company: string) => {
    setSelectedCompany(company);
    setActiveTab('jobs');
  };

  const handleJobSelect = (job: Job) => {
    setSelectedJob(job);
  };

  const jobs = jobsQuery.data || [];
  const heatmapData = heatmapQuery.data || [];
  const summaries = summaryQuery.data || [];
  const companies = companiesQuery.data || [];
  const sources = sourcesQuery.data || [];

  return (
    <Box style={{ minHeight: '100vh', background: 'var(--color-background)' }}>
      {/* Header */}
      <Box
        position="sticky"
        top="0"
        style={{
          zIndex: 40,
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--gray-a6)',
          background: 'var(--color-panel-translucent)',
        }}
      >
        <Container size="4" py="4">
          <Flex justify="between" align="center">
            <Flex gap="3" align="center">
              <Box
                p="2"
                style={{
                  background: 'var(--accent-a3)',
                  borderRadius: 'var(--radius-3)',
                }}
              >
                <Briefcase size={24} style={{ color: 'var(--accent-11)' }} />
              </Box>
              <Box>
                <Heading size="5" weight="bold">FDE Job Tracker</Heading>
                <Text size="2" color="gray">Forward Deployed Engineer Opportunities</Text>
              </Box>
            </Flex>

            <Flex gap="3" align="center">
              <Button
                variant="soft"
                color="gray"
                onClick={() => setCommandOpen(true)}
                style={{ cursor: 'pointer' }}
              >
                <Search size={16} />
                <Text size="2" className="hidden sm:inline">Search jobs...</Text>
                <Flex
                  gap="1"
                  align="center"
                  px="1"
                  style={{
                    background: 'var(--gray-a4)',
                    borderRadius: 'var(--radius-2)',
                    fontSize: '11px',
                  }}
                  className="hidden sm:flex"
                >
                  <Command size={10} />K
                </Flex>
              </Button>

              <Button onClick={handleScrape} disabled={scraping} style={{ cursor: 'pointer' }}>
                <RefreshCw size={16} className={scraping ? 'animate-spin' : ''} />
                {scraping ? 'Scraping...' : 'Scrape Jobs'}
              </Button>
            </Flex>
          </Flex>

          {/* Tabs */}
          <Tabs.Root value={activeTab} onValueChange={(v) => setActiveTab(v as Tab)}>
            <Tabs.List mt="4">
              <Tabs.Trigger value="jobs" style={{ cursor: 'pointer' }}>
                <Flex gap="2" align="center">
                  <Briefcase size={16} />
                  Jobs
                  <Badge size="1" variant="soft">{jobs.length}</Badge>
                </Flex>
              </Tabs.Trigger>
              <Tabs.Trigger value="heatmap" style={{ cursor: 'pointer' }}>
                <Flex gap="2" align="center">
                  <BarChart3 size={16} />
                  Skills Heatmap
                </Flex>
              </Tabs.Trigger>
              <Tabs.Trigger value="summary" style={{ cursor: 'pointer' }}>
                <Flex gap="2" align="center">
                  <Calendar size={16} />
                  Daily Summary
                </Flex>
              </Tabs.Trigger>
            </Tabs.List>
          </Tabs.Root>
        </Container>
      </Box>

      {/* Main Content */}
      <Container size="4" py="6">
        {activeTab === 'jobs' && (
          <Flex gap="6">
            {/* Sidebar Filters */}
            <Box style={{ width: '280px', flexShrink: 0 }} className="hidden lg:block">
              <Filters
                sources={sources}
                companies={companies}
                selectedSource={selectedSource}
                selectedCompany={selectedCompany}
                daysFilter={daysFilter}
                onSourceChange={setSelectedSource}
                onCompanyChange={setSelectedCompany}
                onDaysChange={setDaysFilter}
              />

              <Box mt="4">
                <TextField.Root
                  placeholder="Filter results..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  size="2"
                >
                  <TextField.Slot>
                    <Search size={14} />
                  </TextField.Slot>
                </TextField.Root>
              </Box>
            </Box>

            {/* Job List */}
            <Box style={{ flex: 1, minWidth: 0 }}>
              <Flex direction="column" gap="4">
                {jobsQuery.isLoading && (
                  <Flex justify="center" py="9">
                    <Spinner size="3" />
                  </Flex>
                )}

                {jobsQuery.isError && (
                  <Box py="9" style={{ textAlign: 'center' }}>
                    <Text color="red" size="3">Error loading jobs. Is the backend running?</Text>
                  </Box>
                )}

                {!jobsQuery.isLoading && jobs.length === 0 && (
                  <Flex direction="column" align="center" py="9" gap="3">
                    <Briefcase size={48} style={{ opacity: 0.3 }} />
                    <Text size="4" color="gray">No jobs found</Text>
                    <Text size="2" color="gray">
                      Try adjusting your filters or run a scrape to fetch new jobs
                    </Text>
                  </Flex>
                )}

                {jobs.map((job) => (
                  <JobCard key={job.id} job={job} onSelect={handleJobSelect} />
                ))}
              </Flex>
            </Box>
          </Flex>
        )}

        {activeTab === 'heatmap' && (
          <SkillHeatmap data={heatmapData} onSkillClick={handleSkillClick} />
        )}

        {activeTab === 'summary' && (
          <DailySummary summaries={summaries} onCompanyClick={handleCompanyClick} />
        )}
      </Container>

      {/* Command Palette */}
      <CommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        onSelectJob={handleJobSelect}
      />
    </Box>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
