import { Canvas, useFrame } from "@react-three/fiber";
import { Line, RoundedBox, Sparkles, Text } from "@react-three/drei";
import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const invoiceSeries = [
  ["INV-1001", "Northwind Supply", "₹59,00,000", "PO-4587", "NWS001"],
  ["INV-1003", "Solstice Catering", "₹5,19,200", "PO-7741", "SLC103"],
  ["INV-1004", "Delta Cloud", "₹59,00,000", "PO-6102", "DLC009"],
] as const;

function useWebGLSupport() {
  const [supportsWebGL, setSupportsWebGL] = useState(true);

  useEffect(() => {
    if (typeof document === "undefined") return;

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

function InvoiceCard({
  data,
  active = false,
}: {
  data: readonly [string, string, string, string, string];
  active?: boolean;
}) {
  return (
    <group rotation={[0.08, active ? 0 : -0.18, 0]}>
      <RoundedBox args={[3.35, 4.65, 0.48]} radius={0.16} smoothness={5}>
        <meshStandardMaterial color="#29414a" metalness={0.72} roughness={0.3} emissive="#1d5664" emissiveIntensity={0.24} />
      </RoundedBox>
      <RoundedBox args={[3.02, 4.28, 0.12]} position={[0, 0, 0.27]} radius={0.12} smoothness={5}>
        <meshStandardMaterial color="#10252d" metalness={0.2} roughness={0.62} />
      </RoundedBox>
      <mesh position={[0, 0, 0.35]}>
        <planeGeometry args={[2.75, 4.02]} />
        <meshBasicMaterial color="#86bdc5" transparent opacity={0.12} wireframe />
      </mesh>
      <Text position={[-1.08, 2.02, 0.43]} color="#efffff" fontSize={0.2} anchorX="left" anchorY="middle" letterSpacing={0.04}>
        PAYGUARD AI
      </Text>
      <Text position={[-1.08, 1.72, 0.43]} color="#78929e" fontSize={0.105} anchorX="left" anchorY="middle" letterSpacing={0.1}>
        ACCOUNTS PAYABLE CONTROL
      </Text>
      <mesh position={[0.84, 1.86, 0.43]}>
        <planeGeometry args={[0.32, 0.04]} />
        <meshBasicMaterial color={active ? "#bfff00" : "#28788c"} />
      </mesh>
      <Text position={[-1.08, 1.18, 0.43]} color="#68d7e8" fontSize={0.22} anchorX="left" anchorY="middle" letterSpacing={0.08}>
        INVOICE
      </Text>
      <Text position={[-1.08, 0.82, 0.43]} color="#e6f3f5" fontSize={0.29} anchorX="left" anchorY="middle" letterSpacing={0.06}>
        {data[0]}
      </Text>
      <Text position={[-1.08, 0.14, 0.43]} color="#d7e5e7" fontSize={0.16} anchorX="left" anchorY="middle" maxWidth={2.8}>
        {data[1]}
      </Text>
      <Text position={[-1.08, -0.65, 0.43]} color="#f3fbfb" fontSize={0.33} anchorX="left" anchorY="middle">
        {data[2]}
      </Text>
      <Text position={[-1.08, -1.2, 0.43]} color="#728c96" fontSize={0.09} anchorX="left" anchorY="middle" letterSpacing={0.08}>
        PO NUMBER
      </Text>
      <Text position={[-1.08, -1.48, 0.43]} color="#d7e8ea" fontSize={0.15} anchorX="left" anchorY="middle">
        {data[3]}
      </Text>
      <Text position={[0.58, -1.2, 0.43]} color="#728c96" fontSize={0.09} anchorX="left" anchorY="middle" letterSpacing={0.08}>
        VENDOR CODE
      </Text>
      <Text position={[0.58, -1.48, 0.43]} color="#d7e8ea" fontSize={0.15} anchorX="left" anchorY="middle">
        {data[4]}
      </Text>
      <Text position={[-1.08, -1.95, 0.43]} color="#f0b84b" fontSize={0.12} anchorX="left" anchorY="middle" letterSpacing={0.08}>
        UNDER REVIEW
      </Text>
      <Text position={[-1.08, -2.22, 0.43]} color="#cbdadd" fontSize={0.14} anchorX="left" anchorY="middle">
        QUANTITY MISMATCH
      </Text>
    </group>
  );
}

function FallingMoneyItem({
  type,
  x,
  y,
  z,
  speed,
  seed,
}: {
  type: "rupee" | "coin" | "bag";
  x: number;
  y: number;
  z: number;
  speed: number;
  seed: number;
}) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;

    const phase = (clock.elapsedTime * speed + seed) % 1;
    const currentY = y - phase * 12;
    const drift = Math.sin((phase * 2 + seed) * Math.PI) * 0.42;

    ref.current.position.set(x + drift, currentY, z + Math.cos((phase * 3 + seed) * Math.PI) * 0.5);
    ref.current.rotation.x = phase * 2.5 + seed;
    ref.current.rotation.y = phase * 2.1 + seed * 2;
    ref.current.rotation.z = Math.sin(phase * 5 + seed) * 0.35;
  });

  if (type === "rupee") {
    return (
      <group ref={ref}>
        <Text position={[0, 0, 0]} color="#b48a36" fontSize={0.25} anchorX="center" anchorY="middle">
          ₹
        </Text>
      </group>
    );
  }

  if (type === "coin") {
    return (
      <group ref={ref}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.16, 0.16, 0.06, 24]} />
          <meshStandardMaterial color="#b48a36" metalness={0.9} roughness={0.25} emissive="#8c681e" emissiveIntensity={0.12} />
        </mesh>
        <Text position={[0, 0.04, 0.06]} color="#fff7d6" fontSize={0.1} anchorX="center" anchorY="middle">
          ₹
        </Text>
      </group>
    );
  }

  return (
    <group ref={ref}>
      <RoundedBox args={[0.52, 0.6, 0.44]} radius={0.1} smoothness={4}>
        <meshStandardMaterial color="#59401e" metalness={0.55} roughness={0.8} emissive="#8d6d2b" emissiveIntensity={0.08} />
      </RoundedBox>
      <mesh position={[0, 0.38, 0]}>
        <torusGeometry args={[0.12, 0.03, 10, 14]} />
        <meshStandardMaterial color="#b48a36" metalness={0.75} roughness={0.45} />
      </mesh>
      <Text position={[0, 0, 0.24]} color="#d9b86b" fontSize={0.16} anchorX="center" anchorY="middle">
        ₹
      </Text>
    </group>
  );
}

function SceneContent() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const timer = window.setInterval(() => setElapsed((performance.now() - start) / 1000), 100);
    return () => window.clearInterval(timer);
  }, []);

  const moneyItems = useMemo(
    () => [
      { type: "rupee", x: -3.7, y: 4.6, z: -2.2, speed: 0.11, seed: 0.2 },
      { type: "rupee", x: 3.5, y: 4.2, z: -1.8, speed: 0.13, seed: 0.7 },
      { type: "rupee", x: -2.8, y: 5.1, z: 1.7, speed: 0.14, seed: 1.2 },
      { type: "rupee", x: 3.8, y: 4.7, z: 2.1, speed: 0.12, seed: 1.9 },
      { type: "coin", x: -3.1, y: 5.3, z: 0.9, speed: 0.1, seed: 2.4 },
      { type: "coin", x: 2.5, y: 4.8, z: 2.6, speed: 0.09, seed: 2.9 },
      { type: "coin", x: -1.7, y: 5.4, z: -2.4, speed: 0.12, seed: 3.7 },
      { type: "coin", x: 3.1, y: 4.5, z: -0.8, speed: 0.1, seed: 4.2 },
      { type: "bag", x: -4.2, y: 5.6, z: 1.2, speed: 0.08, seed: 5.3 },
      { type: "bag", x: 4.2, y: 5.2, z: 0.2, speed: 0.09, seed: 5.8 },
    ],
    [],
  );

  const focusRef = useRef<THREE.Group>(null);
  useFrame(({ camera, clock }) => {
    const t = clock.elapsedTime;
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, Math.sin(t * 0.18) * 0.22, 0.025);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, 0.25 + Math.cos(t * 0.16) * 0.08, 0.025);
    camera.lookAt(0, 0.2, 0);
    if (focusRef.current) {
      focusRef.current.rotation.y = Math.sin(t * 0.22) * 0.075;
      focusRef.current.rotation.x = -0.045 + Math.sin(t * 0.3) * 0.012;
      focusRef.current.position.y = 0.35 + Math.sin(t * 0.5) * 0.045;
    }
  });

  const verificationNodes = [
    ["VENDOR", "✓ VERIFIED", [-3.35, 1.65, 0.2]],
    ["PO MATCH", "✓ MATCHED", [3.25, 1.65, 0.2]],
    ["RECEIPT", "✓ RECEIVED", [-3.55, -0.55, 0.3]],
    ["PRICE", "✓ MATCHED", [3.45, -0.55, 0.3]],
    ["DUPLICATE", "✓ CLEAR", [0, 3.0, 0.1]],
  ] as const;
  const stage = Math.min(5, Math.floor(elapsed / 1.05));
  const activeNode = Math.min(4, Math.floor(elapsed / 1.05));

  return (
    <>
      <color attach="background" args={["#040b12"]} />
      <fog attach="fog" args={["#040b12", 8, 16]} />

      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 6, 6]} intensity={2.1} color="#d9f3ff" />
      <pointLight position={[0, 2, 4]} intensity={12} distance={10} color="#69d9ed" />
      <pointLight position={[-4, 1, 2]} intensity={7} distance={8} color="#bfff00" />

      <group>
        <mesh position={[0, -3.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[7.9, 64]} />
          <meshStandardMaterial color="#07141b" metalness={0.82} roughness={0.64} />
        </mesh>
        <mesh position={[0, -2.95, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[2.7, 3.35, 64]} />
          <meshStandardMaterial color="#236d7b" transparent opacity={0.24} emissive="#39cce2" emissiveIntensity={0.22} />
        </mesh>
        <gridHelper args={[14, 22, "#153543", "#0a1c25"]} position={[0, -2.91, 0]} />

        <group position={[-0.1, 0.35, 0]} scale={0.93} ref={focusRef}>
          <InvoiceCard data={["INV-1002", "ABC Technologies Pvt Ltd", "₹7,08,000", "PO-4587", "ABC001"]} active />
          {verificationNodes.map(([label, status, position], index) => {
            const connected = stage > index;
            const pulse = activeNode === index && elapsed % 1.05 > 0.72;
            const start = new THREE.Vector3(0, 0, 0.48);
            const end = new THREE.Vector3(position[0], position[1] - 0.05, position[2] + 0.48);
            return (
              <group key={label} position={position}>
                <mesh scale={pulse ? 1.18 : 1}>
                  <circleGeometry args={[0.12, 20]} />
                  <meshBasicMaterial color={connected ? "#bfff00" : "#3a6570"} transparent opacity={connected ? 0.95 : 0.62} />
                </mesh>
                <Text position={[0, -0.27, 0]} color="#d8eef0" fontSize={0.13} anchorX="center" anchorY="middle" letterSpacing={0.08}>
                  {label}
                </Text>
                <Text position={[0, -0.5, 0]} color={connected ? "#bfff00" : "#71909a"} fontSize={0.1} anchorX="center" anchorY="middle" letterSpacing={0.03}>
                  {connected ? status : "ANALYZING"}
                </Text>
                <Line points={[start, end]} color={connected ? "#70d9dd" : "#244851"} transparent opacity={connected ? 0.6 : 0.28} lineWidth={0.45} />
              </group>
            );
          })}
          {stage >= 5 ? (
            <group position={[0, 3.22, 0.55]}>
              <mesh rotation={[0, 0, -0.78]} position={[-0.12, 0, 0]}>
                <boxGeometry args={[0.34, 0.07, 0.07]} />
                <meshBasicMaterial color="#bfff00" />
              </mesh>
              <mesh rotation={[0, 0, 0.78]} position={[0.12, 0.08, 0]}>
                <boxGeometry args={[0.52, 0.07, 0.07]} />
                <meshBasicMaterial color="#bfff00" />
              </mesh>
              <Text position={[0, -0.42, 0]} color="#bfff00" fontSize={0.12} anchorX="center" anchorY="middle" letterSpacing={0.09}>VERIFICATION COMPLETE</Text>
            </group>
          ) : null}
          {stage >= 5 ? (
            <group position={[0, -2.22, 0.55]}>
              <RoundedBox args={[2.55, 0.9, 0.08]} radius={0.08} smoothness={3}>
                <meshStandardMaterial color="#241c14" metalness={0.35} roughness={0.7} emissive="#6b3519" emissiveIntensity={0.18} />
              </RoundedBox>
              <Text position={[-1.05, 0.22, 0.08]} color="#f0b84b" fontSize={0.1} anchorX="left" anchorY="middle" letterSpacing={0.08}>QUANTITY CHECK</Text>
              <Text position={[-1.05, -0.03, 0.08]} color="#b6c8cb" fontSize={0.085} anchorX="left" anchorY="middle">PO 50   RECEIVED 40   INVOICE 50</Text>
              <Text position={[-1.05, -0.25, 0.08]} color="#f07a5b" fontSize={0.105} anchorX="left" anchorY="middle" letterSpacing={0.05}>MISMATCH · RISK 75 / 100 · REVIEW REQUIRED</Text>
            </group>
          ) : null}
        </group>

        {invoiceSeries.map((invoice, index) => (
          <group key={invoice[0]} position={[index === 0 ? -2.85 : 2.85, index === 0 ? 0.25 : 0.05, -1.4 - index * 0.2]} rotation={[0.08, index === 0 ? 0.35 : -0.35, 0]} scale={0.58}>
            <InvoiceCard data={invoice} />
          </group>
        ))}

        {moneyItems.map((item) => (
          <FallingMoneyItem key={`${item.type}-${item.seed}`} {...item} />
        ))}
      </group>

      <Sparkles count={14} scale={[11, 7, 9]} color="#8bbbc4" size={1.3} speed={0.18} />
    </>
  );
}

export function CinematicIntro() {
  const navigate = useNavigate();
  const supportsWebGL = useWebGLSupport();

  const handleHowItWorks = () => {
    document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#040b12] text-slate-50">
      <div className="pg-ambient" />
      <div className="pg-grid" />

      <div className="relative z-10 mx-auto max-w-[1500px] px-5 pb-16 pt-6 sm:px-8 lg:px-10">
        <header className="panel mb-8 flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-lime font-display text-lg font-bold text-ink">P</span>
            <div>
              <div className="font-display text-[15px] font-semibold tracking-tight text-frost">PayGuard<span className="text-mist"> AI</span></div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist">Accounts payable · command</div>
            </div>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="size-1.5 rounded-full bg-cyan" />
            <span className="font-mono text-[11px] text-mist">Radar · live</span>
            <span className="ml-3 rounded-lg border border-line/10 bg-line/[0.04] px-3 py-2 font-mono text-[11px] text-mist">AP-2048</span>
          </div>
        </header>

        <section className="grid items-center gap-8 md:grid-cols-2">
          <div className="max-w-[640px] animate-fade-up">
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
              <button
                type="button"
                onClick={() => navigate({ to: "/app/dashboard" })}
                className="inline-flex items-center justify-center rounded-xl bg-lime px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-ink transition-colors hover:bg-frost"
              >
                [ ENTER PAYGUARD ]
              </button>
              <button
                type="button"
                onClick={handleHowItWorks}
                className="inline-flex items-center justify-center rounded-xl border border-line/10 bg-transparent px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-frost transition-colors hover:bg-line/[0.05]"
              >
                [ SEE HOW IT WORKS ]
              </button>
            </div>

            <div className="mt-10 max-w-[460px] rounded-[22px] border border-line/10 bg-slate-950/40 p-5 backdrop-blur-sm">
              <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-lime">INVOICE RECEIVED</div>
              <div className="my-3 text-center text-4xl font-semibold text-frost">≠</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-lime">PAYABLE</div>
              <p className="mt-4 text-sm leading-relaxed text-mist">Every invoice must earn its place in the payable ledger.</p>
              <button
                type="button"
                onClick={() => navigate({ to: "/app/dashboard" })}
                className="mt-5 inline-flex items-center justify-center rounded-xl bg-lime px-4 py-2 font-mono text-[10px] uppercase tracking-[0.22em] text-ink"
              >
                ENTER PAYGUARD
              </button>
            </div>
          </div>

          <div className="relative h-[680px] min-h-[680px] w-full overflow-hidden rounded-[30px] border border-line/10 bg-[radial-gradient(circle_at_top,_rgba(110,188,255,0.2),_transparent_38%),linear-gradient(180deg,_rgba(7,15,20,0.96),_rgba(3,10,16,1))] shadow-[0_30px_100px_rgba(2,6,15,0.75)]">
            {supportsWebGL ? (
              <Canvas
                camera={{ position: [0, 0.8, 12], fov: 30 }}
                dpr={[1, 2]}
                gl={{ antialias: true }}
                style={{ width: "100%", height: "100%", display: "block", background: "transparent" }}
              >
                <SceneContent />
              </Canvas>
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-center">
                <div className="max-w-xs">
                  <div className="mx-auto mb-4 grid size-16 place-items-center rounded-2xl border border-line/10 bg-panel text-2xl text-lime">P</div>
                  <p className="font-display text-xl font-semibold text-frost">WebGL unavailable</p>
                  <p className="mt-2 text-sm text-mist">Fallback mode enabled. You can still enter the PayGuard cockpit.</p>
                  <button
                    type="button"
                    onClick={() => navigate({ to: "/app/dashboard" })}
                    className="mt-5 inline-flex rounded-xl bg-lime px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-ink"
                  >
                    ENTER PAYGUARD
                  </button>
                </div>
              </div>
            )}

            <div className="pointer-events-none absolute inset-x-5 bottom-5 rounded-2xl border border-line/10 bg-[#07131d]/80 px-4 py-3 backdrop-blur-md">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-mist">VERIFICATION STATUS</div>
                  <div className="mt-1 text-lg font-semibold text-frost">INVOICE RECEIVED ≠ PAYABLE</div>
                  <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.2em] text-mist">Only verified and approved invoices become payables.</div>
                </div>
                <div className="rounded-full border border-lime/30 bg-lime/14 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-lime">
                  REVIEW REQUIRED
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
