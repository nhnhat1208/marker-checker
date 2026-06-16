import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Users, Zap, ShieldCheck, GitBranch, UserCheck, ArrowRight } from 'lucide-react'
import MarkerLogo from '@/components/brand/MarkerLogo'
import { cn } from '@/lib/utils'

const ORBIT_FEATURES = [
  {
    icon: MessageSquare,
    title: 'Natural Language',
    desc: 'Describe changes in plain text — no forms, no tickets.',
    detail: 'Write the request the way you already explain it to a teammate, then let the agent structure it for approval.',
    top: '19%',
    left: '3%',
    cardSide: 'right',
    labelClass: '-translate-y-[1px]',
    labelWidthClass: 'max-w-[116px]',
  },
  {
    icon: Zap,
    title: 'AI Parsing',
    desc: 'Extracts object, change, and approver automatically.',
    detail: 'The parser identifies system, action, risk, and likely approvers before the request enters the workflow.',
    top: '11%',
    right: '7%',
    cardSide: 'left',
    labelClass: 'translate-x-[1px] -translate-y-[2px]',
    labelWidthClass: 'max-w-[92px]',
  },
  {
    icon: GitBranch,
    title: 'Auto-route',
    desc: 'Maps each request to the right policy path and approver chain.',
    detail: 'Once the intent is understood, the workflow engine routes the request to the correct gate instead of leaving triage to humans.',
    top: '39%',
    left: '7%',
    cardSide: 'right',
    labelClass: 'translate-y-[1px]',
    labelWidthClass: 'max-w-[92px]',
  },
  {
    icon: UserCheck,
    title: 'Human Approval',
    desc: 'Keeps the final decision with people, not just automation.',
    detail: 'Approvers still make the call. The system only prepares the context, collects signals, and makes the decision easier to trust.',
    top: '49%',
    right: '12%',
    cardSide: 'left',
    labelClass: 'translate-x-[2px]',
    labelWidthClass: 'max-w-[108px]',
  },
  {
    icon: Users,
    title: 'Multi-channel',
    desc: 'Approvers act via Telegram or Web UI, seamlessly.',
    detail: 'People can approve where they already work, instead of switching tools just to unblock a request.',
    top: '74%',
    left: '4%',
    cardSide: 'right',
    labelClass: 'translate-y-[2px]',
    labelWidthClass: 'max-w-[104px]',
  },
  {
    icon: ShieldCheck,
    title: 'Audit Trail',
    desc: 'Every decision logged with full history in PostgreSQL.',
    detail: 'Every message, approver action, and final outcome stays traceable for reviews, incident follow-up, and compliance.',
    top: '77%',
    right: '3%',
    cardSide: 'left',
    labelClass: 'translate-x-[1px] translate-y-[1px]',
    labelWidthClass: 'max-w-[86px]',
  },
]

/* ─ Google "G" logo ─────────────────────────────────────────────────── */
function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" aria-hidden>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  )
}

/* ─ Animated 3-D scene ───────────────────────────────────────────────── */
function AgentScene() {
  const [hoveredFeature, setHoveredFeature] = useState<string | null>(null)
  const [pinnedFeature, setPinnedFeature] = useState<string | null>(null)
  const [sequenceFeature, setSequenceFeature] = useState<string | null>(null)
  const [hasInteracted, setHasInteracted] = useState(false)
  const [isCoreHovered, setIsCoreHovered] = useState(false)

  const activeFeature = hoveredFeature ?? pinnedFeature ?? sequenceFeature
  const activeFeatureData = ORBIT_FEATURES.find(feature => feature.title === activeFeature) ?? null
  const ActiveFeatureIcon = activeFeatureData?.icon

  useEffect(() => {
    if (hasInteracted) {
      setSequenceFeature(null)
      return
    }

    const introDelay = 1400
    const stepDuration = 1800
    const timers = ORBIT_FEATURES.map((feature, index) =>
      window.setTimeout(() => setSequenceFeature(feature.title), introDelay + index * stepDuration)
    )
    const clearTimer = window.setTimeout(
      () => setSequenceFeature(null),
      introDelay + ORBIT_FEATURES.length * stepDuration + 500,
    )

    return () => {
      timers.forEach(timer => window.clearTimeout(timer))
      window.clearTimeout(clearTimer)
    }
  }, [hasInteracted])

  return (
    <div className="relative flex items-center justify-center w-full h-full select-none overflow-hidden">

      {/* CSS keyframes */}
      <style>{`
        @keyframes radar   { 0% { transform: scale(.4); opacity: .7; } 100% { transform: scale(3.2); opacity: 0; } }
        @keyframes core-float {
          0%,100% { transform: translateY(0px) scale(1); }
          50%     { transform: translateY(-10px) scale(1.015); }
        }
        @keyframes chip-float {
          0%,100% { transform: translateY(0px); }
          50%     { transform: translateY(-9px); }
        }
        @keyframes node-enter {
          0%   { opacity: 0; filter: blur(8px); }
          100% { opacity: 1; filter: blur(0); }
        }
        @keyframes star-breathe {
          0%,100% { transform: scale(1); opacity: .55; }
          50%     { transform: scale(1.14); opacity: 1; }
        }
        @keyframes beacon {
          0%,100% { opacity: .55; transform: scale(1); }
          50%     { opacity: 1; transform: scale(1.18); }
        }
        @keyframes glow-breathe {
          0%,100% { opacity: .35; transform: scale(1); }
          50%     { opacity: .65; transform: scale(1.08); }
        }
        @keyframes cta-glow {
          0%,100% { opacity: .45; transform: scale(1); }
          50%     { opacity: .9; transform: scale(1.015); }
        }
        @keyframes cta-shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        @keyframes arrow-nudge {
          0%,100% { transform: translateX(0); }
          50%     { transform: translateX(4px); }
        }
      `}</style>

      {/* Grid */}
      <div className="pointer-events-none absolute inset-0 opacity-25" style={{
        backgroundImage:
          'linear-gradient(rgba(99,179,237,.2) 1px,transparent 1px),' +
          'linear-gradient(90deg,rgba(99,179,237,.2) 1px,transparent 1px)',
        backgroundSize: '44px 44px',
        maskImage: 'radial-gradient(ellipse 85% 75% at 50% 50%, black 30%, transparent 100%)',
      }} />

      {/* Ambient glow */}
      <div className="pointer-events-none absolute w-[48rem] h-[48rem] rounded-full bg-blue-500/18 blur-3xl" style={{ animation: 'glow-breathe 6s ease-in-out infinite' }} />
      <div className="pointer-events-none absolute w-80 h-80 rounded-full bg-indigo-500/22 blur-2xl" style={{ animation: 'glow-breathe 5s ease-in-out infinite reverse' }} />

      {/* Background beacons */}
      {[
        { top: '18%', left: '22%', size: 5, color: '#38bdf8', delay: '0s' },
        { top: '27%', left: '68%', size: 4, color: '#60a5fa', delay: '.8s' },
        { top: '42%', left: '16%', size: 4, color: '#a78bfa', delay: '1.6s' },
        { top: '64%', left: '72%', size: 5, color: '#34d399', delay: '2.2s' },
        { top: '74%', left: '30%', size: 4, color: '#67e8f9', delay: '.4s' },
        { top: '82%', left: '58%', size: 3, color: '#818cf8', delay: '1.2s' },
        { top: '14%', left: '52%', size: 4, color: '#38bdf8', delay: '.3s' },
        { top: '30%', left: '82%', size: 3, color: '#93c5fd', delay: '1.9s' },
        { top: '58%', left: '86%', size: 4, color: '#60a5fa', delay: '2.5s' },
        { top: '80%', left: '76%', size: 5, color: '#34d399', delay: '.9s' },
        { top: '88%', left: '60%', size: 3, color: '#818cf8', delay: '1.5s' },
        { top: '78%', left: '18%', size: 4, color: '#67e8f9', delay: '.7s' },
      ].map(node => (
        <div
          key={`${node.top}-${node.left}`}
          className="pointer-events-none absolute rounded-full"
          style={{
            top: node.top,
            left: node.left,
            width: node.size,
            height: node.size,
            background: node.color,
            boxShadow: `0 0 ${node.size * 4}px ${node.color}`,
            animation: `beacon 3.2s ease-in-out ${node.delay} infinite`,
          }}
        />
      ))}

      {/* Radar pulses */}
      {[0, 1.5, 3].map(delay => (
        <div key={delay} className="pointer-events-none absolute w-24 h-24 rounded-full border border-blue-400/40"
          style={{ animation: `radar 4s ease-out ${delay}s infinite` }} />
      ))}

      {/* Orbit ring 0 — far halo */}
      <Ring
        size={624}
        dur="44s"
        activeDur="33s"
        dir="orbit-r"
        color="rgba(148,163,184,.11)"
        active={isCoreHovered}
      >
        <Dot top="10%" left="20%" color="#38bdf8" size={5} />
        <Dot top="16%" left="76%" color="#93c5fd" size={4} />
        <Dot top="76%" left="16%" color="#818cf8" size={4} />
        <Dot top="84%" left="74%" color="#34d399" size={5} />
      </Ring>

      {/* Orbit ring 0 — far halo */}
      <Ring
        size={528}
        dur="38s"
        activeDur="29s"
        dir="orbit-r"
        color="rgba(148,163,184,.12)"
        active={isCoreHovered}
      >
        <Dot top="8%" left="24%" color="#38bdf8" size={5} />
        <Dot top="24%" left="78%" color="#60a5fa" size={6} />
        <Dot top="72%" left="14%" color="#a78bfa" size={4} />
        <Dot top="84%" left="70%" color="#34d399" size={5} />
      </Ring>

      {/* Orbit ring 1 — outermost, slow CW */}
      <Ring
        size={484}
        dur="34s"
        activeDur="25s"
        dir="orbit"
        color="rgba(96,165,250,.16)"
        active={isCoreHovered}
      >
        <Dot top="0" left="50%" ml="-5px" color="#60a5fa" size={10} />
        <Dot top="24%" left="83%" color="#93c5fd" size={7} />
        <Dot top="54%" left="6%" mt="-4px" color="#67e8f9" size={6} />
        <Dot top="82%" left="80%" color="#818cf8" size={7} />
        <Dot top="92%" left="28%" color="#34d399" size={5} />
      </Ring>

      {/* Orbit ring 2 — medium, CCW */}
      <Ring
        size={378}
        dur="24s"
        activeDur="17s"
        dir="orbit-r"
        color="rgba(129,140,248,.18)"
        active={isCoreHovered}
      >
        <Dot top="0" left="50%" ml="-4px" color="#a78bfa" size={8} />
        <Dot top="18%" left="18%" color="#38bdf8" size={6} />
        <Dot top="50%" left="0" mt="-4px" color="#34d399" size={7} />
        <Dot top="66%" left="84%" color="#f9a8d4" size={6} />
        <Dot top="100%" left="50%" ml="-3px" mt="-6px" color="#67e8f9" size={6} />
      </Ring>

      {/* Orbit ring 3 — inner, fast CW */}
      <Ring
        size={276}
        dur="15s"
        activeDur="11s"
        dir="orbit"
        color="rgba(167,139,250,.2)"
        active={isCoreHovered}
      >
        <Dot top="0" left="50%" ml="-4px" color="#c084fc" size={8} />
        <Dot top="28%" left="12%" color="#34d399" size={5} />
        <Dot top="50%" left="100%" mt="-4px" ml="-8px" color="#f472b6" size={6} />
        <Dot top="84%" left="28%" color="#60a5fa" size={5} />
      </Ring>

      {/* Center anchor */}
      <div
        className="relative z-10"
        onMouseEnter={() => {
          setHasInteracted(true)
          setIsCoreHovered(true)
        }}
        onMouseLeave={() => setIsCoreHovered(false)}
      >
        <div
          className="relative flex h-[15.5rem] w-[15.5rem] flex-col items-center justify-center rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(59,130,246,.22) 0%, rgba(37,99,235,.14) 24%, rgba(15,23,42,.18) 52%, rgba(15,23,42,.04) 76%, rgba(15,23,42,0) 88%)',
            boxShadow: '0 0 54px rgba(59,130,246,.18), inset 0 0 46px rgba(96,165,250,.08)',
          }}
        >
          <div
            className="absolute left-1/2 top-1/2 h-[8.8rem] w-[8.8rem] -translate-x-1/2 -translate-y-[58%] rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(96,165,250,.18) 0%, rgba(37,99,235,.12) 34%, rgba(15,23,42,.08) 70%, rgba(15,23,42,0) 100%)',
              boxShadow: 'inset 0 0 28px rgba(147,197,253,.08), 0 0 32px rgba(59,130,246,.14)',
            }}
          />

          <div className="relative z-10 flex flex-col items-center">
            <MarkerLogo
              className="h-[6.85rem] w-[6.85rem]"
              title="Marker Checker"
              style={{
                animation: 'core-float 5s ease-in-out infinite',
                filter: 'drop-shadow(0 0 72px rgba(59,130,246,.82)) drop-shadow(0 24px 68px rgba(0,0,0,.52))',
              }}
            />

            <div className="mt-5 text-center">
              <div className="text-[12px] font-semibold uppercase tracking-[0.28em] text-white [text-shadow:0_0_22px_rgba(255,255,255,.26)]">
                AI Approval
              </div>
              <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-sky-100 [text-shadow:0_0_18px_rgba(96,165,250,.34)]">
                Workflow Agent
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Orbit feature nodes */}
      {ORBIT_FEATURES.map((feature, index) => {
        const Icon = feature.icon
        const isActive = activeFeature === feature.title
        const labelOnLeft = feature.cardSide === 'left'

        return (
          <div
            key={feature.title}
            className="absolute z-20"
            style={{
              top: feature.top,
              left: feature.left,
              right: feature.right,
              animation: `node-enter .55s cubic-bezier(.22,1,.36,1) ${0.2 + index * 0.16}s both, chip-float 4.8s ease-in-out ${index * 0.7}s infinite`,
            }}
            onMouseEnter={() => {
              setHasInteracted(true)
              setHoveredFeature(feature.title)
            }}
            onMouseLeave={() => setHoveredFeature(current => (current === feature.title ? null : current))}
          >
            <button
              type="button"
              aria-pressed={pinnedFeature === feature.title}
              className={cn(
                'group relative flex items-center gap-3 text-left transition-all duration-300',
                labelOnLeft ? 'flex-row-reverse' : 'flex-row',
                'focus-visible:outline-none',
                isActive && 'scale-[1.08]',
              )}
              onFocus={() => {
                setHasInteracted(true)
                setHoveredFeature(feature.title)
              }}
              onBlur={() => setHoveredFeature(current => (current === feature.title ? null : current))}
              onClick={() => {
                setHasInteracted(true)
                setHoveredFeature(null)
                setPinnedFeature(current => (current === feature.title ? null : feature.title))
              }}
              aria-label={feature.title}
            >
              <span className={cn(
                'flex items-center gap-2',
                labelOnLeft ? 'flex-row-reverse text-right' : 'flex-row text-left',
                feature.labelClass,
              )}>
                <span className={cn(
                  'h-px w-7 transition-colors duration-300',
                  isActive ? 'bg-blue-200/80' : 'bg-white/25',
                )} />
                <span
                  className={cn(
                    'text-[11px] font-medium leading-[1.15rem] transition-colors duration-300',
                    feature.labelWidthClass,
                    isActive ? 'text-blue-50' : 'text-blue-100/70',
                  )}
                >
                  {feature.title}
                </span>
              </span>

              <span className="relative flex h-12 w-12 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:ring-blue-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent">
                <span
                  className={cn(
                    'pointer-events-none absolute inset-[-12px] rounded-full transition-opacity duration-300',
                    isActive ? 'opacity-100' : 'opacity-50',
                  )}
                  style={{
                    background: 'radial-gradient(circle, rgba(96,165,250,.26) 0%, rgba(96,165,250,.12) 34%, rgba(96,165,250,0) 74%)',
                    animation: 'star-breathe 3.6s ease-in-out infinite',
                  }}
                />
                <span
                  className={cn(
                    'pointer-events-none absolute inset-0 rounded-full transition-all duration-300',
                    isActive
                      ? 'bg-slate-950/24 ring-[2px] ring-blue-100/60'
                      : 'bg-slate-950/18 ring-[2px] ring-white/24',
                  )}
                />
                <span
                  className={cn(
                    'pointer-events-none absolute inset-[5px] rounded-full transition-all duration-300',
                    isActive
                      ? 'shadow-[0_0_24px_rgba(96,165,250,.92)]'
                      : 'shadow-[0_0_16px_rgba(96,165,250,.52)]',
                  )}
                  style={{
                    background: isActive
                      ? 'radial-gradient(circle at 32% 30%, rgba(224,242,254,.98) 0%, rgba(96,165,250,.98) 34%, rgba(37,99,235,.98) 68%, rgba(30,64,175,1) 100%)'
                      : 'radial-gradient(circle at 32% 30%, rgba(224,242,254,.92) 0%, rgba(96,165,250,.92) 34%, rgba(37,99,235,.9) 68%, rgba(30,64,175,.98) 100%)',
                  }}
                />
                <Icon className="relative h-4 w-4 text-white drop-shadow-[0_1px_8px_rgba(255,255,255,.35)]" />
              </span>
            </button>

            <div
              className={cn(
                'pointer-events-none absolute top-1/2 z-30 hidden w-64 -translate-y-1/2 rounded-2xl border p-4 text-left shadow-[0_24px_60px_rgba(2,6,23,.48)] transition-all duration-200 lg:block',
                'border-slate-700/80 bg-[linear-gradient(180deg,rgba(2,6,23,.98),rgba(15,23,42,.985))]',
                feature.cardSide === 'right' ? 'left-full ml-4 origin-left' : 'right-full mr-4 origin-right',
                isActive ? 'translate-y-[-50%] scale-100 opacity-100' : 'translate-y-[-46%] scale-95 opacity-0',
              )}
            >
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-200/85">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-400/12 ring-1 ring-blue-300/18">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                Orbit signal
              </div>
              <div className="mt-3 text-sm font-semibold text-white">
                {feature.title}
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-200">
                {feature.detail}
              </p>
              <p className="mt-3 text-xs leading-5 text-slate-400">
                {feature.desc}
              </p>
            </div>
          </div>
        )
      })}

      {/* Mobile detail card */}
      {activeFeatureData && ActiveFeatureIcon && (
        <div className="absolute inset-x-4 bottom-16 z-30 rounded-2xl border border-slate-700/80 bg-[linear-gradient(180deg,rgba(2,6,23,.98),rgba(15,23,42,.985))] p-4 text-left shadow-[0_24px_60px_rgba(2,6,23,.48)] lg:hidden">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-200/85">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-400/12 ring-1 ring-blue-300/18">
              <ActiveFeatureIcon className="h-3.5 w-3.5" />
            </span>
            Orbit signal
          </div>
          <div className="mt-3 text-sm font-semibold text-white">
            {activeFeatureData.title}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            {activeFeatureData.detail}
          </p>
          <p className="mt-3 text-xs leading-5 text-slate-400">
            {activeFeatureData.desc}
          </p>
        </div>
      )}

    </div>
  )
}

/* Orbit ring wrapper */
function Ring({ size, dur, activeDur, dir, color, active, children }: {
  size: number
  dur: string
  activeDur?: string
  dir: string
  color: string
  active?: boolean
  children: React.ReactNode
}) {
  const ringRef = useRef<HTMLDivElement | null>(null)
  const angleRef = useRef(0)
  const speedRef = useRef(0)
  const targetSpeedRef = useRef(0)
  const lastTsRef = useRef<number | null>(null)

  const toSeconds = (value: string) => {
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
  }

  const direction = dir === 'orbit-r' ? -1 : 1
  const baseSpeed = direction * (360 / toSeconds(dur))
  const hoverSpeed = direction * (360 / toSeconds(activeDur ?? dur))

  useEffect(() => {
    speedRef.current = baseSpeed
    targetSpeedRef.current = baseSpeed
  }, [baseSpeed])

  useEffect(() => {
    targetSpeedRef.current = active ? hoverSpeed : baseSpeed
  }, [active, baseSpeed, hoverSpeed])

  useEffect(() => {
    const ringNode = ringRef.current

    if (!ringNode) {
      return
    }

    let frameId = 0

    const tick = (timestamp: number) => {
      if (lastTsRef.current == null) {
        lastTsRef.current = timestamp
      }

      const deltaSeconds = Math.min((timestamp - lastTsRef.current) / 1000, 0.05)
      lastTsRef.current = timestamp

      speedRef.current += (targetSpeedRef.current - speedRef.current) * Math.min(1, deltaSeconds * 4.5)
      angleRef.current = (angleRef.current + speedRef.current * deltaSeconds + 360) % 360
      ringNode.style.transform = `rotate(${angleRef.current}deg)`

      frameId = window.requestAnimationFrame(tick)
    }

    frameId = window.requestAnimationFrame(tick)

    return () => {
      window.cancelAnimationFrame(frameId)
      lastTsRef.current = null
    }
  }, [])

  return (
    <div
      ref={ringRef}
      className="pointer-events-none absolute rounded-full"
      style={{
        width: size,
        height: size,
        border: `1px solid ${color}`,
        willChange: 'transform',
        transform: 'rotate(0deg)',
        transformOrigin: 'center',
      }}
    >
      {children}
    </div>
  )
}

/* Dot node on a ring */
function Dot({ top, left, mt, ml, color, size }: {
  top?: string | number; left?: string | number
  mt?: string; ml?: string
  color: string; size: number
}) {
  return (
    <div className="pointer-events-none absolute rounded-full" style={{
      width: size, height: size,
      background: color,
      boxShadow: `0 0 ${size * 2}px ${color}`,
      top: top ?? 'auto', left: left ?? 'auto',
      marginTop: mt, marginLeft: ml,
    }} />
  )
}

/* ─ Main page ───────────────────────────────────────────────────────── */
export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col lg:flex-row">

      {/* ── Left 60 %: scene ── */}
      <div className="relative lg:w-[57%] min-h-[48vh] lg:min-h-screen overflow-hidden"
        style={{ background: 'linear-gradient(145deg,#080f1e 0%,#0d1d3a 45%,#0a1628 100%)' }}>
        <AgentScene />
      </div>

      {/* ── Right 40 %: content ── */}
      <div className="lg:w-[43%] flex items-center justify-center px-8 py-14 bg-white">
        <div className="w-full max-w-[430px]">

          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-7">
            <MarkerLogo className="h-8 w-8" title="Marker Checker" />
            <span className="font-semibold text-gray-900 text-sm tracking-tight">Marker Checker</span>
          </div>

          {/* Headline */}
          <h1 className="text-[1.85rem] font-bold text-gray-900 leading-tight mb-3">
            Approval workflows,<br />
            <span className="text-blue-600">powered by AI.</span>
          </h1>

          {/* Summary */}
          <p className="text-slate-500 text-[15px] leading-8 mb-8">
            Describe any system change in plain text. Marker Checker parses your intent,
            routes it to the right approver, and keeps a full audit trail — all without
            leaving your existing workflow.
          </p>

          {/* CTA */}
          <div>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700">
                <span
                  className="inline-flex h-2 w-2 rounded-full bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,.35)]"
                  style={{ animation: 'beacon 1.8s ease-in-out infinite' }}
                />
                Start here
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                Secure sign-in
              </span>
            </div>

            <div className="relative">
              <div
                className="pointer-events-none absolute inset-x-4 -inset-y-1 rounded-[1.5rem] bg-blue-100/40 blur-2xl"
                style={{ animation: 'cta-glow 2.8s ease-in-out infinite' }}
              />
              <div
                className="pointer-events-none absolute -inset-px rounded-[1.35rem] opacity-50"
                style={{
                  background: 'linear-gradient(110deg, rgba(96,165,250,0) 0%, rgba(96,165,250,.1) 42%, rgba(255,255,255,.95) 50%, rgba(96,165,250,.1) 58%, rgba(96,165,250,0) 100%)',
                  backgroundSize: '220% 100%',
                  animation: 'cta-shimmer 5s linear infinite',
                }}
              />

              <a
                href="/auth/google"
                className={cn(
                  'group relative flex items-center gap-4 w-full min-h-[4.5rem] px-5 py-4 rounded-[1.35rem]',
                  'border border-slate-200/90 bg-gradient-to-r from-white via-slate-50/70 to-blue-50/70',
                  'text-slate-900 shadow-[0_18px_34px_rgba(15,23,42,.08)] hover:border-blue-300 hover:shadow-[0_20px_40px_rgba(37,99,235,.12)]',
                  'transition-all duration-200 active:scale-[.985]',
                )}
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-200">
                  <GoogleLogo />
                </span>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-[15px] font-semibold">
                    Continue with Google
                  </div>
                  <div className="mt-0.5 text-[12px] font-medium text-slate-500">
                    Access chat and approval history
                  </div>
                </div>

                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600/8 ring-1 ring-blue-100 transition-colors group-hover:bg-blue-600/12 group-hover:ring-blue-200">
                  <ArrowRight
                    className="h-4 w-4 text-blue-600"
                    style={{ animation: 'arrow-nudge 1.8s ease-in-out infinite' }}
                  />
                </span>
              </a>
            </div>

            <p className="mt-3 text-center text-xs text-slate-500">
              Any Google account · no allowlist required
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}
