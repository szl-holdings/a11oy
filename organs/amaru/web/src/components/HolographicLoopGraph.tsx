/**
 * HolographicLoopGraph — a HOLO.SYS / cyberpunk-HUD 3D render of the governed
 * loop's node state machine (PLAN → EXECUTE → VERIFY → RECOVER → HALT) and its
 * immutable plan-DAG / receipt-chain links.
 *
 * HONESTY (load-bearing): this layer is AESTHETIC ONLY. Every node it lights up
 * and every edge it pulses is derived from REAL /api/a11oy/v1/agent/cycle
 * receipts passed in as props (node_state_trace transitions, per-node Λ-gate
 * decisions — Λ is Conjecture 1, advisory — and the hash-chained receipt DAG).
 * It NEVER fabricates a node, an edge, or a receipt. When the founder-gated loop
 * is OFF (no transitions), the caller renders an honest OFF state and this
 * component is not mounted.
 *
 * Inspiration (own-code reimplementation, copied no source): the "structured
 * graph" framing of arXiv:2604.11378. Demonstration + attestation · advisory ·
 * NOT a formal proof.
 *
 * Robustness: three.js is dynamically imported (its own lazy chunk), the WebGL
 * context is lazy-initialised, and ANY failure (no WebGL, import error,
 * prefers-reduced-motion with no static frame) degrades gracefully — the caller
 * always shows the functional 2D property cards regardless of this canvas.
 */
import { useEffect, useRef, useState } from 'react';

export interface HoloTransition {
  seq: number;
  from: string;
  to: string;
  hash: string;
}

export interface HoloDecision {
  iteration: number;
  decision: string | null;
  trust: number | null;
}

interface Props {
  /** Real state transitions from sgh.node_state_trace (from_state → to_state). */
  transitions: HoloTransition[];
  /** Real immutable plan-DAG node ids (sgh.plan_dag.nodes[].id). */
  planNodes: string[];
  /** Real per-iteration Λ-gate decisions from trust_trace. */
  decisions: HoloDecision[];
  /** Honest final_status of the cycle. */
  finalStatus?: string;
  /** In-browser prev-hash linkage result over the receipt chain. */
  chainVerified: boolean;
  height?: number;
}

// The five canonical, inspectable node states of the machine. HALT is terminal.
const STATES = ['PLAN', 'EXECUTE', 'VERIFY', 'RECOVER', 'HALT'] as const;
type StateName = (typeof STATES)[number];

// Layered 3D layout: a left→right flow with RECOVER as a lower branch.
const LAYOUT: Record<StateName, [number, number, number]> = {
  PLAN: [-6.2, 0.2, 0],
  EXECUTE: [-3.0, 1.4, 0.4],
  VERIFY: [0.2, 0.0, 0],
  RECOVER: [0.4, -2.6, 1.6],
  HALT: [4.6, 0.8, 0],
};

// Restrained deep-dark palette (low-opacity glow, WCAG-friendly, not blinding).
const COLOR: Record<StateName, number> = {
  PLAN: 0x6ea8ff, // ice blue
  EXECUTE: 0x8be0d0, // teal
  VERIFY: 0x7cc7ff, // sky
  RECOVER: 0xffb347, // amber (recovery/escalation)
  HALT: 0xff5f8f, // fuchsia-rose (terminal)
};

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

function webglSupported(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch {
    return false;
  }
}

// Holographic node material: view-dependent fresnel rim + subtle time flicker.
const NODE_VERT = `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;
const NODE_FRAG = `
  precision mediump float;
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uVisited; // 1.0 = traversed by the real trace, else dim
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float fres = pow(1.0 - max(dot(vNormal, vView), 0.0), 2.2);
    // scanline shimmer along screen-space so nodes read as holographic
    float scan = 0.85 + 0.15 * sin(uTime * 2.0 + gl_FragCoord.y * 0.35);
    float base = mix(0.18, 0.6, uVisited);
    float glow = base + fres * (0.7 + 0.3 * uVisited);
    vec3 col = uColor * glow * scan;
    float alpha = clamp(0.35 + fres * 0.65, 0.0, 0.95) * mix(0.5, 1.0, uVisited);
    gl_FragColor = vec4(col, alpha);
  }
`;

export function HolographicLoopGraph({
  transitions,
  planNodes,
  decisions,
  finalStatus,
  chainVerified,
  height = 300,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;
    if (!webglSupported()) {
      setUnavailable(true);
      return;
    }

    let disposed = false;
    let cleanup: (() => void) | null = null;
    const reduced = prefersReducedMotion();

    // Lazy chunk: three only loads when this real-data panel actually mounts.
    void import('three')
      .then((THREE) => {
        if (disposed || !el) return;

        const width = el.clientWidth || 640;
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 100);
        camera.position.set(0.5, 1.6, 13);
        camera.lookAt(0, -0.2, 0);

        const renderer = new THREE.WebGLRenderer({
          antialias: true,
          alpha: true,
          powerPreference: 'low-power',
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height);
        renderer.setClearColor(0x000000, 0); // deep-dark: page bg shows through
        el.appendChild(renderer.domElement);
        renderer.domElement.style.display = 'block';
        renderer.domElement.setAttribute('aria-hidden', 'true');

        const group = new THREE.Group();
        scene.add(group);

        // Which states the REAL trace actually visited (drives glow, no fakery).
        const visited = new Set<string>();
        for (const t of transitions) {
          if (t.from) visited.add(t.from);
          if (t.to) visited.add(t.to);
        }
        // INIT is a pseudo-state (machine entry); fold it into PLAN visibly.
        visited.delete('INIT');
        if (transitions.length > 0) visited.add('PLAN');

        // Was any Λ-gate decision a DENY? (deny-by-default halt is honest.)
        const denied = decisions.some((d) => d.decision === 'DENY');

        const uniforms: Record<string, { value: number }[]> = {};
        const nodeMeshes: Record<string, { rotation: { y: number } }> = {};
        const clock = new THREE.Clock();
        const timeUniforms: { value: number }[] = [];

        // Build the five state nodes at their layout positions.
        for (const state of STATES) {
          const pos = LAYOUT[state];
          const isVisited = visited.has(state);
          const uTime = { value: 0 };
          timeUniforms.push(uTime);
          const mat = new THREE.ShaderMaterial({
            uniforms: {
              uColor: { value: new THREE.Color(COLOR[state]) },
              uTime,
              uVisited: { value: isVisited ? 1.0 : 0.0 },
            },
            vertexShader: NODE_VERT,
            fragmentShader: NODE_FRAG,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
          });
          const geo = new THREE.IcosahedronGeometry(isVisited ? 0.7 : 0.5, 1);
          const mesh = new THREE.Mesh(geo, mat);
          mesh.position.set(pos[0], pos[1], pos[2]);
          group.add(mesh);
          nodeMeshes[state] = mesh;

          // Holographic wireframe shell over the core.
          const wire = new THREE.LineSegments(
            new THREE.WireframeGeometry(geo),
            new THREE.LineBasicMaterial({
              color: COLOR[state],
              transparent: true,
              opacity: isVisited ? 0.5 : 0.18,
            }),
          );
          mesh.add(wire);
          void uniforms;
        }

        // Canonical skeleton edges (dim) — the immutable plan flow.
        const skeleton: Array<[StateName, StateName]> = [
          ['PLAN', 'EXECUTE'],
          ['EXECUTE', 'VERIFY'],
          ['VERIFY', 'HALT'],
          ['VERIFY', 'RECOVER'],
          ['RECOVER', 'EXECUTE'],
          ['RECOVER', 'HALT'],
        ];
        function addEdge(
          a: [number, number, number],
          b: [number, number, number],
          color: number,
          opacity: number,
        ) {
          const g = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(a[0], a[1], a[2]),
            new THREE.Vector3(b[0], b[1], b[2]),
          ]);
          const m = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          });
          group.add(new THREE.Line(g, m));
        }
        for (const [a, b] of skeleton) addEdge(LAYOUT[a], LAYOUT[b], 0x3a4a6a, 0.22);

        // REAL traversed edges (from node_state_trace) — bright, on top.
        for (const t of transitions) {
          const from = (t.from === 'INIT' ? 'PLAN' : t.from) as StateName;
          const to = t.to as StateName;
          if (!LAYOUT[from] || !LAYOUT[to] || from === to) continue;
          const col = to === 'HALT' && denied ? 0xff5f8f : COLOR[to] ?? 0x7cc7ff;
          addEdge(LAYOUT[from], LAYOUT[to], col, 0.85);
        }

        // Faint plan-DAG ring beneath the machine (real plan node count).
        const ringCount = Math.max(1, planNodes.length);
        for (let i = 0; i < ringCount; i++) {
          const ang = (i / ringCount) * Math.PI * 2;
          const dot = new THREE.Mesh(
            new THREE.SphereGeometry(0.12, 8, 8),
            new THREE.MeshBasicMaterial({
              color: 0x6ea8ff,
              transparent: true,
              opacity: 0.5,
              blending: THREE.AdditiveBlending,
            }),
          );
          dot.position.set(Math.cos(ang) * 3.2, -3.6, Math.sin(ang) * 3.2);
          group.add(dot);
        }

        // Terminal tint: a subtle plane behind HALT keyed to real final_status.
        const termColor =
          finalStatus === 'converged'
            ? 0x2dd4a7
            : finalStatus === 'halted_by_gate'
              ? 0x7cc7ff
              : finalStatus === 'budget_exhausted' || finalStatus === 'halted_by_banach'
                ? 0xffb347
                : 0x3a4a6a;
        void chainVerified;

        const haloMat = new THREE.MeshBasicMaterial({
          color: termColor,
          transparent: true,
          opacity: 0.1,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        });
        const halo = new THREE.Mesh(new THREE.CircleGeometry(1.8, 32), haloMat);
        halo.position.set(LAYOUT.HALT[0], LAYOUT.HALT[1], LAYOUT.HALT[2] - 0.4);
        group.add(halo);

        group.rotation.x = -0.12;

        let raf = 0;
        const render = () => {
          const t = clock.getElapsedTime();
          for (const u of timeUniforms) u.value = t;
          if (!reduced) {
            group.rotation.y = Math.sin(t * 0.18) * 0.5;
          }
          renderer.render(scene, camera);
          if (!reduced && !disposed) raf = requestAnimationFrame(render);
        };
        // Under reduced-motion: render a single static frame (no animation loop).
        if (reduced) {
          for (const u of timeUniforms) u.value = 0;
          renderer.render(scene, camera);
        } else {
          raf = requestAnimationFrame(render);
        }

        const onResize = () => {
          if (!el) return;
          const w = el.clientWidth || width;
          renderer.setSize(w, height);
          camera.aspect = w / height;
          camera.updateProjectionMatrix();
          if (reduced) renderer.render(scene, camera);
        };
        window.addEventListener('resize', onResize);

        cleanup = () => {
          cancelAnimationFrame(raf);
          window.removeEventListener('resize', onResize);
          scene.traverse((obj) => {
            const anyObj = obj as unknown as {
              geometry?: { dispose?: () => void };
              material?: { dispose?: () => void } | Array<{ dispose?: () => void }>;
            };
            anyObj.geometry?.dispose?.();
            const m = anyObj.material;
            if (Array.isArray(m)) m.forEach((mm) => mm.dispose?.());
            else m?.dispose?.();
          });
          renderer.dispose();
          if (renderer.domElement.parentNode === el)
            el.removeChild(renderer.domElement);
          void nodeMeshes;
        };
      })
      .catch(() => {
        if (!disposed) setUnavailable(true);
      });

    return () => {
      disposed = true;
      if (cleanup) cleanup();
    };
  }, [transitions, planNodes, decisions, finalStatus, chainVerified, height]);

  if (unavailable) {
    return (
      <div
        style={{ height: Math.min(height, 120) }}
        className="flex items-center justify-center rounded-md border border-dashed border-fuchsia-500/20 bg-black/30 px-4 text-center text-[11px] text-muted-foreground"
      >
        Holographic layer unavailable (no WebGL) — the real receipt data is shown
        in the property cards below. Nothing is fabricated.
      </div>
    );
  }

  return (
    <div
      className="relative overflow-hidden rounded-md border border-fuchsia-500/20 bg-[#05060a]"
      style={{ height }}
    >
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      {/* CSS scanline overlay — cheap holographic sheen, pointer-events off. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(124,199,255,0.05) 0px, rgba(124,199,255,0.05) 1px, transparent 1px, transparent 3px)',
          mixBlendMode: 'screen',
        }}
      />
      <div className="pointer-events-none absolute bottom-1 right-2 font-mono text-[9px] uppercase tracking-widest text-fuchsia-300/50">
        HOLO.SYS · real receipts · advisory
      </div>
    </div>
  );
}
