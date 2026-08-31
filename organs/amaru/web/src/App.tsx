import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { Toaster } from 'sonner';
import { Layout } from '@/components/layout';
import { InnovationStoreProvider } from '@/lib/innovation-store';
import ConduitLandingPage from '@/pages/conduit-landing';
import Dashboard from '@/pages/dashboard';
import ComputePage from '@/pages/compute';
import ConnectionsList from '@/pages/connections/list';
import ConnectionsNew from '@/pages/connections/new';
import SyncsList from '@/pages/syncs/list';
import SyncsNew from '@/pages/syncs/new';
import SyncsDetail from '@/pages/syncs/detail';
import RunsList from '@/pages/runs/list';
import RunsDetail from '@/pages/runs/detail';
import TemplatesList from '@/pages/templates/list';
import Settings from '@/pages/settings';
import ConvergentSync from '@/pages/convergent-sync';
import CodexLoop from '@/pages/codex-loop';
import OuroborosPage from '@/pages/ouroboros';
import AmaruThesisPage from '@/pages/thesis';
import BrainPage from '@/pages/brain';
import ConduitSigil from '@/pages/sigil';
import OperationalCorePage from '@/pages/operational-core';
import SovereignAiHub from '@/pages/sovereign-ai-hub/index';
import ModelFleetConsole from '@/pages/sovereign-ai-hub/model-fleet';
import InferenceObservatory from '@/pages/sovereign-ai-hub/inference';
import DomainDistillery from '@/pages/sovereign-ai-hub/distillery';
import PraxisPlayground from '@/pages/sovereign-ai-hub/praxis';
import DataEstateCatalog from '@/pages/sovereign-ai-hub/data-estate';
import CognitiveInsights from '@/pages/sovereign-ai-hub/cognitive';
import AdminUsagePage from '@/pages/admin-usage';
import AgiForecastPage from '@/pages/agi-forecast';
import SourcesPage from '@/pages/sources';
import ModelsPage from '@/pages/models';
import DestinationsPage from '@/pages/destinations';
import MappingsPage from '@/pages/mappings';
import PoliciesPage from '@/pages/policies';
import ObservabilityPage from '@/pages/observability';
import OutcomesPage from '@/pages/outcomes';
import AgentsPage from '@/pages/agents';
import RoadmapPage from '@/pages/roadmap';
import InnovationPage from '@/pages/innovation/index';
import AudienceSqlPage from '@/pages/innovation/audience-sql';
import LineagePage from '@/pages/innovation/lineage';
import DriftRepairPage from '@/pages/innovation/drift-repair';
import GoldenRecordPage from '@/pages/innovation/golden-record';
import CostCarbonPage from '@/pages/innovation/cost-carbon';
import ClosedLoopPage from '@/pages/innovation/closed-loop';
import SimTheaterPage from '@/pages/innovation/sim-theater';
import MapperAccuracyPage from '@/pages/innovation/mapper-accuracy';
import DestinationDiscoveryPage from '@/pages/innovation/destination-discovery';
import PolicyDslPage from '@/pages/innovation/policy-dsl';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  return (
    <Switch>
      <Route path="/" component={ConduitLandingPage} />
      <Route>
        <Layout>
          <Switch>
            <Route path="/cockpit" component={Dashboard} />
            <Route path="/dashboard" component={Dashboard} />
        <Route path="/compute" component={ComputePage} />
        <Route path="/connections" component={ConnectionsList} />
        <Route path="/connections/new" component={ConnectionsNew} />
        <Route path="/syncs" component={SyncsList} />
        <Route path="/syncs/new" component={SyncsNew} />
        <Route path="/syncs/:id" component={SyncsDetail} />
        <Route path="/runs" component={RunsList} />
        <Route path="/runs/:id" component={RunsDetail} />
        <Route path="/templates" component={TemplatesList} />
        <Route path="/settings" component={Settings} />
        <Route path="/convergent-sync" component={ConvergentSync} />
        <Route path="/codex-loop" component={CodexLoop} />
        <Route path="/ouroboros" component={OuroborosPage} />
        <Route path="/thesis" component={AmaruThesisPage} />
        <Route path="/brain" component={BrainPage} />
        <Route path="/sigil" component={ConduitSigil} />
        <Route path="/operational-core" component={OperationalCorePage} />
        <Route path="/sovereign-ai-hub" component={SovereignAiHub} />
        <Route path="/sovereign-ai-hub/model-fleet" component={ModelFleetConsole} />
        <Route path="/sovereign-ai-hub/inference" component={InferenceObservatory} />
        <Route path="/sovereign-ai-hub/distillery" component={DomainDistillery} />
        <Route path="/sovereign-ai-hub/praxis" component={PraxisPlayground} />
        <Route path="/sovereign-ai-hub/data-estate" component={DataEstateCatalog} />
        <Route path="/sovereign-ai-hub/cognitive" component={CognitiveInsights} />
        <Route path="/admin/usage" component={AdminUsagePage} />
        <Route path="/agi-forecast" component={AgiForecastPage} />
        <Route path="/sources" component={SourcesPage} />
        <Route path="/models" component={ModelsPage} />
        <Route path="/destinations" component={DestinationsPage} />
        <Route path="/mappings" component={MappingsPage} />
        <Route path="/policies" component={PoliciesPage} />
        <Route path="/observability" component={ObservabilityPage} />
        <Route path="/outcomes" component={OutcomesPage} />
        <Route path="/agents" component={AgentsPage} />
        <Route path="/roadmap" component={RoadmapPage} />
        <Route path="/innovation" component={InnovationPage} />
        <Route path="/innovation/audience-sql" component={AudienceSqlPage} />
        <Route path="/innovation/lineage" component={LineagePage} />
        <Route path="/innovation/drift-repair" component={DriftRepairPage} />
        <Route path="/innovation/golden-record" component={GoldenRecordPage} />
        <Route path="/innovation/cost-carbon" component={CostCarbonPage} />
        <Route path="/innovation/closed-loop" component={ClosedLoopPage} />
        <Route path="/innovation/sim-theater" component={SimTheaterPage} />
        <Route path="/innovation/mapper-accuracy" component={MapperAccuracyPage} />
        <Route path="/innovation/destination-discovery" component={DestinationDiscoveryPage} />
        <Route path="/innovation/policy-dsl" component={PolicyDslPage} />
            <Route>
              <div className="flex h-full items-center justify-center text-muted-foreground">
                Page not found
              </div>
            </Route>
          </Switch>
        </Layout>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
        <InnovationStoreProvider>
          <AppContent />
        </InnovationStoreProvider>
      </WouterRouter>
      <Toaster theme="dark" toastOptions={{ className: 'font-sans' }} />
    </QueryClientProvider>
  );
}

export default App;
