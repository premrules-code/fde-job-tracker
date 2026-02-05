import { Flex, Box, Text } from '@radix-ui/themes';
import { Flame } from 'lucide-react';
import type { HeatmapData } from '../api';

interface SkillHeatmapProps {
  data: HeatmapData[];
  onSkillClick?: (skill: string) => void;
}

// Category colors matching the reference design
const categoryColors: Record<string, { bg: string; text: string; label: string }> = {
  ai: { bg: '#a78bfa', text: '#a78bfa', label: 'AI & LLMs' },
  ml: { bg: '#60a5fa', text: '#60a5fa', label: 'Machine Learning' },
  backend: { bg: '#f472b6', text: '#f472b6', label: 'Backend' },
  frontend: { bg: '#4ade80', text: '#4ade80', label: 'Frontend' },
  cloud: { bg: '#2dd4bf', text: '#2dd4bf', label: 'Cloud & DevOps' },
  data: { bg: '#fbbf24', text: '#fbbf24', label: 'Data & ETL' },
  fde: { bg: '#fb923c', text: '#fb923c', label: 'FDE / Field' },
  industry: { bg: '#94a3b8', text: '#94a3b8', label: 'Industry' },
};

interface FlatSkill {
  skill: string;
  frequency: number;
  category: string;
}

export const SkillHeatmap = ({ data, onSkillClick }: SkillHeatmapProps) => {
  // Flatten all skills into a single sorted array
  const allSkills: FlatSkill[] = data
    .flatMap((cat) =>
      (cat.skills || []).map((s) => ({
        skill: s.skill,
        frequency: s.frequency,
        category: cat.category,
      }))
    )
    .sort((a, b) => b.frequency - a.frequency);

  const maxFrequency = Math.max(...allSkills.map((s) => s.frequency), 1);

  if (allSkills.length === 0) {
    return (
      <Flex direction="column" align="center" py="9" gap="3">
        <Flame size={48} style={{ opacity: 0.3 }} />
        <Text size="4" color="gray">No skills data available</Text>
        <Text size="2" color="gray">Skills will appear after scraping jobs</Text>
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap="4">
      {/* Skills List */}
      <Flex direction="column" gap="1">
        {allSkills.map(({ skill, frequency, category }) => {
          const colors = categoryColors[category] || { bg: '#9ca3af', text: '#9ca3af', label: 'Other' };
          const barWidth = (frequency / maxFrequency) * 100;

          return (
            <Flex
              key={`${category}-${skill}`}
              align="center"
              gap="3"
              py="1"
              style={{ cursor: 'pointer' }}
              onClick={() => onSkillClick?.(skill)}
            >
              {/* Skill Name */}
              <Text
                size="2"
                style={{
                  width: '220px',
                  textAlign: 'right',
                  color: 'var(--gray-11)',
                  flexShrink: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {skill}
              </Text>

              {/* Bar Container */}
              <Box style={{ flex: 1, position: 'relative', height: '20px' }}>
                {/* Bar */}
                <Box
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: '2px',
                    height: '16px',
                    width: `${Math.max(barWidth, 3)}%`,
                    background: `linear-gradient(90deg, ${colors.bg}dd, ${colors.bg}99)`,
                    borderRadius: '2px',
                    transition: 'width 0.3s ease',
                  }}
                />
              </Box>

              {/* Frequency Count */}
              <Text
                size="2"
                weight="medium"
                style={{
                  width: '30px',
                  textAlign: 'right',
                  color: colors.text,
                  flexShrink: 0,
                }}
              >
                {frequency}
              </Text>
            </Flex>
          );
        })}
      </Flex>

      {/* Legend */}
      <Flex
        gap="4"
        wrap="wrap"
        justify="center"
        pt="4"
        style={{ borderTop: '1px solid var(--gray-a5)' }}
      >
        {Object.entries(categoryColors).map(([key, value]) => (
          <Flex key={key} align="center" gap="2">
            <Box
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '2px',
                background: value.bg,
              }}
            />
            <Text size="1" color="gray">
              {value.label}
            </Text>
          </Flex>
        ))}
      </Flex>
    </Flex>
  );
};

export default SkillHeatmap;
