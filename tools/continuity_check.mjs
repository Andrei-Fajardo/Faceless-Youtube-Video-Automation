// continuity_check.mjs — automatic continuity and physics check for a multi-shot sequence (see the "Continuity and physics standard").
// Usage: node tools/continuity_check.mjs <studio project folder name> [from] [to] [state module, default _poolstate.js]      e.g. node tools/continuity_check.mjs half-brain 63.85 92.6
// Samples the shared world state every 0.04 s and reports: people on the water, people floating above or sunk through a surface, position jumps,
// anyone missing from the roster, and bodies that leave the visible yard. Exit code 1 if anything fails.
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
const proj = process.argv[2] || 'half-brain', from = Number(process.argv[3] ?? 63.85), to = Number(process.argv[4] ?? 92.6), stateFile = process.argv[5] || '_poolstate.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'aitrends-2d-studio', 'projects', proj, 'scenes');
const m = await import(pathToFileURL(path.join(root, stateFile)).href);
const { K, stateAt, IDS, feetY } = m, dt = 0.04, bad = new Map(), note = (k, msg) => { if (!bad.has(k)) bad.set(k, []); const a = bad.get(k); if (a.length < 3) a.push(msg); else if (a.length === 3) a.push('...'); };
let prev = null, n = 0;
for (let t = from; t <= to + 1e-9; t += dt, n++) {
  const st = stateAt(t); const ids = st.map(s => s.id).sort().join(',');
  if (ids !== [...IDS].sort().join(',')) note('roster', `t=${t.toFixed(2)} has ${ids}`);
  for (const s of st) {
    const inPool = s.x > K.px0 && s.x < K.px1, fy = feetY(s);
    if (s.mode === 'ground') {
      if (inPool) note('on-water', `${s.id} stands in the pool span at t=${t.toFixed(2)} (x=${s.x.toFixed(0)})`);
      if (fy < K.g0 + 10 || fy > K.g0 + 220) note('floating', `${s.id} feet y=${fy.toFixed(0)} outside the ground band at t=${t.toFixed(2)}`);
    }
    if (s.mode === 'water') { if (!inPool) note('water-outside', `${s.id} in water mode outside the pool at t=${t.toFixed(2)}`); if (s.cy < K.wl - 40 || s.cy > K.bottom) note('water-depth', `${s.id} hip y=${s.cy.toFixed(0)} out of the water column at t=${t.toFixed(2)}`); }
    if (s.mode === 'air' && s.cy > K.wl + 60) note('sunk-in-air', `${s.id} airborne below the water line at t=${t.toFixed(2)}`);
    if (s.x < -1000 || s.x > 3000) note('offstage', `${s.id} at x=${s.x.toFixed(0)} is outside the yard`);
  }
  // speed limit 1200 px/s (a fall of 0.4 s reaches about 750 px/s); while both samples are on the ground, compare feet, otherwise compare hips
  if (prev) for (const s of st) { const p = prev.find(q => q.id === s.id), ground = s.mode === 'ground' && p.mode === 'ground', v = Math.hypot(s.x - p.x, ground ? feetY(s) - feetY(p) : s.cy - p.cy) / dt; if (v > 1200) note('teleport', `${s.id} moved ${v.toFixed(0)} px/s at t=${t.toFixed(2)}`); }
  prev = st;
}
console.log(`continuity_check: ${n} samples of ${IDS.length} people, ${from}s to ${to}s`);
if (!bad.size) { console.log('PASS: nobody on the water, nobody floating, no jumps, full roster in every sample'); process.exit(0); }
for (const [k, v] of bad) console.log(`FAIL ${k}:\n  ` + v.join('\n  '));
process.exit(1);
