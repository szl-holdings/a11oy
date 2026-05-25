import { getKernel } from '@szl/alloy/prompts';
import { BookOpen, Brain, Mic, Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';

export function AlloyKernelPanel() {
  const kernel = useMemo(() => getKernel('voice-to-action'), []);
  const [showExample, setShowExample] = useState(false);
  const example = kernel.codex.examples[0];

  return (
    <div
      className="rounded-xl p-5 mt-6"
      style={{ border: '1px solid rgba(74,144,184,0.2)', background: 'rgba(74,144,184,0.03)' }}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'rgba(74,144,184,0.12)', border: '1px solid rgba(74,144,184,0.25)' }}
          >
            <Brain className="w-4 h-4" style={{ color: '#4a90b8' }} />
          </div>
          <div>
            <div className="text-sm font-bold text-white">Voice Command Parser</div>
            <div className="text-[10px] font-mono" style={{ color: 'rgba(74,144,184,0.6)' }}>
              Continuum Codex · {kernel.name} · v{kernel.version}
            </div>
          </div>
        </div>
        <span
          className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider"
          style={{
            background: 'rgba(74,144,184,0.1)',
            border: '1px solid rgba(74,144,184,0.25)',
            color: '#4a90b8',
          }}
        >
          {kernel.pattern}
        </span>
      </div>

      <div className="space-y-3 mb-4">
        <div
          className="rounded-lg p-3"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div
            className="text-[10px] font-mono uppercase tracking-wider mb-1.5 flex items-center gap-1"
            style={{ color: 'rgba(74,144,184,0.6)' }}
          >
            <Mic className="w-3 h-3" /> Role
          </div>
          <p className="text-xs text-white/70 leading-relaxed">{kernel.codex.role}</p>
        </div>

        <div
          className="rounded-lg p-3"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div
            className="text-[10px] font-mono uppercase tracking-wider mb-1.5 flex items-center gap-1"
            style={{ color: 'rgba(74,144,184,0.6)' }}
          >
            <Sparkles className="w-3 h-3" /> Contract
          </div>
          <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>
            {kernel.codex.contract}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-1">
          {kernel.inspirations.map((i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 rounded text-[9px] font-mono"
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.4)',
              }}
            >
              {i}
            </span>
          ))}
        </div>
        {example && (
          <button
            onClick={() => setShowExample((v) => !v)}
            className="flex items-center gap-1 text-[10px] font-mono transition-colors"
            style={{ color: '#4a90b8' }}
          >
            <BookOpen className="w-3 h-3" />
            {showExample ? 'Hide' : 'View'} example
          </button>
        )}
      </div>

      {showExample && example && (
        <div
          className="mt-3 rounded-lg p-3"
          style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(74,144,184,0.1)' }}
        >
          <div
            className="text-[10px] font-mono uppercase tracking-wider mb-2"
            style={{ color: 'rgba(74,144,184,0.4)' }}
          >
            Example: {example.description}
          </div>
          <pre
            className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono overflow-hidden max-h-48 overflow-y-auto"
            style={{ color: 'rgba(255,255,255,0.4)' }}
          >
            {example.output}
          </pre>
        </div>
      )}
    </div>
  );
}
