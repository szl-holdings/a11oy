import { lazy, Suspense, type ReactNode } from 'react';
import { Route, Switch } from 'wouter';
import { GraphQLProvider } from './graphql';
import { AppShell } from './components/shell/AppShell';

function stripTrailingSlash(path: string) {
  return path.endsWith('/') && path.length > 1 ? path.slice(0, -1) : path;
}

// RESET 2026-05-31 (Yachay CTO): a11oy is the Brand Orchestration Layer mounted at
// ROOT (vite base="/", Replit artifact.toml BASE_PATH="/"). With base="/",
// import.meta.env.BASE_URL === "/", so stripping the trailing slash yields "" — the
// correct root mount. The previous `|| '/a11oy'` fallback was a bug: it coerced the
// empty (root) string back to "/a11oy", registering every wouter route under
// /a11oy/* so the live /boardroom, /investor-demo, /fabric, ... URLs matched NOTHING
// and rendered the 404 shell. Empty string === root is intentional; do not re-add
// a non-root fallback.
const base = stripTrailingSlash((import.meta.env.BASE_URL ?? '/').replace(/\/$/, ''));

function Loader() {
  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ backgroundColor: '#0a0a0a' }}
    >
      <div
        className="w-6 h-6 border-2 rounded-full animate-spin"
        style={{ borderColor: 'rgba(255,255,255,0.08)', borderTopColor: '#c9b787' }}
      />
    </div>
  );
}

function WithShell({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}

const HomePage = lazy(() => import('./pages/HomePage').then((m) => ({ default: m.HomePage })));
const NowBoard = lazy(() => import('./pages/NowBoard').then((m) => ({ default: m.NowBoard })));
const CommandSurface = lazy(() =>
  import('./pages/CommandSurface').then((m) => ({ default: m.CommandSurface })),
);
const SignalMesh = lazy(() =>
  import('./pages/SignalMesh').then((m) => ({ default: m.SignalMesh })),
);
const ActionRail = lazy(() =>
  import('./pages/ActionRail').then((m) => ({ default: m.ActionRail })),
);
const ProofLedger = lazy(() =>
  import('./pages/ProofLedger').then((m) => ({ default: m.ProofLedger })),
);
const Governance = lazy(() =>
  import('./pages/Governance').then((m) => ({ default: m.Governance })),
);
const Agents = lazy(() => import('./pages/Agents').then((m) => ({ default: m.Agents })));
const Workcells = lazy(() => import('./pages/Workcells').then((m) => ({ default: m.Workcells })));
const WorkcellDetail = lazy(() =>
  import('./pages/WorkcellDetail').then((m) => ({ default: m.WorkcellDetail })),
);
const WorkcellReplayDetail = lazy(() =>
  import('./pages/WorkcellReplayDetail').then((m) => ({ default: m.WorkcellReplayDetail })),
);
const MirrorEval = lazy(() =>
  import('./pages/MirrorEval').then((m) => ({ default: m.MirrorEval })),
);
const ConnectorFirewall = lazy(() =>
  import('./pages/ConnectorFirewall').then((m) => ({ default: m.ConnectorFirewall })),
);
const TwinFoundry = lazy(() =>
  import('./pages/TwinFoundry').then((m) => ({ default: m.TwinFoundry })),
);
const TrustCenter = lazy(() =>
  import('./pages/TrustCenter').then((m) => ({ default: m.TrustCenter })),
);
const Constitution = lazy(() =>
  import('./pages/Constitution').then((m) => ({ default: m.Constitution })),
);
const SecurityCompliance = lazy(() =>
  import('./pages/SecurityCompliance').then((m) => ({ default: m.SecurityCompliance })),
);
const RightToAudit = lazy(() =>
  import('./pages/RightToAudit').then((m) => ({ default: m.RightToAudit })),
);
const ModelRouter = lazy(() =>
  import('./pages/ModelRouter').then((m) => ({ default: m.ModelRouter })),
);
const SkillsLibrary = lazy(() =>
  import('./pages/SkillsLibrary').then((m) => ({ default: m.SkillsLibrary })),
);
// COOKBOOK + RESEARCH INSTILLATION (Opus 4.8, additive — Doctrine v9).
const CookbookLanding = lazy(() =>
  import('./pages/CookbookLanding').then((m) => ({ default: m.CookbookLanding })),
);
const CookbookKnotCalculus = lazy(() =>
  import('./pages/CookbookKnotCalculus').then((m) => ({ default: m.CookbookKnotCalculus })),
);
const CookbookAnatomy = lazy(() =>
  import('./pages/CookbookAnatomy').then((m) => ({ default: m.CookbookAnatomy })),
);
const ResearchThesis = lazy(() =>
  import('./pages/ResearchThesis').then((m) => ({ default: m.ResearchThesis })),
);
const WorkcellReplay = lazy(() =>
  import('./pages/WorkcellReplay').then((m) => ({ default: m.WorkcellReplay })),
);
const SovereignReplayDetail = lazy(() =>
  import('./pages/SovereignReplayDetail').then((m) => ({ default: m.SovereignReplayDetail })),
);
const Sovereign = lazy(() => import('./pages/Sovereign').then((m) => ({ default: m.Sovereign })));
const BoardroomMode = lazy(() =>
  import('./pages/BoardroomMode').then((m) => ({ default: m.BoardroomMode })),
);
const InvestorDemo = lazy(() =>
  import('./pages/InvestorDemo').then((m) => ({ default: m.InvestorDemo })),
);
const FlexCacheRuntime = lazy(() =>
  import('./pages/FlexCacheRuntime').then((m) => ({ default: m.FlexCacheRuntime })),
);
const Terminal = lazy(() => import('./pages/Terminal').then((m) => ({ default: m.Terminal })));
const Fabric = lazy(() => import('./pages/Fabric').then((m) => ({ default: m.Fabric })));
const FabricCockpit = lazy(() =>
  import('./pages/fabric/FabricCockpit').then((m) => ({ default: m.FabricCockpit })),
);
const FabricVerticalsCommand = lazy(() =>
  import('./pages/fabric/VerticalsCommand').then((m) => ({ default: m.VerticalsCommand })),
);
const FabricDomainTwins = lazy(() =>
  import('./pages/fabric/DomainTwins').then((m) => ({ default: m.DomainTwins })),
);
const FabricSignalMeshPage = lazy(() =>
  import('./pages/fabric/SignalMesh').then((m) => ({ default: m.FabricSignalMesh })),
);
const FabricRiskMatrix = lazy(() =>
  import('./pages/fabric/RiskMatrix').then((m) => ({ default: m.RiskMatrix })),
);
const FabricDecisionQueue = lazy(() =>
  import('./pages/fabric/DecisionQueue').then((m) => ({ default: m.DecisionQueue })),
);
const FabricOutcomeMemory = lazy(() =>
  import('./pages/fabric/OutcomeMemory').then((m) => ({ default: m.OutcomeMemory })),
);
const FabricEvidenceLedger = lazy(() =>
  import('./pages/fabric/EvidenceLedger').then((m) => ({ default: m.EvidenceLedger })),
);
const FabricEcosystemRoadmap = lazy(() =>
  import('./pages/fabric/EcosystemRoadmap').then((m) => ({ default: m.EcosystemRoadmap })),
);
const Verticals = lazy(() => import('./pages/Verticals').then((m) => ({ default: m.Verticals })));
const Outcomes = lazy(() => import('./pages/Outcomes').then((m) => ({ default: m.Outcomes })));
const Memory = lazy(() => import('./pages/Memory').then((m) => ({ default: m.Memory })));
const Tools = lazy(() => import('./pages/Tools').then((m) => ({ default: m.Tools })));
const Pce = lazy(() => import('./pages/Pce').then((m) => ({ default: m.Pce })));
const Demo = lazy(() => import('./pages/Demo').then((m) => ({ default: m.Demo })));
const About = lazy(() => import('./pages/About').then((m) => ({ default: m.About })));
const Recommendations = lazy(() =>
  import('./pages/Recommendations').then((m) => ({ default: m.Recommendations })),
);
const ExecutiveBrief = lazy(() =>
  import('./pages/ExecutiveBrief').then((m) => ({ default: m.ExecutiveBrief })),
);
const AgentOrchestration = lazy(() =>
  import('./pages/AgentOrchestration').then((m) => ({ default: m.AgentOrchestration })),
);
const AgentViz = lazy(() => import('./pages/AgentViz').then((m) => ({ default: m.AgentViz })));
const DevPlatform = lazy(() =>
  import('./pages/DevPlatform').then((m) => ({ default: m.DevPlatform })),
);
const A11oyCode = lazy(() => import('./pages/A11oyCode').then((m) => ({ default: m.A11oyCode })));
// ADDITIVE (Yachay): a11oy.code conversational orchestrator — NEW route /a11oy.code.
// Distinct from the marketing page above at /a11oy-code (untouched).
const A11oyCodeChat = lazy(() =>
  import('./pages/A11oyCodeChat').then((m) => ({ default: m.A11oyCodeChat })),
);
const AgentMesh = lazy(() => import('./pages/AgentMesh').then((m) => ({ default: m.AgentMesh })));
const PluginHub = lazy(() => import('./pages/PluginHub').then((m) => ({ default: m.PluginHub })));
const DeepResearch = lazy(() =>
  import('./pages/DeepResearch').then((m) => ({ default: m.DeepResearch })),
);
const CiAction = lazy(() => import('./pages/CiAction').then((m) => ({ default: m.CiAction })));
const AgiConvergence = lazy(() =>
  import('./pages/AgiConvergence').then((m) => ({ default: m.AgiConvergence })),
);
const OmniaAdoptionPage = lazy(() =>
  import('./pages/OmniaAdoption').then((m) => ({ default: m.OmniaAdoption })),
);
const Solutions = lazy(() => import('./pages/Solutions').then((m) => ({ default: m.Solutions })));
const ApplicationsCatalog = lazy(() =>
  import('./pages/ApplicationsCatalog').then((m) => ({ default: m.ApplicationsCatalog })),
);
const ConstellationGraph = lazy(() =>
  import('./pages/ConstellationGraph').then((m) => ({ default: m.ConstellationGraph })),
);
const ArchitectureOverview = lazy(() =>
  import('./pages/ArchitectureOverview').then((m) => ({ default: m.ArchitectureOverview })),
);
const ResourcesHub = lazy(() =>
  import('./pages/ResourcesHub').then((m) => ({ default: m.ResourcesHub })),
);
const ControlTower = lazy(() =>
  import('./pages/ControlTower').then((m) => ({ default: m.ControlTower })),
);
const PipelineCanvas = lazy(() =>
  import('./pages/PipelineCanvas').then((m) => ({ default: m.PipelineCanvas })),
);
const IntentRouter = lazy(() =>
  import('./pages/IntentRouter').then((m) => ({ default: m.IntentRouter })),
);
const PlannerCanvas = lazy(() =>
  import('./pages/PlannerCanvas').then((m) => ({ default: m.PlannerCanvas })),
);
const OntologyGraph = lazy(() =>
  import('./pages/OntologyGraph').then((m) => ({ default: m.OntologyGraph })),
);
const LearningLoop = lazy(() =>
  import('./pages/LearningLoop').then((m) => ({ default: m.LearningLoop })),
);
const Counterfactuals = lazy(() =>
  import('./pages/Counterfactuals').then((m) => ({ default: m.Counterfactuals })),
);
const AdversarialResilience = lazy(() =>
  import('./pages/AdversarialResilience').then((m) => ({ default: m.AdversarialResilience })),
);
const FrontierIntelligence = lazy(() =>
  import('./pages/FrontierIntelligence').then((m) => ({ default: m.FrontierIntelligence })),
);
const DarpaResilienceHub = lazy(() =>
  import('./pages/DarpaResilienceHub').then((m) => ({ default: m.DarpaResilienceHub })),
);
const GardRobustness = lazy(() =>
  import('./pages/GardRobustness').then((m) => ({ default: m.GardRobustness })),
);
const FormalVerification = lazy(() =>
  import('./pages/FormalVerification').then((m) => ({ default: m.FormalVerification })),
);
// ADDITIVE: Lean Kernel Live — embeds SZLHOLDINGS/lean-kernel live theorem table.
const LeanKernel = lazy(() =>
  import('./pages/LeanKernel').then((m) => ({ default: m.LeanKernel })),
);
const SupplyChainAttestation = lazy(() =>
  import('./pages/SupplyChainAttestation').then((m) => ({ default: m.SupplyChainAttestation })),
);
const ExplainabilityEngine = lazy(() =>
  import('./pages/ExplainabilityEngine').then((m) => ({ default: m.ExplainabilityEngine })),
);
const CapabilityCompartments = lazy(() =>
  import('./pages/CapabilityCompartments').then((m) => ({ default: m.CapabilityCompartments })),
);
const CyberResilience = lazy(() =>
  import('./pages/CyberResilience').then((m) => ({ default: m.CyberResilience })),
);
const SimGovernance = lazy(() =>
  import('./pages/SimGovernance').then((m) => ({ default: m.SimGovernance })),
);
const ApprovalQueue = lazy(() =>
  import('./pages/ApprovalQueue').then((m) => ({ default: m.ApprovalQueue })),
);
const VerifierAgent = lazy(() =>
  import('./pages/VerifierAgent').then((m) => ({ default: m.VerifierAgent })),
);
const AtlasSection = lazy(() =>
  import('./pages/AtlasSection').then((m) => ({ default: m.AtlasSection })),
);
const TokensSection = lazy(() =>
  import('./pages/TokensSection').then((m) => ({ default: m.TokensSection })),
);
const VoiceSection = lazy(() =>
  import('./pages/VoiceSection').then((m) => ({ default: m.VoiceSection })),
);
const LibrarySection = lazy(() =>
  import('./pages/LibrarySection').then((m) => ({ default: m.LibrarySection })),
);
const ReleasesSection = lazy(() =>
  import('./pages/ReleasesSection').then((m) => ({ default: m.ReleasesSection })),
);
const AuditSection = lazy(() =>
  import('./pages/AuditSection').then((m) => ({ default: m.AuditSection })),
);
const DoctrineOverview = lazy(() =>
  import('./pages/DoctrineOverview').then((m) => ({ default: m.DoctrineOverview })),
);
const RiskReports = lazy(() =>
  import('./pages/RiskReports').then((m) => ({ default: m.RiskReports })),
);
const BehavioralAudit = lazy(() =>
  import('./pages/BehavioralAudit').then((m) => ({ default: m.BehavioralAudit })),
);
const CovenantLift = lazy(() =>
  import('./pages/CovenantLift').then((m) => ({ default: m.CovenantLift })),
);
const CodeBehaviors = lazy(() =>
  import('./pages/CodeBehaviors').then((m) => ({ default: m.CodeBehaviors })),
);
const RewardHacking = lazy(() =>
  import('./pages/RewardHacking').then((m) => ({ default: m.RewardHacking })),
);
const AlignmentReview = lazy(() =>
  import('./pages/AlignmentReview').then((m) => ({ default: m.AlignmentReview })),
);
const SnapshotProvenance = lazy(() =>
  import('./pages/SnapshotProvenance').then((m) => ({ default: m.SnapshotProvenance })),
);
const AIUserTurn = lazy(() =>
  import('./pages/AIUserTurn').then((m) => ({ default: m.AIUserTurn })),
);
const AgentWelfare = lazy(() =>
  import('./pages/AgentWelfare').then((m) => ({ default: m.AgentWelfare })),
);
const RedTeam = lazy(() => import('./pages/RedTeam').then((m) => ({ default: m.RedTeam })));
const GlasswingPage = lazy(() =>
  import('./pages/Glasswing').then((m) => ({ default: m.Glasswing })),
);
const ArgoForgePage = lazy(() =>
  import('./pages/ArgoForge').then((m) => ({ default: m.ArgoForge })),
);
const HatunLayerPage = lazy(() =>
  import('./pages/HatunLayer').then((m) => ({ default: m.HatunLayer })),
);
const AerialTwinPage = lazy(() =>
  import('./pages/AerialTwin').then((m) => ({ default: m.AerialTwin })),
);
const AerialTwinMilestonePage = lazy(() =>
  import('./pages/AerialTwinMilestone').then((m) => ({ default: m.AerialTwinMilestone })),
);
const SystemCard = lazy(() =>
  import('./pages/SystemCard').then((m) => ({ default: m.SystemCard })),
);
const CapabilityTrajectory = lazy(() =>
  import('./pages/CapabilityTrajectory').then((m) => ({ default: m.CapabilityTrajectory })),
);
const HatunSpec = lazy(() =>
  import('./pages/HatunSpec').then((m) => ({ default: m.HatunSpec })),
);
const GlasswingPartners = lazy(() =>
  import('./pages/GlasswingPartners').then((m) => ({ default: m.GlasswingPartners })),
);
const CAVDPage = lazy(() => import('./pages/CAVD').then((m) => ({ default: m.CAVD })));
const TransparencyReport = lazy(() =>
  import('./pages/TransparencyReport').then((m) => ({ default: m.TransparencyReport })),
);
const PublicTrustPortal = lazy(() =>
  import('./pages/PublicTrustPortal').then((m) => ({ default: m.PublicTrustPortal })),
);
const RobustnessWall = lazy(() =>
  import('./pages/RobustnessWall').then((m) => ({ default: m.RobustnessWall })),
);
const ConstitutionDSL = lazy(() =>
  import('./pages/ConstitutionDSL').then((m) => ({ default: m.ConstitutionDSL })),
);
const WelfarePlaybooks = lazy(() =>
  import('./pages/WelfarePlaybooks').then((m) => ({ default: m.WelfarePlaybooks })),
);
const DefenderCredits = lazy(() =>
  import('./pages/DefenderCredits').then((m) => ({ default: m.DefenderCredits })),
);
const Compass = lazy(() => import('./pages/Compass').then((m) => ({ default: m.Compass })));
const AgentBom = lazy(() => import('./pages/AgentBom').then((m) => ({ default: m.AgentBom })));
const DelegationChainPage = lazy(() =>
  import('./pages/DelegationChain').then((m) => ({ default: m.DelegationChain })),
);
const TrustExchange = lazy(() =>
  import('./pages/TrustExchange').then((m) => ({ default: m.TrustExchange })),
);
const CareEngine = lazy(() =>
  import('./pages/CareEngine').then((m) => ({ default: m.CareEngine })),
);
const PrecisionAI = lazy(() =>
  import('./pages/PrecisionAI').then((m) => ({ default: m.PrecisionAI })),
);
const WeaponizedIntel = lazy(() =>
  import('./pages/WeaponizedIntel').then((m) => ({ default: m.WeaponizedIntel })),
);
const AgentZeroTrust = lazy(() =>
  import('./pages/AgentZeroTrust').then((m) => ({ default: m.AgentZeroTrust })),
);
const AtlasShield = lazy(() =>
  import('./pages/AtlasShield').then((m) => ({ default: m.AtlasShield })),
);
const SwarmOrchestrator = lazy(() =>
  import('./pages/SwarmOrchestrator').then((m) => ({ default: m.SwarmOrchestrator })),
);
const PlaybookEngine = lazy(() =>
  import('./pages/PlaybookEngine').then((m) => ({ default: m.PlaybookEngine })),
);
const A2AInterop = lazy(() =>
  import('./pages/A2AInterop').then((m) => ({ default: m.A2AInterop })),
);
const AgentIdentityRegistry = lazy(() =>
  import('./pages/AgentIdentityRegistry').then((m) => ({ default: m.AgentIdentityRegistry })),
);
const SelfOptimization = lazy(() =>
  import('./pages/SelfOptimization').then((m) => ({ default: m.SelfOptimization })),
);
const GovernedSecurityAgents = lazy(() =>
  import('./pages/GovernedSecurityAgents').then((m) => ({ default: m.GovernedSecurityAgents })),
);
const A11oyBillingPage = lazy(() => import('./pages/billing-account'));
const KarpathyEvolution = lazy(() =>
  import('./pages/KarpathyEvolution').then((m) => ({ default: m.KarpathyEvolution })),
);
const Praxis = lazy(() => import('./pages/Praxis').then((m) => ({ default: m.Praxis })));
const McpHub = lazy(() => import('./pages/McpHub').then((m) => ({ default: m.McpHub })));
const AgenticRag = lazy(() =>
  import('./pages/AgenticRag').then((m) => ({ default: m.AgenticRag })),
);
const SubstrateCompute = lazy(() =>
  import('./pages/SubstrateCompute').then((m) => ({ default: m.SubstrateCompute })),
);
const TotoForecaster = lazy(() =>
  import('./pages/TotoForecaster').then((m) => ({ default: m.TotoForecaster })),
);
const CausalRCA = lazy(() => import('./pages/CausalRCA').then((m) => ({ default: m.CausalRCA })));
const SyntheticMetrics = lazy(() =>
  import('./pages/SyntheticMetrics').then((m) => ({ default: m.SyntheticMetrics })),
);
const SelfHealingEngine = lazy(() =>
  import('./pages/SelfHealingEngine').then((m) => ({ default: m.SelfHealingEngine })),
);
const ObservabilityAsCode = lazy(() =>
  import('./pages/ObservabilityAsCode').then((m) => ({ default: m.ObservabilityAsCode })),
);
const AlertTriage = lazy(() =>
  import('./pages/AlertTriage').then((m) => ({ default: m.AlertTriage })),
);
const CostAwareMonitoring = lazy(() =>
  import('./pages/CostAwareMonitoring').then((m) => ({ default: m.CostAwareMonitoring })),
);
// DINN Lab (/research/dinn) — additive DINN research surface
const DinnLab = lazy(() =>
  import('./pages/DinnLab').then((m) => ({ default: m.DinnLab })),
);
// ADDITIVE: LUTAR_EVIDENCE + OUROBOROS_RUN_ALL — Doctrine v10 P0 surfaces (2026-05-31)
const Evidence = lazy(() =>
  import('./pages/Evidence').then((m) => ({ default: m.Evidence })),
);
const Ouroboros = lazy(() =>
  import('./pages/Ouroboros').then((m) => ({ default: m.Ouroboros })),
);
// ADDITIVE: WAYRA — the empire's lungs (Doctrine v13, 4th edge organ) (2026-06-01)
const Wayra = lazy(() =>
  import('./pages/Wayra').then((m) => ({ default: m.Wayra })),
);

export default function App() {
  return (
    <GraphQLProvider>
      <Suspense fallback={<Loader />}>
        <Switch>
          <Route path={`${base}/`} component={HomePage} />
          {/* ROOT-MOUNT FIX (Yachay CTO + Opus): at root, base==='' so a bare
              `path={base}` is the empty string. wouter's matchRoute does
              `parser(route || "*")`, and "" is falsy — so an empty path compiles to
              the "*" WILDCARD and matches EVERY route, making the Switch render
              HomePage on /boardroom, /investor-demo, /governance, ... (all routes
              showed the landing hero). We only emit the bare-base alias when base
              is a non-empty prefix (e.g. "/a11oy"); at root, `path={base}/`="/"
              already covers the front door. */}
          {base ? <Route path={base} component={HomePage} /> : null}
          <Route path={`${base}/research/dinn`} component={DinnLab} />
          <Route path={`${base}/now`} component={NowBoard} />
          <Route path={`${base}/recommendations`} component={Recommendations} />
          <Route path={`${base}/brief`} component={ExecutiveBrief} />
          <Route path={`${base}/command`} component={CommandSurface} />
          <Route path={`${base}/signals`} component={SignalMesh} />
          <Route path={`${base}/actions`} component={ActionRail} />
          <Route path={`${base}/proof`} component={ProofLedger} />
          <Route path={`${base}/governance`} component={Governance} />
          <Route path={`${base}/agents`} component={Agents} />
          <Route path={`${base}/workcells/:id/replay`} component={WorkcellReplayDetail} />
          <Route path={`${base}/workcells/:id`} component={WorkcellDetail} />
          <Route path={`${base}/workcells`} component={Workcells} />
          <Route path={`${base}/evals`} component={MirrorEval} />
          <Route path={`${base}/connectors`} component={ConnectorFirewall} />
          <Route path={`${base}/twins`} component={TwinFoundry} />
          <Route path={`${base}/model-router`} component={ModelRouter} />
          <Route path={`${base}/skills`} component={SkillsLibrary} />
          <Route path={`${base}/replay/:id`} component={SovereignReplayDetail} />
          <Route path={`${base}/replay`} component={WorkcellReplay} />
          <Route path={`${base}/trust`} component={TrustCenter} />
          <Route path={`${base}/constitution`} component={Constitution} />
          <Route path={`${base}/security-compliance`} component={SecurityCompliance} />
          <Route path={`${base}/right-to-audit`} component={RightToAudit} />
          <Route path={`${base}/sovereign`} component={Sovereign} />
          <Route path={`${base}/boardroom`} component={BoardroomMode} />
          <Route path={`${base}/investor-demo`} component={InvestorDemo} />
          <Route path={`${base}/flexcache`} component={FlexCacheRuntime} />
          <Route path={`${base}/terminal`} component={Terminal} />
          <Route path={`${base}/nexus`} component={Praxis} />
          <Route path={`${base}/mcp-hub`} component={McpHub} />
          <Route path={`${base}/agentic-rag`} component={AgenticRag} />
          <Route path={`${base}/fabric/verticals`} component={FabricVerticalsCommand} />
          <Route path={`${base}/fabric/twins`} component={FabricDomainTwins} />
          <Route path={`${base}/fabric/signals`} component={FabricSignalMeshPage} />
          <Route path={`${base}/fabric/risks`} component={FabricRiskMatrix} />
          <Route path={`${base}/fabric/decisions`} component={FabricDecisionQueue} />
          <Route path={`${base}/fabric/outcomes`} component={FabricOutcomeMemory} />
          <Route path={`${base}/fabric/evidence`} component={FabricEvidenceLedger} />
          <Route path={`${base}/fabric/roadmap`} component={FabricEcosystemRoadmap} />
          <Route path={`${base}/fabric`} component={FabricCockpit} />
          <Route path={`${base}/verticals`} component={Verticals} />
          <Route path={`${base}/outcomes`} component={Outcomes} />
          <Route path={`${base}/memory`} component={Memory} />
          <Route path={`${base}/tools`} component={Tools} />
          <Route path={`${base}/pce`} component={Pce} />
          <Route path={`${base}/demo`} component={Demo} />
          <Route path={`${base}/orchestration`} component={AgentOrchestration} />
          <Route path={`${base}/agent-viz`} component={AgentViz} />
          <Route path={`${base}/sdk`} component={DevPlatform} />
          <Route path={`${base}/a11oy-code`} component={A11oyCode} />
          <Route path={`${base}/a11oy.code`} component={A11oyCodeChat} />
          <Route path={`${base}/agent-mesh`} component={AgentMesh} />
          <Route path={`${base}/plugins`} component={PluginHub} />
          <Route path={`${base}/deep-research`} component={DeepResearch} />
          <Route path={`${base}/action`} component={CiAction} />
          <Route path={`${base}/convergence`} component={AgiConvergence} />
          <Route path={`${base}/solutions`} component={Solutions} />
          <Route path={`${base}/about`} component={About} />
          <Route path={`${base}/omnia-adoption`} component={OmniaAdoptionPage} />
          <Route path={`${base}/applications`} component={ApplicationsCatalog} />
          <Route path={`${base}/constellation`} component={ConstellationGraph} />
          <Route path={`${base}/architecture`} component={ArchitectureOverview} />
          <Route path={`${base}/resources`} component={ResourcesHub} />
          <Route path={`${base}/control-tower`} component={ControlTower} />
          <Route path={`${base}/pipeline`} component={PipelineCanvas} />
          <Route path={`${base}/intent-router`} component={IntentRouter} />
          <Route path={`${base}/planner`} component={PlannerCanvas} />
          <Route path={`${base}/ontology`} component={OntologyGraph} />
          <Route path={`${base}/learning`} component={LearningLoop} />
          <Route path={`${base}/counterfactuals`} component={Counterfactuals} />
          <Route path={`${base}/adversarial`} component={AdversarialResilience} />
          <Route path={`${base}/frontier`} component={FrontierIntelligence} />
          <Route path={`${base}/approval-queue`} component={ApprovalQueue} />
          <Route path={`${base}/verifier`} component={VerifierAgent} />
          <Route path={`${base}/doctrine`} component={DoctrineOverview} />
          <Route path={`${base}/risk-reports`} component={RiskReports} />
          <Route path={`${base}/behavioral-audit`} component={BehavioralAudit} />
          <Route path={`${base}/covenant-lift`} component={CovenantLift} />
          <Route path={`${base}/code-behaviors`} component={CodeBehaviors} />
          <Route path={`${base}/reward-hacking`} component={RewardHacking} />
          <Route path={`${base}/alignment-review`} component={AlignmentReview} />
          <Route path={`${base}/snapshot-provenance`} component={SnapshotProvenance} />
          <Route path={`${base}/ai-user-turn`} component={AIUserTurn} />
          <Route path={`${base}/welfare`} component={AgentWelfare} />
          <Route path={`${base}/red-team`} component={RedTeam} />
          <Route path={`${base}/glasswing`} component={GlasswingPage} />
          <Route path={`${base}/argo`} component={ArgoForgePage} />
          <Route path={`${base}/hatun-layer`} component={HatunLayerPage} />
          <Route path={`${base}/aerial-twin`} component={AerialTwinPage} />
          <Route path={`${base}/aerial-twin/:milestone`} component={AerialTwinMilestonePage} />
          <Route path={`${base}/system-card/:id`} component={SystemCard} />
          <Route path={`${base}/capability-trajectory`} component={CapabilityTrajectory} />
          <Route path={`${base}/resilience`} component={DarpaResilienceHub} />
          <Route path={`${base}/gard-robustness`} component={GardRobustness} />
          <Route path={`${base}/formal-verification`} component={FormalVerification} />
          <Route path={`${base}/lean`} component={LeanKernel} />
          <Route path={`${base}/supply-chain`} component={SupplyChainAttestation} />
          <Route path={`${base}/explainability`} component={ExplainabilityEngine} />
          <Route path={`${base}/compartments`} component={CapabilityCompartments} />
          <Route path={`${base}/cyber-resilience`} component={CyberResilience} />
          <Route path={`${base}/sim-governance`} component={SimGovernance} />
          <Route path={`${base}/hatun-spec`} component={HatunSpec} />
          <Route path={`${base}/glasswing-partners`} component={GlasswingPartners} />
          <Route path={`${base}/cavd`} component={CAVDPage} />
          <Route path={`${base}/transparency-report`} component={TransparencyReport} />
          <Route path={`${base}/trust-portal`} component={PublicTrustPortal} />
          <Route path={`${base}/robustness-wall`} component={RobustnessWall} />
          <Route path={`${base}/constitution-dsl`} component={ConstitutionDSL} />
          <Route path={`${base}/welfare-playbooks`} component={WelfarePlaybooks} />
          <Route path={`${base}/defender-credits`} component={DefenderCredits} />
          <Route path={`${base}/compass`} component={Compass} />
          <Route path={`${base}/agent-bom`} component={AgentBom} />
          <Route path={`${base}/delegation-chain`} component={DelegationChainPage} />
          <Route path={`${base}/trust-exchange`} component={TrustExchange} />
          <Route path={`${base}/care`} component={CareEngine} />
          <Route path={`${base}/precision-ai`} component={PrecisionAI} />
          <Route path={`${base}/weaponized-intel`} component={WeaponizedIntel} />
          <Route path={`${base}/agent-zero-trust`} component={AgentZeroTrust} />
          <Route path={`${base}/atlas-shield`} component={AtlasShield} />
          <Route path={`${base}/swarm-orchestrator`} component={SwarmOrchestrator} />
          <Route path={`${base}/playbook-engine`} component={PlaybookEngine} />
          <Route path={`${base}/a2a-interop`} component={A2AInterop} />
          <Route path={`${base}/agent-identity`} component={AgentIdentityRegistry} />
          <Route path={`${base}/self-optimization`} component={SelfOptimization} />
          <Route path={`${base}/security-agents`} component={GovernedSecurityAgents} />
          <Route path={`${base}/karpathy-evolution`} component={KarpathyEvolution} />
          <Route path={`${base}/substrate-compute`} component={SubstrateCompute} />
          <Route path={`${base}/toto-forecaster`} component={TotoForecaster} />
          <Route path={`${base}/causal-rca`} component={CausalRCA} />
          <Route path={`${base}/synthetic-metrics`} component={SyntheticMetrics} />
          <Route path={`${base}/self-healing`} component={SelfHealingEngine} />
          <Route path={`${base}/observability-as-code`} component={ObservabilityAsCode} />
          <Route path={`${base}/alert-triage`} component={AlertTriage} />
          <Route path={`${base}/cost-monitoring`} component={CostAwareMonitoring} />
          {/* COOKBOOK + RESEARCH (Opus 4.8 instillation — additive). Specific
              recipe routes registered BEFORE the /cookbook landing so wouter's
              Switch matches them first. */}
          <Route path={`${base}/cookbook/knot-calculus-v1`} component={CookbookKnotCalculus} />
          <Route path={`${base}/cookbook/anatomy-evolved-v1`} component={CookbookAnatomy} />
          <Route path={`${base}/cookbook`} component={CookbookLanding} />
          <Route path={`${base}/research/thesis`} component={ResearchThesis} />
          {/* ADDITIVE: LUTAR_EVIDENCE + OUROBOROS_RUN_ALL — Doctrine v10 P0 surfaces */}
          <Route path={`${base}/evidence`} component={Evidence} />
          <Route path={`${base}/ouroboros`} component={Ouroboros} />
          {/* ADDITIVE: WAYRA — always-learning firehose organ (Doctrine v13) */}
          <Route path={`${base}/wayra`} component={Wayra} />

          <Route path={`${base}/atlas`}>
            <WithShell>
              <AtlasSection />
            </WithShell>
          </Route>
          <Route path={`${base}/tokens`}>
            <WithShell>
              <TokensSection />
            </WithShell>
          </Route>
          <Route path={`${base}/voice`}>
            <WithShell>
              <VoiceSection />
            </WithShell>
          </Route>
          <Route path={`${base}/library`}>
            <WithShell>
              <LibrarySection />
            </WithShell>
          </Route>
          <Route path={`${base}/releases`}>
            <WithShell>
              <ReleasesSection />
            </WithShell>
          </Route>
          <Route path={`${base}/audit`}>
            <WithShell>
              <AuditSection />
            </WithShell>
          </Route>
          <Route path={`${base}/account/billing`}>
            <WithShell>
              <A11oyBillingPage />
            </WithShell>
          </Route>
          <Route>
            <div
              className="flex items-center justify-center min-h-screen"
              style={{
                backgroundColor: 'var(--color-a11oy-navy)',
                color: 'var(--color-a11oy-text)',
              }}
            >
              <div className="text-center">
                <div
                  className="text-6xl font-display font-bold mb-4"
                  style={{ color: 'var(--color-a11oy-border)' }}
                >
                  404
                </div>
                <div className="text-sm" style={{ color: 'var(--color-a11oy-text-ghost)' }}>
                  Page not found
                </div>
                <a
                  href={`${base}/`}
                  className="mt-4 inline-block text-sm"
                  style={{ color: '#c9b787' }}
                >
                  ← Back to A11oy
                </a>
              </div>
            </div>
          </Route>
        </Switch>
      </Suspense>
    </GraphQLProvider>
  );
}
