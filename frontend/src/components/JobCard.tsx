import { useState } from 'react';
import { format } from 'date-fns';
import { Card, Flex, Box, Text, Heading, Badge, Button, Separator, Grid } from '@radix-ui/themes';
import {
  ExternalLink,
  MapPin,
  ChevronDown,
  ChevronUp,
  Building2,
  Code,
  Brain,
  Cloud,
} from 'lucide-react';
import type { Job } from '../api';

interface JobCardProps {
  job: Job;
  onSelect?: (job: Job) => void;
}

const sourceColors: Record<string, 'blue' | 'purple' | 'green' | 'orange' | 'pink'> = {
  linkedin: 'blue',
  indeed: 'purple',
  greenhouse: 'green',
  lever: 'orange',
  wellfound: 'pink',
};

export const JobCard = ({ job, onSelect }: JobCardProps) => {
  const [expanded, setExpanded] = useState(false);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Unknown';
    try {
      return format(new Date(dateStr), 'MMM d, yyyy');
    } catch {
      return 'Unknown';
    }
  };

  const hasAiMlSkills = job.ai_ml_keywords && job.ai_ml_keywords.length > 0;
  const hasRequiredSkills = job.required_skills && job.required_skills.length > 0;
  const hasTechSkills = job.technologies && job.technologies.length > 0;

  return (
    <Card size="3" style={{ cursor: 'pointer' }} onClick={() => onSelect?.(job)}>
      {/* Header */}
      <Flex justify="between" align="start" mb="3">
        <Box style={{ flex: 1 }}>
          <Flex gap="2" align="center" mb="2">
            {job.source && (
              <Badge size="1" color={sourceColors[job.source] || 'gray'}>
                {job.source}
              </Badge>
            )}
            <Badge size="1" variant="outline" color="gray">
              {formatDate(job.date_posted)}
            </Badge>
          </Flex>
          <Heading size="4" weight="bold" style={{ lineHeight: 1.3 }}>
            {job.title}
          </Heading>
        </Box>

        <Button size="2" asChild onClick={(e) => e.stopPropagation()}>
          <a href={job.apply_url || job.job_url} target="_blank" rel="noopener noreferrer">
            Apply <ExternalLink size={14} />
          </a>
        </Button>
      </Flex>

      {/* Company & Location */}
      <Flex gap="4" wrap="wrap" mb="4">
        <Flex gap="1" align="center">
          <Building2 size={14} style={{ color: 'var(--accent-11)' }} />
          <Text size="2" weight="medium">{job.company}</Text>
        </Flex>
        {job.location && (
          <Flex gap="1" align="center">
            <MapPin size={14} style={{ color: 'var(--gray-11)' }} />
            <Text size="2" color="gray">{job.location}</Text>
          </Flex>
        )}
        {job.salary_range && (
          <Text size="2" color="green" weight="medium">{job.salary_range}</Text>
        )}
      </Flex>

      {/* Skills Section - More Prominent */}
      <Box mb="4" p="3" style={{ background: 'var(--gray-a2)', borderRadius: 'var(--radius-3)' }}>
        <Grid columns={{ initial: '1', sm: '3' }} gap="3">
          {/* AI/ML Skills */}
          {hasAiMlSkills && (
            <Box>
              <Flex gap="1" align="center" mb="2">
                <Brain size={14} style={{ color: 'var(--purple-11)' }} />
                <Text size="1" weight="bold" color="purple">AI/ML</Text>
              </Flex>
              <Flex gap="1" wrap="wrap">
                {job.ai_ml_keywords?.map((skill) => (
                  <Badge key={skill} size="1" variant="soft" color="purple" radius="full">
                    {skill}
                  </Badge>
                ))}
              </Flex>
            </Box>
          )}

          {/* Programming Skills */}
          {hasRequiredSkills && (
            <Box>
              <Flex gap="1" align="center" mb="2">
                <Code size={14} style={{ color: 'var(--blue-11)' }} />
                <Text size="1" weight="bold" color="blue">Programming</Text>
              </Flex>
              <Flex gap="1" wrap="wrap">
                {job.required_skills?.map((skill) => (
                  <Badge key={skill} size="1" variant="soft" color="blue" radius="full">
                    {skill}
                  </Badge>
                ))}
              </Flex>
            </Box>
          )}

          {/* Cloud/DevOps Skills */}
          {hasTechSkills && (
            <Box>
              <Flex gap="1" align="center" mb="2">
                <Cloud size={14} style={{ color: 'var(--orange-11)' }} />
                <Text size="1" weight="bold" color="orange">Cloud/DevOps</Text>
              </Flex>
              <Flex gap="1" wrap="wrap">
                {job.technologies?.map((skill) => (
                  <Badge key={skill} size="1" variant="soft" color="orange" radius="full">
                    {skill}
                  </Badge>
                ))}
              </Flex>
            </Box>
          )}
        </Grid>
      </Box>

      {/* Expand Button */}
      <Button
        variant="soft"
        size="2"
        color="gray"
        onClick={(e) => {
          e.stopPropagation();
          setExpanded(!expanded);
        }}
        style={{ cursor: 'pointer', width: '100%' }}
      >
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        {expanded ? 'Hide Job Description' : 'View Full Job Description'}
      </Button>

      {/* Expandable Details */}
      {expanded && (
        <Box mt="4">
          <Separator size="4" mb="4" />

          {/* Job Description */}
          {job.raw_description && (
            <Box
              p="4"
              style={{
                background: 'var(--gray-a2)',
                borderRadius: 'var(--radius-3)',
                maxHeight: '500px',
                overflow: 'auto',
              }}
            >
              <Text size="2" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {job.raw_description}
              </Text>
            </Box>
          )}

          {/* Parsed Sections */}
          {(job.about_role || job.responsibilities || job.qualifications) && (
            <Flex direction="column" gap="4" mt="4">
              {job.about_role && (
                <Box>
                  <Text size="2" weight="bold" color="blue" mb="2" as="p">About the Role</Text>
                  <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>{job.about_role}</Text>
                </Box>
              )}

              {job.responsibilities && (
                <Box>
                  <Text size="2" weight="bold" color="blue" mb="2" as="p">Responsibilities</Text>
                  <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>{job.responsibilities}</Text>
                </Box>
              )}

              {job.qualifications && (
                <Box>
                  <Text size="2" weight="bold" color="green" mb="2" as="p">Qualifications</Text>
                  <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>{job.qualifications}</Text>
                </Box>
              )}

              {job.nice_to_have && (
                <Box>
                  <Text size="2" weight="bold" color="purple" mb="2" as="p">Nice to Have</Text>
                  <Text size="2" color="gray" style={{ whiteSpace: 'pre-wrap' }}>{job.nice_to_have}</Text>
                </Box>
              )}
            </Flex>
          )}
        </Box>
      )}
    </Card>
  );
};

export default JobCard;
