// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { ContactModal, useContactModal } from '@szl-holdings/shared-ui/contact-modal';
import { ArrowRight, Building2, CheckCircle, Layers, Shield, X } from 'lucide-react';
import { useState } from 'react';
import { AEGIS_MITRE_COVERAGE, metricDisplay } from '../lib/claims';

const ACCENT = '#f5f5f5';
const BG = '#080a10';

const tiers = [
  {
    name: 'Defender',
    monthly: 799,
    annual: 665,
    description: 'For security teams getting unified visibility across their threat landscape.',
    icon: Shield,
    cta: 'Request Access',
    highlight: false,
    features: [
      'SOC command dashboard',
      metricDisplay(AEGIS_MITRE_COVERAGE),
      'CVE & vulnerability tracking',
      'Basic threat intelligence feed',
      'Incident management',
      '30-day event history',
      '5 analyst seats',
      'Email & Slack alerts',
    ],
    notIncluded: [
      'Adversary emulation',
      'MSP command (client management)',
      'Intelligence Engine (AI Labs)',
      'Custom compliance frameworks',
    ],
  },
  {
    name: 'Command',
    monthly: 2499,
    annual: 2079,
    description: 'For enterprise security teams and MSPs needing full-spectrum command.',
    icon: Layers,
    cta: 'Request Access',
    highlight: true,
    features: [
      'Full SOC command + XDR correlation',
      'MITRE ATT&CK adversary emulation',
      'Threat hunting & forensics timeline',
      'Identity threat detection',
      'Vulnerability management + hardening',
      'MSP client management & NOC',
      'SLA tracking & ticket workflow',
      'Compliance frameworks (NIST, SOC2, ISO)',
      'Sentinel AI security advisor',
      '90-day event history',
      '25 analyst seats',
      'API access',
    ],
    notIncluded: ['AI Intelligence Labs', 'Dedicated security engineer'],
  },
  {
    name: 'Enterprise',
    monthly: null,
    annual: null,
    description: 'For government agencies, financial institutions, and defense contractors.',
    icon: Building2,
    cta: 'Contact Sales',
    highlight: false,
    features: [
      'Full PARAGON platform — all workspaces',
      'AI Intelligence Labs access',
      'Custom AI security models',
      'Classified threat feed integration',
      'StateRAMP / CMMC / IL-4 support',
      'Dedicated security engineer',
      'Unlimited analyst seats',
      'Unlimited event history',
      'Custom compliance reporting',
      'SSO / SAML / SCIM',
      'Air-gapped deployment option',
      '99.99% SLA guarantee',
      'Executive security briefings',
    ],
    notIncluded: [],
  },
];

export default function AegisPricingPage() {
  const [annual, setAnnual] = useState(true);
  const { isOpen: contactOpen, open: openContact, close: closeContact } = useContactModal('demo');

  return (
    <div className="min-h-screen" style={{ background: BG, color: 'rgba(255,255,255,0.88)' }}>
      <ContactModal
        isOpen={contactOpen}
        onClose={closeContact}
        type="demo"
        app="aegis"
        title="Request Enterprise Access"
        subtitle="Vetted access only. Tell us about your organization."
      />

      <div className="border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/sentra/" className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(245,245,245,0.2)', border: '1px solid rgba(245,245,245,0.3)' }}
            >
              <Shield className="w-3.5 h-3.5" style={{ color: ACCENT }} />
            </div>
            <span className="text-sm font-semibold tracking-tight text-white">Sentra</span>
          </a>
          <a href="/sentra/" className="text-[12px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
            ← Back to Platform
          </a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-20 text-center">
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium mb-6"
          style={{ background: `${ACCENT}15`, color: ACCENT, border: `1px solid ${ACCENT}30` }}
        >
          Defense & Intelligence Pricing
        </div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-white">
          Unified defense at any scale
        </h1>
        <p
          className="text-[15px] max-w-xl mx-auto mb-10"
          style={{ color: 'rgba(255,255,255,0.5)' }}
        >
          From security teams to government agencies. Every tier includes full SOC command
          capability.
        </p>

        <div
          className="inline-flex items-center gap-1 p-1 rounded-full mb-16"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <button
            onClick={() => setAnnual(false)}
            className="px-5 py-2 rounded-full text-[13px] font-medium transition-all"
            style={{
              background: !annual ? 'rgba(255,255,255,0.12)' : 'transparent',
              color: !annual ? 'white' : 'rgba(255,255,255,0.45)',
            }}
          >
            Monthly
          </button>
          <button
            onClick={() => setAnnual(true)}
            className="px-5 py-2 rounded-full text-[13px] font-medium transition-all flex items-center gap-2"
            style={{
              background: annual ? 'rgba(255,255,255,0.12)' : 'transparent',
              color: annual ? 'white' : 'rgba(255,255,255,0.45)',
            }}
          >
            Annual
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
              style={{ background: `${ACCENT}20`, color: ACCENT }}
            >
              Save 17%
            </span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier) => {
            const Icon = tier.icon;
            const price = annual ? tier.annual : tier.monthly;
            return (
              <div
                key={tier.name}
                className="relative rounded-2xl p-8 text-left flex flex-col"
                style={{
                  background: tier.highlight
                    ? `linear-gradient(135deg, rgba(245,245,245,0.10), rgba(245,245,245,0.05))`
                    : 'rgba(255,255,255,0.03)',
                  border: tier.highlight
                    ? `1px solid ${ACCENT}35`
                    : '1px solid rgba(255,255,255,0.07)',
                }}
              >
                {tier.highlight && (
                  <div
                    className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider"
                    style={{ background: ACCENT, color: '#fff' }}
                  >
                    Most Popular
                  </div>
                )}

                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center"
                    style={{
                      background: tier.highlight ? `${ACCENT}20` : 'rgba(255,255,255,0.06)',
                    }}
                  >
                    <Icon
                      className="w-4 h-4"
                      style={{ color: tier.highlight ? ACCENT : 'rgba(255,255,255,0.5)' }}
                    />
                  </div>
                  <div className="text-[15px] font-bold text-white">{tier.name}</div>
                </div>

                <div className="mb-4">
                  {price !== null ? (
                    <div className="flex items-end gap-1.5">
                      <span className="text-4xl font-bold text-white">${price}</span>
                      <span className="text-[13px] mb-2" style={{ color: 'rgba(255,255,255,0.4)' }}>
                        /month
                      </span>
                    </div>
                  ) : (
                    <div className="text-3xl font-bold text-white">Custom</div>
                  )}
                  {annual && price !== null && (
                    <div className="text-[12px] mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
                      Billed annually
                    </div>
                  )}
                </div>

                <p
                  className="text-[13px] mb-6 leading-relaxed"
                  style={{ color: 'rgba(255,255,255,0.45)' }}
                >
                  {tier.description}
                </p>

                {tier.cta === 'Contact Sales' ? (
                  <button
                    onClick={() => openContact()}
                    className="w-full py-3 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 transition-all mb-8"
                    style={{
                      background: 'rgba(255,255,255,0.08)',
                      color: 'white',
                      border: '1px solid rgba(255,255,255,0.12)',
                    }}
                  >
                    {tier.cta} <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    className="w-full py-3 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 transition-all mb-8"
                    style={{
                      background: tier.highlight ? ACCENT : 'rgba(255,255,255,0.08)',
                      color: 'white',
                      border: tier.highlight ? 'none' : '1px solid rgba(255,255,255,0.12)',
                    }}
                  >
                    {tier.cta} <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}

                <div className="space-y-2.5 flex-1">
                  {tier.features.map((f) => (
                    <div
                      key={f}
                      className="flex items-start gap-2.5 text-[13px]"
                      style={{ color: 'rgba(255,255,255,0.7)' }}
                    >
                      <CheckCircle
                        className="w-4 h-4 mt-0.5 flex-shrink-0"
                        style={{ color: ACCENT }}
                      />
                      {f}
                    </div>
                  ))}
                  {tier.notIncluded.map((f) => (
                    <div
                      key={f}
                      className="flex items-start gap-2.5 text-[13px]"
                      style={{ color: 'rgba(255,255,255,0.22)' }}
                    >
                      <X className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      {f}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 text-center max-w-3xl mx-auto">
          {[
            { label: 'Access by request', desc: 'Vetted onboarding process. No open sign-up.' },
            {
              label: 'Air-gap ready',
              desc: 'On-premises deployment available for classified environments.',
            },
            { label: 'StateRAMP pathway', desc: 'Compliance-first architecture from the ground up.' },
          ].map((item) => (
            <div key={item.label}>
              <div className="text-[14px] font-semibold text-white mb-1">{item.label}</div>
              <div className="text-[12px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
                {item.desc}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
