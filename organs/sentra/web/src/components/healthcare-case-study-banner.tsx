/**
 * Healthcare IdP Case Study Banner
 *
 * Sticky contextual banner shown on the 4 case-study pages when the user
 * navigates with ?caseStudy=healthcare-idp. Links to each step in the chain:
 * autonomous-soc-command → identity-blast-radius → adversary-engine → incident-commander.
 */
import { cn } from '@szl-holdings/shared-ui/utils';
import { Activity, AlertTriangle, ArrowRight, Brain, ExternalLink, Shield, Target, X } from 'lucide-react';
import { useState } from 'react';
import { useSearch } from 'wouter';

interface CaseStudyStep {
  step: number;
  label: string;
  page: string;
  deepLink: string;
  icon: typeof Shield;
  active?: boolean;
}

const STEPS: CaseStudyStep[] = [
  { step: 1, label: 'Autonomous SOC', page: 'autonomous-soc-command', deepLink: '/sentra/autonomous-soc-command?caseStudy=healthcare-idp', icon: Activity },
  { step: 2, label: 'Blast Radius', page: 'identity-blast-radius', deepLink: '/sentra/identity-blast-radius?identityId=ehr-svc-prod&caseStudy=healthcare-idp', icon: Brain },
  { step: 3, label: 'Adversary Replay', page: 'adversary-engine', deepLink: '/sentra/adversary-engine?scenario=case-study-healthcare-idp-2026&caseStudy=healthcare-idp', icon: Target },
  { step: 4, label: 'Incident Commander', page: 'incident-commander', deepLink: '/sentra/incident-commander?incident=INC-HCARE-001&caseStudy=healthcare-idp', icon: Shield },
];

interface HealthcareCaseStudyBannerProps {
  currentPage: CaseStudyStep['page'];
  className?: string;
}

export function HealthcareCaseStudyBanner({ currentPage, className }: HealthcareCaseStudyBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const search = useSearch();
  const params = new URLSearchParams(search);
  const isActive = params.get('caseStudy') === 'healthcare-idp';
  if (!isActive || dismissed) return null;

  const currentStep = STEPS.find(s => s.page === currentPage);

  return (
    <div className={cn(
      'rounded-xl border border-[#c9b787]/30 bg-[#c9b787]/8 p-4',
      className,
    )}>
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-[#c9b787]/15 border border-[#c9b787]/30 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-4 h-4 text-[#c9b787]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-semibold text-[#c9b787]">Case Study</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded border border-[#f5f5f5]/30 bg-[#f5f5f5]/10 text-[#f5f5f5] font-mono uppercase">CRITICAL</span>
            <span className="text-[9px] text-zinc-500">HIPAA · CRITICAL INFRASTRUCTURE</span>
          </div>
          <h3 className="text-sm font-semibold text-white mb-1">Healthcare IdP Compromise → 7-Day Blast Radius</h3>
          <p className="text-[11px] text-zinc-400 mb-3 leading-relaxed">
            SAML assertion forgery (CVE-2024-22243, EPSS 0.71, KEV-listed) against Azure AD B2C. Service account
            <code className="mx-1 px-1 py-0.5 rounded bg-white/5 text-[#c9b787] text-[10px]">ehr-svc-prod</code>
            compromised. Blast radius: 312 systems, 1.4M EHI records at risk.
          </p>

          <div className="flex items-center gap-1 flex-wrap">
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              const isActive = step.page === currentPage;
              const isDone = step.step < (currentStep?.step ?? 1);
              return (
                <div key={step.step} className="flex items-center gap-1">
                  <a
                    href={step.deepLink}
                    className={cn(
                      'flex items-center gap-1.5 px-2 py-1 rounded border text-[10px] font-medium transition-all',
                      isActive
                        ? 'border-[#c9b787]/50 bg-[#c9b787]/15 text-[#c9b787]'
                        : isDone
                        ? 'border-white/10 bg-white/5 text-zinc-500'
                        : 'border-white/8 bg-white/3 text-zinc-400 hover:bg-white/8 hover:text-zinc-300',
                    )}
                  >
                    <Icon className="w-3 h-3" />
                    <span>{step.step}. {step.label}</span>
                    {isActive && <span className="w-1.5 h-1.5 rounded-full bg-[#c9b787] animate-pulse" />}
                  </a>
                  {i < STEPS.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-zinc-600 shrink-0" />
                  )}
                </div>
              );
            })}
            <a
              href="/sentra/autonomous-soc-command?caseStudy=healthcare-idp"
              className="ml-2 flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              Full case study
            </a>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-zinc-600 hover:text-zinc-400 transition-colors shrink-0 mt-0.5"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
