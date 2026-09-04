# AXTI and the Indium Phosphide Floor

Why indium phosphide is irreplaceable in optical interconnects, where AXT actually sits in the photonics stack, and what breaks the bottleneck thesis.

**Last Updated:** 2026-09-04
**Status:** Active
**Audience:** Both

Rendered companion, with the fiber-attenuation chart and revenue chart this file cannot
carry: [`data/2026-09-04_AXTI_INDIUM_PHOSPHIDE_RESEARCH.html`](data/2026-09-04_AXTI_INDIUM_PHOSPHIDE_RESEARCH.html)
— open it from disk. There is also a published copy at
https://claude.ai/code/artifact/df8ef9cd-beff-4524-8b19-a5ad1e7035c1, which is private to the
author's account and will not open for other readers.

> **On the committed HTML.** `AGENTS.md` says to avoid committing generated HTML; that rule
> targets `docsrc/` build output, which is reproducible from source in CI. This page is not —
> it is the primary artifact of the research and holds the two charts. It is committed
> deliberately as a hand-authored document, not as build output, and it is not a precedent for
> checking in generated docs. It and this file are a **pair**: correct a figure in one, correct
> it in the other.

---

## Overview

AXT, Inc. (NASDAQ: AXTI) grows compound semiconductor substrates — indium phosphide (InP),
gallium arsenide (GaAs) and germanium (Ge). Over five quarters InP went from 20% to 65% of
its revenue on AI data center optical demand, and gross margin ran from 8.2% to 45.0%.

This document answers two separate questions that are easy to conflate:

1. **Is InP genuinely foundational to optics and photonics?** Yes, for reasons that are
   physical and not subject to engineering around in this decade.
2. **Does that make AXT the foundation of the industry?** No. AXT is the number two
   supplier of one input, two layers below the transceiver, and its entire production base
   sits inside China's export-control regime.

Not investment advice. Figures are as reported; market data was accurate at compile time and
AXTI has moved >50% in a quarter more than once this year.

---

## 1. The physics: why the photon must be born on InP

Three constraints stack, and only one crystal satisfies all three.

### 1.1 The emitter needs a direct bandgap

In an indirect-bandgap semiconductor an electron and hole cannot recombine into a photon
without also involving a lattice vibration, making the process orders of magnitude less
probable than competing non-radiative paths. This is why no practical silicon laser exists.
Silicon and germanium are both indirect. Direct-bandgap III–V compounds recombine
radiatively as a matter of course.

### 1.2 The wavelength must land in the fiber's low-loss windows

Silica fiber has two useful transmission windows:

| Window | Wavelength | Typical attenuation | Property |
| --- | --- | --- | --- |
| O-band | 1310 nm | ~0.33 dB/km | Near-zero chromatic dispersion |
| C/L-band | 1550 nm | ~0.19 dB/km | Global attenuation minimum |
| (short reach) | 850 nm | ~2.2 dB/km | >10x lossier; multimode only, few hundred metres |

850 nm is where GaAs-based VCSELs emit, which is why those links never leave a rack row.
Scale-out links between racks and across a data hall need 1310/1550 nm.

### 1.3 The emitting alloy must be lattice-matched to its substrate

A lattice mismatch of even a fraction of a percent generates threading dislocations, and
dislocations are what kill laser lifetime. So the substrate fixes the alloy palette, and the
alloy palette fixes the wavelength:

| Substrate | Bandgap | Transition | Lattice-matched emitters | Accessible wavelengths |
| --- | --- | --- | --- | --- |
| Si | 1.12 eV | Indirect | none that emit efficiently | no practical laser |
| Ge | 0.66 eV | Indirect | detector / solar-cell base only | no practical laser |
| GaAs | 1.42 eV | Direct | AlGaAs, InGaAs (strained) | 780–1100 nm |
| **InP** | **1.34 eV** | **Direct** | **InGaAsP, InGaAlAs, InGaAs** | **1200–1650 nm (O/E/S/C/L bands)** |

The bottom row is the whole argument. In(0.53)Ga(0.47)As is lattice-matched to InP at ~0.75 eV,
and quaternary InGaAsP/InGaAlAs tunes continuously between that and InP's own 1.34 eV — so a
single substrate platform covers the entire telecom spectrum with defect-free epitaxy. No other
commercially available substrate does. Attempts to reach 1310 nm from GaAs (InGaAsN, GaAsSb)
have been researched for 25 years and have never displaced InP in volume.

### 1.4 The quieter constraint: electron velocity

InP's electron mobility is roughly an order of magnitude above silicon's and its peak electron
velocity exceeds GaAs's. That makes InP the platform not only for the light source but for the
electro-absorption modulator integrated alongside it in an EML, for InP HBT/HEMT circuits above
100 GHz, and for the high-speed PIN and avalanche photodiodes on the receive side. As per-lane
rates move past 200G PAM4, modulator bandwidth pushes further into InP-only territory.

### 1.5 What is actually built on the wafer

| Device | Function | Where it ships |
| --- | --- | --- |
| EML (DFB + EAM, monolithic) | Modulated 1310 nm transmit channel at 100–200G/lane | 800G / 1.6T pluggables — largest InP consumer today |
| CW-DFB laser | Continuous-wave source feeding an external modulator | Silicon-photonics transceivers; external laser sources for CPO |
| Tunable laser (DBR / ECL) | Wavelength-agile narrow-linewidth source | Coherent 400ZR/800ZR, DWDM line systems |
| SOA | Optical gain without electrical conversion | Loss budget recovery in CPO and PON |
| Pump laser (980/1480 nm) | Energises erbium-doped fiber amplifiers | Every long-haul and metro amplifier site |
| PIN / APD photodiode | Converts 1310/1550 nm light back to current | Receive side of long-reach modules |
| InP PIC | Laser, modulator, splitter, detector monolithically integrated | Coherent transponders |

### 1.6 Silicon photonics and CPO make the dependency worse, not better

The common misreading is that silicon photonics displaces III–V. It does not. A silicon
photonic die can guide, split, modulate and detect light; it cannot generate it. Every silicon
photonics platform pairs the silicon die with an InP gain chip — flip-chip attached,
micro-transfer-printed, or coupled from a separately packaged external laser source.

Co-packaged optics goes further: it moves the optical engine onto the switch package,
multiplies independent laser sources per package, and tightens reliability and low-defect
requirements on the substrate, because a failed laser inside a switch package is far more
expensive than a failed pluggable. TSMC's COUPE platform and the Broadcom and NVIDIA CPO
products all still need an InP light source per package. More integration, more lasers,
more wafers.

### 1.7 Why the substrate itself is not a commodity

Laser-grade InP must hit dislocation etch-pit densities in the hundreds to low thousands per
cm^2, surface roughness below ~0.3 nm Ra, and crystal-plane orientation tolerances around
+/-0.01 deg. It comes in two non-interchangeable electrical flavours: sulphur-doped n-type for
laser and detector epitaxy, and iron-doped semi-insulating (~10^7 ohm-cm) for high-frequency
devices where substrate conductivity would destroy the circuit.

AXT grows by **vertical gradient freeze (VGF)** — slow, low-thermal-gradient, lower dislocation
density than melt-pulling, at the cost of long growth cycles. Industry single-crystal yields run
roughly 15–25%; from 100 kg of high-purity indium feedstock, on the order of 10 kg emerges as
saleable wafer. That yield curve plus multi-quarter customer requalification is the moat — and
the reason capacity cannot be conjured in two quarters no matter how much capital arrives.

---

## 2. Where AXT sits: six layers from crystal to cluster

Bottom-up, in the order material actually moves:

| # | Layer | Who |
| --- | --- | --- |
| 01 | **Raw materials** | **AXT** — high-purity gallium and germanium, InP poly base material, pyrolytic boron nitride crucibles (JinMei, BoYu subsidiaries). Indium itself is bought in; it is a zinc-refining by-product and China produced ~69–70% of refined indium. |
| 02 | **Substrate** | **AXT** — VGF growth, slicing, lapping, polishing into 2/3/4-inch and now 6-inch InP, plus GaAs and Ge. Three suppliers worldwide at scale. |
| 03 | Epitaxy | MOCVD growth of the quantum-well structure. Merchant epi houses (LandMark, VPEC) plus in-house lines. |
| 04 | Laser / detector die | Coherent, Lumentum, Sumitomo, Mitsubishi, Broadcom, Source Photonics, Accelink, Chinese laser cohort. |
| 05 | Optical module / engine | Innolight, Eoptolink, Coherent, Marvell DSP-paired designs, TSMC COUPE. |
| 06 | Switch and cluster | NVIDIA, Broadcom, Arista, hyperscalers — who create the demand signal and have begun reaching five layers down with prepayments. |

**The value-capture asymmetry.** A 1.6T module sells for four figures; the InP substrate content
under it is a small fraction. AXT's entire TTM revenue is ~$126M against an optical module market
in the tens of billions. Its leverage is not share of wallet — it is *pricing power in a shortage*,
which is real but conditional, and is exactly what everyone above layer 02 is spending capital
to eliminate.

---

## 3. The company

### 3.1 Revenue by product line ($M)

| Quarter | InP | GaAs | Ge | Raw mat. | Total | GM (non-GAAP) | EPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Q2 2025 | 3.6 | 6.2 | 1.5 | 6.7* | 18.0 | 8.2% | (0.15) |
| Q3 2025 | 13.1 | 7.5 | 0.6 | 6.7 | 28.0 | 22.4% | (0.03) |
| Q4 2025 | 8.0 | 7.0 | 0.2 | 7.6 | 23.0 | 21.5% | (0.05) |
| Q1 2026 | 13.6 | 5.4 | 0.3 | 7.6 | 26.9 | 29.9% | (0.01) |
| Q2 2026 | **30.7** | 6.6 | 0.3 | 10.0 | **47.6** | **45.0%** | **0.19** |
| Q3 2026 guide | — | — | — | — | >= 66 | rising | 0.30–0.32 |

\* AXT did not separately report Q2/25 raw materials. $6.7M is derived from the Q3/25 report's
statement that the segment was flat sequentially, and checks out against the reported $18.0M total.
Every other cell is as reported.

Two things matter more than the growth rate:

- **Operating leverage is severe in both directions.** Gross margin went 8.2% -> 45.0% while
  revenue merely went $18M -> $48M, because crystal growth is high-fixed-cost and utilisation
  is everything. The same mechanism runs in reverse.
- **There is no second engine.** GaAs (850 nm VCSELs, micro-LED, HBLED, RF power amplifiers)
  has hovered at $5–7.5M for years. Germanium (multi-junction space solar cells) has rolled off
  from $1.5M to $0.3M a quarter. The thesis is InP or nothing.

### 3.2 Capacity ramp

April 2026: ~$632.5M gross secondary offering — more than five years of revenue — lifting cash
from ~$123M to ~$749M at closing in April; cash plus short- and long-term investments stood at
$715.8M at 30 June. Stated use: InP capacity at Beijing Tongmei plus 6-inch R&D.
Management then raised its own targets on the Q2 call:

| Milestone | InP quarterly revenue capacity | Prior target |
| --- | --- | --- |
| Q4 2025 actual | $8M | — |
| Q3 2026 target | $35–40M | $20M |
| Exit 2026 target | $60M | — |
| Exit 2027 target | $130M | $70M |

These are management capacity targets, not orders.

### 3.3 Customer prepayments signed in 2026

Downstream is funding the expansion, which is the clearest signal that supply security rather
than price is the binding concern:

| Counterparty | Structure | Cash | Term |
| --- | --- | ---: | --- |
| Lumentum | Capacity reservation + supply, minimum annual commitment; deposits as shipment credits | $87.0M (2 x $43.5M) | to 2031-12-31 |
| Coherent | Master Development & Supply Agreement, 6-inch InP; AXT commits to expansion 2026–28 | $22.3M | to 2029-06 |
| Nanjing Casela | Long-term supply agreement | $22.3M | from 2027 |

Backlog exceeds $100M — more than two quarters of guided revenue — extending into 2027.
Lumentum is the supplier behind a large NVIDIA optics commitment, so the chain from GPU cluster
to AXT crystal furnace is now contractually visible end to end.

### 3.4 Vertical integration

Through JinMei, AXT purifies its own 6N/7N gallium and produces InP polycrystalline base
material; through BoYu it makes the pyrolytic boron nitride crucibles that crystal growth
happens *inside* — a consumable that constrains competitors and that AXT also sells to them.
With the raw material chain (indium, gallium, germanium, pBN) itself concentrated in China and
under export control, owning those steps is a genuine cost and continuity advantage. It is also
why the raw-materials segment grew to $10M last quarter: the whole compound-semi industry is
bidding for the same inputs.

---

## 4. The market

At the RAISE Summit on 2026-07-08, Lumentum CEO Michael Hurlston said the InP supply/demand
imbalance had surpassed DRAM and NAND, that shipments were running >30% short of customer demand
for EMLs and pump lasers, and that order sizes had moved from "hundreds of units typical of
traditional telecom customers to hundreds of millions." Lumentum is reported sold out through
2028 despite quadrupling output. Third-party estimates put 2025 global InP demand near 1.5–2.0M
wafer-equivalents against 600–700k of capacity. Post-controls, 6-inch InP wafer prices are
reported up ~250% to roughly $5,000.

> **Treat the volume figures with care.** The 2M-vs-600k comparison circulates widely but the
> unit ("pieces", "devices", "wafer-equivalents") is inconsistent across sources and the diameter
> mix is unstated — a 6-inch wafer yields ~400 laser die against ~250 for a 3-inch, so wafer
> counts and die counts tell different stories. The direction is corroborated by independent
> evidence (prepayments, sold-out positions, permit-gated backlog, simultaneous incumbent
> expansions). The precise multiple is not reliable.

### 4.1 Supply landscape

| Supplier | Position | Method / status | Announced expansion |
| --- | --- | --- | --- |
| Sumitomo Electric (JP) | Leader, often cited near 60% | Vertical Bridgman; 4-inch Fe-doped strength | ~JPY 18B to 3.1x FY2024 capacity by FY2028 |
| **AXT / Beijing Tongmei** | #2; AXT + Sumitomo ~80% combined | VGF; 2–4 inch in volume, 6-inch pilot | $632M raised; doubling in 2026 and again in 2027 |
| JX Advanced Metals (JP) | ~10% | Established supplier | Multi-year program; reported figures vary widely by source |
| Yunnan Germanium, Guangdong Xiandao, Zhuhai Dingtai Xinyuan, San'an (CN) | <10% combined | 4-inch in volume, 6-inch qualifying | Yunnan Germanium RMB 189M -> 450k wafers/yr, shipments +74% in 2025; San'an RMB 6.5B Wuhan 6-inch line |

**Coherent is a customer, not a substrate rival — a distinction the trade press routinely blurs.**
Coherent grows its own SiC and GaAs crystals but does *not* grow InP: it buys InP substrates
externally under three-to-five-year supply agreements (the AXT agreement above is one of them)
and performs epitaxy and device fabrication in-house. Its widely reported "6-inch InP" milestones
and the $650M Sherman, Texas expansion with NVIDIA are *device* wafer capacity at the layer
above, so that expansion **increases** substrate demand rather than adding competing supply.
The same applies to IQE, which appears on many InP vendor lists but is an epitaxy house.

**Market-share figures disagree and should be held loosely.** Reuters-sourced reporting puts AXT
and Sumitomo together near 80% with JX around 10%, and separately credits Sumitomo with ~60%
(implying AXT near 20%); Chinese industry sources put AXT as high as 35%. The decision-relevant
fact is the structure, not the split: three incumbents hold 80–90%, and the barrier is yield and
qualification rather than capital — roughly $60M reportedly buys 400k wafer-equivalents of
nameplate capacity but not the yield to run it.

### 4.2 The listed universe is almost empty

The bottleneck is one of the most discussed in AI infrastructure, and there is essentially one
liquid listed way to own it directly.

| Company | Listing | Access | Purity of exposure |
| --- | --- | --- | --- |
| **AXT** (Beijing Tongmei) | **AXTI** (Nasdaq) | Direct, liquid | High — InP 64.5% of Q2/26 revenue and all the growth |
| Sumitomo Electric | 5802 (Tokyo) | Tokyo session; US ADR **SMTOY** is unsponsored OTC and thin | Very low — InP inside a ~JPY 4tn conglomerate led by auto wiring harnesses and power cable |
| JX Advanced Metals | 5016 (Tokyo) | Tokyo session; no meaningful US line | Very low — sputtering targets and rolled copper foil dominate; compound-semi crystals not broken out |
| Yunnan Germanium (via Yunnan Xinyao) | 002428 (Shenzhen) | A-share, Stock Connect / QFII | Moderate — germanium mining plus GaAs/InP wafers |
| San'an Optoelectronics | 600703 (Shanghai) | A-share | Low — predominantly LED epitaxy |
| Guangdong Xiandao, Zhuhai Dingtai Xinyuan, Freiberger, Xiamen Powerway, Vital Materials | — | Private / not separately listed | — |

Adjacent liquid vehicles (Lumentum, Coherent, Fabrinet, and MOCVD toolmakers Veeco and Aixtron)
express the same optical-bottleneck thesis but sit on the **demand** side of the substrate.

### 4.3 The 4-inch to 6-inch transition is the competitive battleground

A 6-inch wafer yields ~400 usable laser die against ~250 for a 3-inch, and reported cost per die
falls to ~60–70% of the 3-inch level. Whoever qualifies 6-inch at production yield first gets a
structural cost advantage and relieves the shortage fastest. AXT's 6-inch program is explicitly
in "development / pilot production" — the company's own characterisation in the Coherent
agreement filing, alongside named risks of lower-than-expected yields and difficulty scaling
crystal growth. Sumitomo's expansion is a 6-inch line upgrade with mass production reported for
2028.

---

## 5. Risk register

Ranked by how much of the thesis each one breaks.

### 5.1 China export permits — structural, highest

China added InP substrates to its export control list on **2025-02-04**; GaAs and germanium went
on in **August 2023**. Every overseas customer order requires a separate MOFCOM permit; processing
has run ~60 business days, and there were effectively no InP permits for months before the first
was granted in late June 2025.

This is the mechanism behind AXT's own revenue volatility: Q3/25 InP hit $13.1M, Q4/25 fell to
$8.0M purely on permit timing, and Q4/25 guidance was missed for the same reason. Management calls
permits "the most significant challenge we currently face." It has hit customers directly —
Taiwanese epi houses VPEC and LandMark reported disruption from AXT permit delays — and North
American revenue fell from 8% to 2% of sales during the worst of it. **AXT does not control this
variable and cannot forecast it.**

### 5.2 Geographic and listing structure — structural

All substrate and raw-material production is in the PRC. Tongmei **withdrew its Shanghai STAR
Market IPO application on 2026-06-26** and pivoted to Hong Kong, triggering redemption rights on
~RMB 324.4M raised from eleven Chinese private equity funds; AXT says it can repay while
negotiating their participation in the new listing. Noncontrolling and redeemable noncontrolling
interests in Tongmei stood at ~14.5%. A US-listed holding company whose value is a Chinese
operating subsidiary being separately listed in Hong Kong is a structure that can compress the
parent's multiple regardless of operating performance — and it sits on the wrong side of both
governments' escalation options.

### 5.3 The bottleneck attracts the capital that ends it — cyclical

Every incumbent is expanding simultaneously (Sumitomo to 3.1x FY2024, JX on a multi-year program)
while $5,000 wafers and Beijing's permit regime give hyperscalers, governments and customers
overwhelming incentive to finance non-China supply. Chinese domestic producers are being pulled
forward by the same export controls that constrain AXT's exports: Yunnan Germanium shipments
+74% in 2025, and China targets 30% global share by 2030. The question is whether 2028 capacity
overshoots 2028 demand.

### 5.4 Customer concentration, now contractual — elevated

The prepayments that de-risk capacity also concentrate the customer base. Lumentum, Coherent and
Casela hold contractual claims on reserved capacity, and all three are laser makers exposed to
the same end demand — so their orders correlate rather than diversify.

### 5.5 Execution: 6-inch yield and the ramp — elevated

AXT is attempting to triple InP output in 2026 and roughly double again in 2027, in a process
where industry single-crystal yields are 15–25% and new capacity requires customer
requalification. The 6-inch program is pilot-stage by the company's own filing. Missing the ramp
costs margin non-linearly, in the same direction that produced the 8.2% trough in Q2/25.

### 5.6 Technology substitution — low near-term

Nothing on the horizon removes the need for a III–V gain material at 1310/1550 nm. Credible
long-run threats are cost-structure attacks rather than replacements: InP-on-GaAs engineered
substrates, quantum-dot lasers grown directly on silicon, and thin-film lithium niobate
modulators (which still need an InP laser in front of them). A 2030s risk to substrate volume
per link, not a near-term threat to the platform.

### 5.7 Valuation and dilution — elevated

The stock went from under $3 to $143.16 in May 2026 and trades near $60.86 — ~58% below the high,
still up many multiples year on year. TTM revenue is ~$126M against a ~$3.91B market cap; the
forward P/E of ~38 depends entirely on the ramp landing. The April raise added shares at the top
of the move, insiders including the CEO sold into strength in early June, and the stock has
repeatedly fallen on *good* news — what a crowded momentum position looks like. Price discovery
has run several quarters ahead of the financial statements.

One structural amplifier worth naming: because AXTI is the only liquid pure-play vehicle
(section 4.2), the entire theme's flow funnels into a single small float. That cuts both ways.

---

## 6. Falsifiers — what would settle the open questions

| When | What to watch |
| --- | --- |
| Q3 2026 results (~late Oct 2026) | **Did the ramp land, and did permits allow it?** Guidance is >=$66M, EPS $0.30–0.32, InP capacity target $35–40M. The tell is the gap between capacity and shipments: if capacity hits $40M and InP revenue lands well short, the constraint is permits, not demand — the core vulnerability quantified. |
| Ongoing | **Non-China revenue mix.** Management guided toward 40/60 non-China/China, with China above 50% in Q2/26 on laser-sector demand. Rising non-China share is direct evidence permits are flowing; falling share means the export regime is quietly re-routing AXT into the domestic Chinese market, where prices and competition are worse. |
| 2026–2027 | **6-inch qualification at a named customer.** The Coherent agreement runs to June 2029 and is explicitly a development program. Production-yield 6-inch shipments would validate both the cost structure and the exit-2027 $130M/quarter target. Continued silence, or a yield disclosure, is the bear signal. |
| 2027–2028 | **Whether the shortage survives the expansions.** Sumitomo at 3.1x FY2024, JX's program, China's domestic cohort and AXT's own tripling all arrive in roughly the same window. Watch the 6-inch spot price: if $5,000 holds through 2028 the bottleneck is structural; if it reverts toward pre-control levels, 45% gross margins were a cycle, not a moat. |

---

## Sources

Primary filings:

- [AXT Q2 2026 results, 8-K exhibit](https://www.sec.gov/Archives/edgar/data/0001051627/000143774926025061/ex_974537.htm)
- [AXT Q1 2026 results, 8-K exhibit](https://www.sec.gov/Archives/edgar/data/1051627/000143774926014204/ex_906119.htm)
- [AXT Form 10-Q, quarter ended 2026-06-30](https://www.sec.gov/Archives/edgar/data/1051627/000143774926027677/axti20260630_10q.htm)
- [AXT Form 10-K, FY2024](https://www.sec.gov/Archives/edgar/data/1051627/000155837025003004/axti-20241231x10k.htm) — product lines, applications, raw-material subsidiaries, PRC manufacturing
- [AXT 8-K, 2026-06-29](https://www.sec.gov/Archives/edgar/data/1051627/000143774926022984/axti20260629_8k.htm) — Tongmei STAR withdrawal, Hong Kong pivot, RMB 324.4M redemption rights
- [AXT–Coherent Master Development & Supply Agreement](https://www.stocktitan.net/sec-filings/AXTI/8-k-axt-inc-reports-material-event-a5cebc00919f.html)

Trade press and analysis:

- [AXT returns to profit on record InP revenue](https://www.semiconductor-today.com/news_items/2026/aug/axt-040826.shtml) — Semiconductor Today, 2026-08-04 (product-line split, capacity targets, guidance)
- [AXT Q1/26 revenue grows 17%](https://www.semiconductor-today.com/news_items/2026/may/axt-050526.shtml) — 2026-05-05
- [AXT Q4/25 constrained by permit delay](https://www.semiconductor-today.com/news_items/2026/mar/axt-090326.shtml) — 2026-03-09
- [AXT Q3/25 exceeds guidance after licences granted](https://www.semiconductor-today.com/news_items/2025/nov/axt-101125.shtml) — 2025-11-10
- [AXT–Lumentum long-term InP agreement](https://www.semiconductor-today.com/news_items/2026/jul/axt-lumentum-300726.shtml) — 2026-07-30
- [InP shortage as AI optical interconnect bottleneck](https://www.trendforce.com/news/2026/08/06/news-inp-shortage-emerges-as-ai-optical-interconnect-bottleneck/) — TrendForce, 2026-08-06
- [Sumitomo Electric JPY 18B InP expansion](https://www.trendforce.com/news/2026/07/13/news-sumitomo-electric-to-raise-inp-substrate-expansion-scale-with-jpy-18-billion/) — TrendForce, 2026-07-13
- China's control over InP exports threatens AI data centre rollout — Reuters; read via the [Yahoo Finance mirror](https://finance.yahoo.com/sectors/technology/articles/chinas-control-over-indium-phosphide-010212293.html) because the [Mining.com copy](https://www.mining.com/web/chinas-control-over-indium-phosphide-exports-threatens-ai-data-centre-rollout/) returns 403. Source of the 70% refined-indium share, the ~250% price move to ~$5,000, the 80%/10% share split, and the Yunnan Germanium capacity figures.
- [Lumentum's "worse than memory" warning](https://xenospectrum.com/en/lumentum-inp-ai-optics-shortage/) — RAISE Summit, 2026-07-08
- [Coherent moves 6-inch InP wafers into full production](https://convergedigest.com/coherent-moves-6-inch-indium-phosphide-wafers-into-full-production/)
- [Coherent and NVIDIA break ground on Texas InP fab](https://blogs.nvidia.com/blog/coherent-texas-ai-optical/)
- [Coherent's vertical integration strategy](https://www.chipstrat.com/p/coherents-vertical-integration-strategy) — confirms Coherent buys InP substrates externally
- [Indium Phosphide Takes the Spotlight](https://eu.36kr.com/en/p/3651344579993989) — 36Kr (Chinese supply chain, 4->6 inch die economics)
- [InP substrates for AI data center lasers](https://www.exponentialindustry.com/blog/2026-07-13-indium-phosphide-inp-substrate-ai-datacenter-lasers/) — 2026-07-13
- [Can AXT capture the value?](https://valueinvestus.com/articles/axti-ai-optical-bottleneck-indium-phosphide-analysis) — bear case framing

Market data:

- [AXTI quote and fundamentals](https://stockanalysis.com/stocks/axti/), retrieved 2026-09-04
- [Sumitomo Electric 5802 / SMTOY](https://www.investing.com/equities/sumitomo-electric-adr), [JX 5016](https://www.investing.com/equities/jx-advanced-metals), [Yunnan Germanium 002428](https://finance.yahoo.com/quote/002428.SZ/)

---

## Notes on method

Material properties (bandgaps, lattice-matched alloy ranges, fiber attenuation, etch-pit and
resistivity specifications) are standard published values for the material systems, not
measurements of a specific vendor's product. Financial figures are as reported by AXT — with the
single exception marked in section 3.1 — and were cross-checked for internal consistency: each
quarter's product-line figures sum to the reported total within rounding. Where sources conflict — market share above all — the conflict is stated
rather than resolved.
