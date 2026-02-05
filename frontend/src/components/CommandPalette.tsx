import { useEffect, useState, useCallback } from 'react';
import { Command } from 'cmdk';
import { Box, Flex, Text, Kbd } from '@radix-ui/themes';
import { Search, Building2, Briefcase, MapPin, ExternalLink } from 'lucide-react';
import { searchJobs, type Job } from '../api';
import { useDebounce } from '../hooks/useDebounce';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectJob: (job: Job) => void;
}

export const CommandPalette = ({
  open,
  onOpenChange,
  onSelectJob,
}: CommandPaletteProps) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);

  const debouncedQuery = useDebounce(query, 300);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const jobs = await searchJobs(searchQuery, 20);
      setResults(jobs);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    performSearch(debouncedQuery);
  }, [debouncedQuery, performSearch]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === 'Escape') {
        onOpenChange(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <Box
      position="fixed"
      inset="0"
      style={{
        zIndex: 50,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '20vh',
      }}
    >
      {/* Backdrop */}
      <Box
        position="absolute"
        inset="0"
        onClick={() => onOpenChange(false)}
        style={{
          background: 'rgba(0, 0, 0, 0.6)',
          backdropFilter: 'blur(4px)',
        }}
      />

      {/* Command Dialog */}
      <Command
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '640px',
          margin: '0 16px',
          background: 'var(--color-panel-solid)',
          borderRadius: 'var(--radius-4)',
          border: '1px solid var(--gray-a6)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
        shouldFilter={false}
      >
        <Flex
          align="center"
          px="4"
          style={{
            borderBottom: '1px solid var(--gray-a6)',
          }}
        >
          <Search size={20} style={{ color: 'var(--gray-11)', flexShrink: 0 }} />
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder="Search jobs by title, company, skills, or description..."
            autoFocus
            style={{
              flex: 1,
              padding: '16px 12px',
              fontSize: '16px',
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--gray-12)',
            }}
          />
          <Kbd size="2">ESC</Kbd>
        </Flex>

        <Command.List
          style={{
            maxHeight: '400px',
            overflow: 'auto',
            padding: '8px',
          }}
        >
          {loading && (
            <Command.Loading>
              <Box p="4" style={{ textAlign: 'center' }}>
                <Text color="gray">Searching...</Text>
              </Box>
            </Command.Loading>
          )}

          {!loading && query && results.length === 0 && (
            <Command.Empty>
              <Box p="4" style={{ textAlign: 'center' }}>
                <Text color="gray">No jobs found for "{query}"</Text>
              </Box>
            </Command.Empty>
          )}

          {!loading && results.length > 0 && (
            <Command.Group
              heading={
                <Text size="1" color="gray" weight="medium" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {results.length} results
                </Text>
              }
            >
              {results.map((job) => (
                <Command.Item
                  key={job.id}
                  value={`${job.title}-${job.company}-${job.id}`}
                  onSelect={() => {
                    onSelectJob(job);
                    onOpenChange(false);
                    setQuery('');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px',
                    borderRadius: 'var(--radius-2)',
                    cursor: 'pointer',
                  }}
                >
                  <Box style={{ flex: 1, minWidth: 0 }}>
                    <Flex gap="2" align="center">
                      <Briefcase size={14} style={{ color: 'var(--accent-11)', flexShrink: 0 }} />
                      <Text size="2" weight="medium" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {job.title}
                      </Text>
                    </Flex>
                    <Flex gap="3" mt="1" align="center">
                      <Flex gap="1" align="center">
                        <Building2 size={12} style={{ color: 'var(--gray-11)' }} />
                        <Text size="1" color="gray">{job.company}</Text>
                      </Flex>
                      {job.location && (
                        <Flex gap="1" align="center">
                          <MapPin size={12} style={{ color: 'var(--gray-11)' }} />
                          <Text size="1" color="gray">{job.location}</Text>
                        </Flex>
                      )}
                    </Flex>
                  </Box>
                  <ExternalLink size={14} style={{ color: 'var(--gray-9)', flexShrink: 0 }} />
                </Command.Item>
              ))}
            </Command.Group>
          )}

          {!query && (
            <Box p="4" style={{ textAlign: 'center' }}>
              <Text size="2" color="gray" as="p">Start typing to search across all job postings</Text>
              <Text size="1" color="gray" mt="2" as="p">
                Search by job title, company name, skills, technologies, or any text in the job description
              </Text>
            </Box>
          )}
        </Command.List>

        {/* Quick actions footer */}
        <Flex
          justify="between"
          align="center"
          px="4"
          py="2"
          style={{
            borderTop: '1px solid var(--gray-a6)',
          }}
        >
          <Flex gap="4" align="center">
            <Text size="1" color="gray">Navigate</Text>
            <Text size="1" color="gray">Select</Text>
            <Text size="1" color="gray">ESC Close</Text>
          </Flex>
          <Flex gap="1" align="center">
            <Kbd size="1">K</Kbd>
            <Text size="1" color="gray">to toggle</Text>
          </Flex>
        </Flex>
      </Command>
    </Box>
  );
};

export default CommandPalette;
