import type { DomainData } from '../types';
import { DomainCard } from './domain-card';

interface DomainGridProps {
  domains: DomainData[];
}

export function DomainGrid({ domains }: DomainGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {domains.map((domain) => (
        <DomainCard key={domain.id} data={domain} />
      ))}
    </div>
  );
}
