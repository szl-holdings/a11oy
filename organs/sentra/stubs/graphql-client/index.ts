import type { ReactNode } from 'react';
export const GraphQLProvider = ({ children }: { children?: ReactNode }) => children;
export function useAegisAssessments() { return { data: [], loading: false }; }
export function useAegisIncidents() { return { data: [], loading: false }; }
