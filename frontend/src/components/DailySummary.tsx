import { format } from 'date-fns';
import { Card, Flex, Box, Text, Heading, Badge, Grid, Separator } from '@radix-ui/themes';
import { TrendingUp, Building2 } from 'lucide-react';
import type { DailySummary as DailySummaryType } from '../api';

interface DailySummaryProps {
  summaries: DailySummaryType[];
  onCompanyClick?: (company: string) => void;
}

export const DailySummary = ({ summaries, onCompanyClick }: DailySummaryProps) => {
  return (
    <Flex direction="column" gap="4">
      <Flex justify="between" align="center">
        <Heading size="5">Daily Summary</Heading>
        <Text size="2" color="gray">Last {summaries.length} days</Text>
      </Flex>

      <Grid columns={{ initial: '1', md: '2', lg: '3' }} gap="4">
        {summaries.map((summary) => {
          const dateStr = format(new Date(summary.date), 'EEE, MMM d');
          const isToday = summary.date === format(new Date(), 'yyyy-MM-dd');

          return (
            <Card
              key={summary.date}
              size="2"
              style={{
                border: isToday ? '1px solid var(--accent-8)' : undefined,
              }}
            >
              <Flex justify="between" align="center" mb="3">
                <Heading size="3">
                  {isToday ? 'Today' : dateStr}
                </Heading>
                <Flex gap="1" align="center">
                  <TrendingUp size={14} style={{ color: 'var(--green-9)' }} />
                  <Text size="2" weight="medium" color="green">+{summary.new_jobs}</Text>
                </Flex>
              </Flex>

              {/* Jobs by Company */}
              <Box mb="4">
                <Text size="1" weight="medium" color="gray" mb="2" as="p" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Companies Hiring
                </Text>
                <Flex gap="2" wrap="wrap">
                  {Object.entries(summary.jobs_by_company)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 5)
                    .map(([company, count]) => (
                      <Badge
                        key={company}
                        size="1"
                        variant="soft"
                        color="gray"
                        style={{ cursor: 'pointer' }}
                        onClick={() => onCompanyClick?.(company)}
                      >
                        <Building2 size={10} />
                        {company}
                        <Text size="1" color="gray">({count})</Text>
                      </Badge>
                    ))}
                </Flex>
              </Box>

              {/* Top Skills */}
              <Box mb="3">
                <Text size="1" weight="medium" color="gray" mb="2" as="p" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Top Skills
                </Text>
                <Flex gap="2" wrap="wrap">
                  {summary.top_skills.slice(0, 6).map(({ skill, count }) => (
                    <Badge key={skill} size="1" variant="soft" color="purple">
                      {skill} ({count})
                    </Badge>
                  ))}
                </Flex>
              </Box>

              {/* Sources */}
              <Separator size="4" mb="3" />
              <Flex gap="3" wrap="wrap">
                {Object.entries(summary.jobs_by_source).map(([source, count]) => (
                  <Flex key={source} gap="1" align="center">
                    <Box
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: 'var(--accent-9)',
                      }}
                    />
                    <Text size="1" color="gray">{source}: {count}</Text>
                  </Flex>
                ))}
              </Flex>
            </Card>
          );
        })}
      </Grid>

      {summaries.length === 0 && (
        <Box py="8" style={{ textAlign: 'center' }}>
          <Text size="3" color="gray">
            No summary data available yet. Run a scrape to populate data.
          </Text>
        </Box>
      )}
    </Flex>
  );
};

export default DailySummary;
