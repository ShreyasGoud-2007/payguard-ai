import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Html, Line } from "@react-three/drei";
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const verificationSteps = [
  "INVOICE RECEIVED",
  "VENDOR VERIFIED",
  "PO MATCH",
  "GOODS RECEIPT",
  "QUANTITY CHECK",
  "PRICE CHECK",
  "DUPLICATE CHECK",
  "RISK ENGINE",
];

const verificationNodes = [
  { label: "VENDOR", position: [-2.6, 1.5, 0.2] },
  { label: "PO MATCH", position: [-1.7, 2.2, 0.6] },
  { label: "GOODS RECEIPT", position: [-0.8, 2.5, 1.1] },
  { label: "QUANTITY", position: [0.7, 2.35, 1.25] },
  { label: "PRICE", position: [1.9, 1.9, 0.9] },
  { label: "DUPLICATE", position: [2.7, 0.85, 0.3] },
  { label: "RISK ENGINE", position: [2.3, -0.85, 0.2] },
];

function usePrefersReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(media.matches);

    updatePreference();
    media.addEventListener("change", updatePreference);

    return () => media.removeEventListener("change", updatePreference);
  }, []);

  return reducedMotion;
}

function useWebGLSupport() {
  const [supportsWebGL, setSupportsWebGL] = useState(true);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl");
      setSupportsWebGL(Boolean(gl));
    } catch {
      setSupportsWebGL(false);
    }
  }, []);

  return supportsWebGL;
}

function NodeBadge({ label, active, position }: { label: string; active: boolean; position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.14, 18, 18]} />
        <meshStandardMaterial
          color={active ? "#b5ff4f" : "#8ba0b5"}
          emissive={active ? "#b5ff4f" : "#1f2a32"}
          emissiveIntensity={active ? 0.9 : 0.25}
        />
      </mesh>
      <Html center distanceFactor={10} position={[0, 0.38, 0]}>
        <div
          className={[
            "rounded-full border px-2 py-1 font-mono text-[9px] uppercase tracking-[0.2em] backdrop-blur-sm",
            active
              ? "border-lime/50 bg-lime/12 text-lime shadow-[0_0_12px_rgba(181,255,79,0.25)]"
              : "border-white/10 bg-slate-900/80 text-slate-300",
          ].join(" ")}
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

function InvoiceDocument({ activeIndex }: { activeIndex: number }) {
  const useGlow = activeIndex >= 0;

  return (
    <Float speed={1.5} rotationIntensity={0.35} floatIntensity={0.55}>
      <group position={[0, 0.1, 0]}>
        <mesh rotation={[0.12, 0.2, 0]}>
          <boxGeometry args={[2.1, 2.8, 0.14]} />
          <meshStandardMaterial
            color={useGlow ? "#dfe7ef" : "#e4ebf3"}
            metalness={0.3}
            roughness={0.3}
            emissive={useGlow ? "#7ae2ff" : "#0b1220"}
            emissiveIntensity={useGlow ? 0.12 : 0.04}
          />
        </mesh>
        <mesh position={[0, 0.18, 0.08]}>
          <boxGeometry args={[1.72, 2.32, 0.04]} />
          <meshStandardMaterial color="#0d1721" roughness={0.9} metalness={0.15} />
        </mesh>
        <mesh position={[-0.58, 0.72, 0.13]}>
          <boxGeometry args={[0.7, 0.12, 0.02]} />
          <meshStandardMaterial color={activeIndex >= 1 ? "#b5ff4f" : "#8699ae"} emissive={activeIndex >= 1 ? "#b5ff4f" : "#0d1721"} emissiveIntensity={0.6} />
        </mesh>
        <mesh position={[-0.58, 0.42, 0.13]}>
          <boxGeometry args={[0.9, 0.1, 0.02]} />
          <meshStandardMaterial color={activeIndex >= 2 ? "#b5ff4f" : "#8699ae"} emissive={activeIndex >= 2 ? "#b5ff4f" : "#0d1721"} emissiveIntensity={0.6} />
        </mesh>
        <mesh position={[-0.66, 0.12, 0.13]}>
          <boxGeometry args={[1.08, 0.1, 0.02]} />
          <meshStandardMaterial color={activeIndex >= 3 ? "#b5ff4f" : "#8699ae"} emissive={activeIndex >= 3 ? "#b5ff4f" : "#0d1721"} emissiveIntensity={0.6} />
        </mesh>
        <mesh position={[-0.38, -0.18, 0.13]}>
          <boxGeometry args={[1.38, 0.1, 0.02]} />
          <meshStandardMaterial color={activeIndex >= 4 ? "#b5ff4f" : "#8699ae"} emissive={activeIndex >= 4 ? "#b5ff4f" : "#0d1721"} emissiveIntensity={0.6} />
        </mesh>
        <mesh position={[-0.56, -0.48, 0.13]}>
          <boxGeometry args={[0.9, 0.1, 0.02]} />
          <meshStandardMaterial color={activeIndex >= 5 ? "#b5ff4f" : "#8699ae"} emissive={activeIndex >= 5 ? "#b5ff4f" : "#0d1721"} emissiveIntensity={0.6} />
        </mesh>
      </group>
    </Float>
  );
}

function VerificationSequence({ reducedMotion }: { reducedMotion: boolean }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const groupRef = useRef<THREE.Group>(null);
  const pointerRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (reducedMotion) {
      setActiveIndex(verificationSteps.length - 1);
      return;
    }

    const interval = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % verificationSteps.length);
    }, 850);

    return () => window.clearInterval(interval);
  }, [reducedMotion]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      pointerRef.current = {
        x: (event.clientX / window.innerWidth - 0.5) * 1.4,
        y: (event.clientY / window.innerHeight - 0.5) * 1.2,
      };
    };

    window.addEventListener("pointermove", handlePointerMove);
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, []);

  useFrame(({ camera, clock }) => {
    const elapsed = clock.elapsedTime;
    const basePosition = reducedMotion ? new THREE.Vector3(0, 0.2, 5.2) : new THREE.Vector3(0, 0.25, 5.8 - Math.min(elapsed * 0.18, 1.5));
    camera.position.lerp(basePosition, 0.04);
    camera.lookAt(0, 0.15, 0);

    if (groupRef.current) {
      groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, pointerRef.current.x * 0.65, 0.04);
      groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, -pointerRef.current.y * 0.4, 0.04);
    }
  });

  const visibleNodes = useMemo(
    () => verificationNodes.slice(0, Math.min(activeIndex + 1, verificationNodes.length)),
    [activeIndex],
  );

  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[0, 4, 5]} color="#8fe3ff" intensity={28} />
      <pointLight position={[2, -2, 4]} color="#b5ff4f" intensity={16} />
      <group ref={groupRef}>
        <mesh position={[0, 0, -0.6]}>
          <torusGeometry args={[2.9, 0.02, 12, 120]} />
          <meshStandardMaterial color="#1b2c38" emissive="#1a57ae" emissiveIntensity={0.18} />
        </mesh>
        <InvoiceDocument activeIndex={activeIndex} />
        {visibleNodes.map((node, index) => (
          <group key={node.label}>
            <Line
              points={[
                [0, 0.1, -0.1],
                [node.position[0] * 0.45, node.position[1] * 0.42, 0.2],
              ]}
              color={index <= activeIndex ? "#b5ff4f" : "#506271"}
              lineWidth={1.1}
            />
            <NodeBadge label={node.label} active={index <= activeIndex} position={node.position as [number, number, number]} />
          </group>
        ))}
      </group>
    </>
  );
}

export function CinematicIntro() {
  const [mounted, setMounted] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const supportsWebGL = useWebGLSupport();

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#050b13] text-slate-50">
      <div className="pg-ambient" />
      <div className="pg-grid" />

      <div className="relative mx-auto max-w-[1440px] px-5 pb-14 pt-5 sm:px-8 lg:px-10">
        <header className="panel flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-lime font-display text-lg font-bold text-ink">P</span>
            <div>
              <div className="font-display text-[15px] font-semibold tracking-tight text-frost">
                PayGuard<span className="text-mist"> AI</span>
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist">Accounts payable · command</div>
            </div>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="size-1.5 rounded-full bg-cyan" />
            <span className="font-mono text-[11px] text-mist">Radar · live</span>
            <span className="ml-3 rounded-lg border border-line/10 bg-line/[0.04] px-3 py-2 font-mono text-[11px] text-mist">AP-2048</span>
          </div>
        </header>

        <section className="mt-8 grid items-center gap-8 lg:grid-cols-[0.96fr_1.04fr]">
          <div className="animate-fade-up">
            <div className="inline-flex items-center gap-2 rounded-full border border-line/10 bg-line/[0.05] px-3 py-1.5">
              <span className="size-1.5 rounded-full bg-lime" />
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-mist">Live demo · 3 sec to command</span>
            </div>

            <h1 className="mt-6 font-display text-5xl font-bold leading-[0.95] tracking-tight text-frost sm:text-6xl lg:text-7xl">
              PAYGUARD AI
            </h1>
            <h2 className="mt-3 font-display text-2xl font-semibold tracking-tight text-lime sm:text-3xl">
              VERIFY BEFORE YOU PAY.
            </h2>

            <p className="mt-5 max-w-[34rem] text-[15px] leading-relaxed text-mist">
              Intelligent accounts payable control.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/app/dashboard"
                className="inline-flex items-center justify-center rounded-xl bg-lime px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-ink transition-colors hover:bg-frost"
              >
                [ ENTER PAYGUARD ]
              </Link>
              <button
                type="button"
                onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth", block: "start" })}
                className="inline-flex items-center justify-center rounded-xl border border-line/10 bg-transparent px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-frost transition-colors hover:bg-line/[0.05]"
              >
                [ SEE HOW IT WORKS ]
              </button>
            </div>
          </div>

          <div className="relative h-[560px] overflow-hidden rounded-[28px] border border-line/10 bg-[radial-gradient(circle_at_top,_rgba(66,143,255,0.18),_transparent_38%),linear-gradient(180deg,_rgba(10,19,28,0.95),_rgba(5,11,19,1))] shadow-[0_30px_80px_rgba(2,6,15,0.7)]">
            {mounted && supportsWebGL ? (
              <Canvas camera={{ position: [0, 0.2, 5.8], fov: 38 }} dpr={[1, 2]}>
                <VerificationSequence reducedMotion={reducedMotion} />
              </Canvas>
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-center">
                <div className="max-w-xs">
                  <div className="mx-auto mb-4 grid size-16 place-items-center rounded-2xl border border-line/10 bg-panel text-2xl text-lime">P</div>
                  <p className="font-display text-xl font-semibold text-frost">WebGL unavailable</p>
                  <p className="mt-2 text-sm text-mist">Fallback mode enabled. You can still enter the PayGuard cockpit.</p>
                  <Link to="/app/dashboard" className="mt-5 inline-flex rounded-xl bg-lime px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-ink">
                    ENTER PAYGUARD
                  </Link>
                </div>
              </div>
            )}

            <div className="pointer-events-none absolute inset-x-8 bottom-6 flex items-center justify-between gap-3 rounded-2xl border border-line/10 bg-[#07131d]/80 px-4 py-3 backdrop-blur-sm">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-mist">VERIFICATION STATUS</div>
                <div className="mt-1 text-lg font-semibold text-frost">INVOICE RECEIVED ≠ PAYABLE</div>
              </div>
              <div className="rounded-full border border-lime/30 bg-lime/14 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-lime">
                REVIEW REQUIRED
              </div>
            </div>
          </div>
        </section>

        <section id="how-it-works" className="mt-16 pt-6">
          <div className="mb-6 text-center">
            <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-lime">Verification flow</div>
            <h3 className="mt-2 font-display text-3xl font-bold text-frost">From invoice received to payment decision.</h3>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {verificationSteps.map((step, index) => (
              <div
                key={step}
                className="panel flex min-h-[124px] flex-col justify-between p-4 text-left"
              >
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-mist">
                  Step {index + 1}
                </div>
                <div className="mt-3 text-lg font-semibold text-frost">{step}</div>
                {index < verificationSteps.length - 1 ? (
                  <div className="mt-4 text-[10px] uppercase tracking-[0.22em] text-cyan">↓</div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <div className="panel p-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-lime">Outcome</div>
              <div className="mt-3 font-display text-3xl font-bold text-frost">APPROVED</div>
              <p className="mt-2 text-sm text-mist">A matched invoice continues to the payment lane with traceability and approval record intact.</p>
            </div>
            <div className="panel border border-amber/20 bg-amber/5 p-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-amber">Outcome</div>
              <div className="mt-3 font-display text-3xl font-bold text-frost">REVIEW REQUIRED</div>
              <p className="mt-2 text-sm text-mist">Any mismatch, duplicate, or risk signal is held before funds move.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
