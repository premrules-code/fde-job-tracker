import { Flex, Box, Text, Heading, Badge, Card } from '@radix-ui/themes';
import { Flame, Code, Brain, Cloud, Users, Building2, Database } from 'lucide-react';
import type { HeatmapData } from '../api';

interface SkillHeatmapProps {
  data: HeatmapData[];
  onSkillClick?: (skill: string) => void;
}

// Map categories to display names and icons
const categoryConfig: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  ai: { label: 'AI & LLMs', icon: <Brain size={18} />, color: '#a78bfa' },
  ml: { label: 'Machine Learning', icon: <Brain size={18} />, color: '#60a5fa' },
  backend: { label: 'Backend & Languages', icon: <Code size={18} />, color: '#f472b6' },
  frontend: { label: 'Frontend', icon: <Code size={18} />, color: '#4ade80' },
  cloud: { label: 'Cloud & DevOps', icon: <Cloud size={18} />, color: '#2dd4bf' },
  data: { label: 'Data & ETL', icon: <Database size={18} />, color: '#fbbf24' },
  fde: { label: 'FDE / Field Skills', icon: <Users size={18} />, color: '#fb923c' },
  industry: { label: 'Industry Domains', icon: <Building2 size={18} />, color: '#94a3b8' },
};

// Group categories for display
const skillGroups = {
  'Required Skills': ['backend', 'frontend', 'cloud', 'data'],
  'AI/ML Skills': ['ai', 'ml'],
  'FDE & Soft Skills': ['fde'],
  'Industry Experience': ['industry'],
};

export const SkillHeatmap = ({ data, onSkillClick }: SkillHeatmapProps) => {
  if (!data || data.length === 0) {
    return (
      <Flex direction="column" align="center" py="9" gap="3">
        <Flame size={48} style={{ opacity: 0.3 }} />
        <Text size="4" color="gray">No skills data available</Text>
        <Text size="2" color="gray">Skills will appear after scraping jobs</Text>
      </Flex>
    );
  }

  // Get skills by category
  const getSkillsByCategories = (categories: string[]) => {
    return data
      .filter((cat) => categories.includes(cat.category))
      .flatMap((cat) =>
        (cat.skills || []).map((s) => ({
          skill: s.skill,
          frequency: s.frequency,
          category: cat.category,
        }))
      )
      .sort((a, b) => b.frequency - a.frequency);
  };

  return (
    <Flex direction="column" gap="6">
      {Object.entries(skillGroups).map(([groupName, categories]) => {
        const skills = getSkillsByCategories(categories);
        if (skills.length === 0) return null;

        return (
          <Card key={groupName} size="3">
            <Heading size="4" mb="4">{groupName}</Heading>
            <Flex gap="2" wrap="wrap">
              {skills.map(({ skill, frequency, category }) => {
                const config = categoryConfig[category] || { color: '#9ca3af' };
                return (
                  <Badge
                    key={`${category}-${skill}`}
                    size="2"
                    style={{
                      cursor: 'pointer',
                      background: `${config.color}22`,
                      color: config.color,
                      border: `1px solid ${config.color}44`,
                    }}
                    onClick={() => onSkillClick?.(skill)}
                  >
                    {skill}
                    {frequency > 1 && (
                      <Text size="1" style={{ opacity: 0.7, marginLeft: '4px' }}>
                        ×{frequency}
                      </Text>
                    )}
                  </Badge>
                );
              })}
            </Flex>
          </Card>
        );
      })}

      {/* Legend */}
      <Card size="2">
        <Text size="2" weight="medium" color="gray" mb="3">Categories</Text>
        <Flex gap="4" wrap="wrap">
          {Object.entries(categoryConfig).map(([key, value]) => (
            <Flex key={key} align="center" gap="2">
              <Box
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '3px',
                  background: value.color,
                }}
              />
              <Text size="1" color="gray">{value.label}</Text>
            </Flex>
          ))}
        </Flex>
      </Card>
    </Flex>
  );
};

export default SkillHeatmap;
