import { Card, Flex, Box, Text, Button, Select, Heading } from '@radix-ui/themes';
import { Filter, X } from 'lucide-react';

interface FiltersProps {
  sources: { source: string; count: number }[];
  companies: { company: string; count: number }[];
  selectedSource: string | null;
  selectedCompany: string | null;
  daysFilter: number;
  onSourceChange: (source: string | null) => void;
  onCompanyChange: (company: string | null) => void;
  onDaysChange: (days: number) => void;
}

export const Filters = ({
  sources,
  companies,
  selectedSource,
  selectedCompany,
  daysFilter,
  onSourceChange,
  onCompanyChange,
  onDaysChange,
}: FiltersProps) => {
  const hasActiveFilters = selectedSource || selectedCompany || daysFilter !== 30;

  return (
    <Card size="2">
      <Flex justify="between" align="center" mb="4">
        <Flex gap="2" align="center">
          <Filter size={18} />
          <Heading size="3">Filters</Heading>
        </Flex>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="1"
            color="gray"
            onClick={() => {
              onSourceChange(null);
              onCompanyChange(null);
              onDaysChange(30);
            }}
            style={{ cursor: 'pointer' }}
          >
            <X size={14} />
            Clear all
          </Button>
        )}
      </Flex>

      {/* Days Filter */}
      <Box mb="4">
        <Text size="2" weight="medium" color="gray" mb="2" as="p">
          Posted within
        </Text>
        <Flex gap="2" wrap="wrap">
          {[7, 14, 30, 60].map((days) => (
            <Button
              key={days}
              variant={daysFilter === days ? 'solid' : 'soft'}
              color={daysFilter === days ? 'blue' : 'gray'}
              size="1"
              onClick={() => onDaysChange(days)}
              style={{ cursor: 'pointer' }}
            >
              {days} days
            </Button>
          ))}
        </Flex>
      </Box>

      {/* Source Filter */}
      <Box mb="4">
        <Text size="2" weight="medium" color="gray" mb="2" as="p">
          Source
        </Text>
        <Flex gap="2" wrap="wrap">
          <Button
            variant={!selectedSource ? 'solid' : 'soft'}
            color={!selectedSource ? 'blue' : 'gray'}
            size="1"
            onClick={() => onSourceChange(null)}
            style={{ cursor: 'pointer' }}
          >
            All
          </Button>
          {sources.map(({ source, count }) => (
            <Button
              key={source}
              variant={selectedSource === source ? 'solid' : 'soft'}
              color={selectedSource === source ? 'blue' : 'gray'}
              size="1"
              onClick={() => onSourceChange(source)}
              style={{ cursor: 'pointer' }}
            >
              {source} ({count})
            </Button>
          ))}
        </Flex>
      </Box>

      {/* Company Filter */}
      <Box>
        <Text size="2" weight="medium" color="gray" mb="2" as="p">
          Company
        </Text>
        <Select.Root
          value={selectedCompany || 'all'}
          onValueChange={(value) => onCompanyChange(value === 'all' ? null : value)}
        >
          <Select.Trigger style={{ width: '100%' }} />
          <Select.Content>
            <Select.Item value="all">All Companies</Select.Item>
            {companies.slice(0, 20).map(({ company, count }) => (
              <Select.Item key={company} value={company}>
                {company} ({count})
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Box>
    </Card>
  );
};

export default Filters;
