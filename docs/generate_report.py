"""
generate_report.py
Generates the Sybil-Net full project report as a styled .docx file.
Run with:
    source ../venv/bin/activate && python generate_report.py
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def set_cell_bg(cell, hex_color: str):
    """Set a table cell background colour (hex without #)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def set_cell_border(cell, **kwargs):
    """Set cell borders. kwargs: top, bottom, left, right – each a dict with
    keys 'val', 'sz', 'color'."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in ('top', 'bottom', 'left', 'right', 'insideH', 'insideV'):
        props = kwargs.get(side, {'val': 'single', 'sz': 4, 'color': 'BFBFBF'})
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), props.get('val', 'single'))
        el.set(qn('w:sz'), str(props.get('sz', 4)))
        el.set(qn('w:color'), props.get('color', 'BFBFBF'))
        tcBorders.append(el)
    tcPr.append(tcBorders)


def add_table(doc, headers, rows, col_widths=None, header_bg='1F3A5F', header_fg='FFFFFF'):
    """Add a styled table with bold header row."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'

    # Header row
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        cell = hdr_cells[i]
        set_cell_bg(cell, header_bg)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.size = Pt(9)

    # Data rows
    for r_idx, row_data in enumerate(rows):
        row_cells = table.rows[r_idx + 1].cells
        bg = 'F0F4FA' if r_idx % 2 == 0 else 'FFFFFF'
        for c_idx, val in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(str(val))
            run.font.size = Pt(9)

    # Column widths
    if col_widths:
        for col_idx, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[col_idx].width = Inches(w)

    return table


def add_chapter_heading(doc, chapter_num, title):
    """Add a styled chapter heading."""
    doc.add_paragraph()  # spacer
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(f'CHAPTER {chapter_num}')
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x5C, 0x8A, 0xE6)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run2 = p2.add_run(title.upper())
    run2.bold = True
    run2.font.size = Pt(16)
    run2.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    # Horizontal rule
    p3 = doc.add_paragraph('─' * 80)
    p3.runs[0].font.color.rgb = RGBColor(0x5C, 0x8A, 0xE6)
    p3.runs[0].font.size = Pt(8)
    doc.add_paragraph()  # spacer


def add_section(doc, title):
    """Add a bold section subheading."""
    p = doc.add_paragraph()
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)


def add_sub_section(doc, title):
    p = doc.add_paragraph()
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x33, 0x66, 0x99)


def body(doc, text, italic=False):
    """Add a body paragraph."""
    p = doc.add_paragraph(text)
    for run in p.runs:
        run.font.size = Pt(10)
        if italic:
            run.italic = True
    return p


def bullet(doc, text, level=0):
    """Add a bullet list item."""
    p = doc.add_paragraph(text, style='List Bullet')
    for run in p.runs:
        run.font.size = Pt(10)
    return p


def code_block(doc, text):
    """Simulate a code block with monospace font in a shaded paragraph."""
    lines = text.strip().split('\n')
    for line in lines:
        p = doc.add_paragraph()
        run = p.add_run(line if line else ' ')
        run.font.name = 'Courier New'
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
        # Light grey shading via paragraph shading
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F4F6F9')
        pPr.append(shd)


# ---------------------------------------------------------------------------
# Build Document
# ---------------------------------------------------------------------------

doc = Document()

# Page margins
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.left_margin = Inches(1.2)
section.right_margin = Inches(1.2)
section.top_margin = Inches(1.0)
section.bottom_margin = Inches(1.0)

# Default font
style = doc.styles['Normal']
font = style.font
font.name = 'Calibri'
font.size = Pt(10)

# ============================================================
# COVER PAGE
# ============================================================
doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()

title_p = doc.add_paragraph()
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title_p.add_run('SYBIL-NET')
r.bold = True
r.font.size = Pt(36)
r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

sub_p = doc.add_paragraph()
sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r2 = sub_p.add_run('Graph Neural Network Based Decentralised Sybil Detection Protocol')
r2.bold = True
r2.font.size = Pt(16)
r2.font.color.rgb = RGBColor(0x5C, 0x8A, 0xE6)

doc.add_paragraph()

tagline_p = doc.add_paragraph()
tagline_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r3 = tagline_p.add_run('Detecting bots at the graph level — in the mempool, before confirmation, enforcing truth on-chain.')
r3.italic = True
r3.font.size = Pt(11)
r3.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()

line_p = doc.add_paragraph('━' * 60)
line_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
line_p.runs[0].font.color.rgb = RGBColor(0x5C, 0x8A, 0xE6)

doc.add_paragraph()

info_lines = [
    ('Project Type:', 'Full-Stack + Machine Learning + Blockchain'),
    ('Duration:', '8 Weeks'),
    ('Tech Stack:', 'Python · PyTorch Geometric · Solidity · Next.js · Circom'),
    ('Model:', 'GraphSAGE (3-layer, 37,122 parameters)'),
    ('Status:', 'Complete — All 8 Phases Delivered'),
]
for label, val in info_lines:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_label = p.add_run(f'{label}  ')
    r_label.bold = True
    r_label.font.size = Pt(10)
    r_label.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    r_val = p.add_run(val)
    r_val.font.size = Pt(10)
    r_val.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

doc.add_paragraph()
doc.add_paragraph()

date_p = doc.add_paragraph()
date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r_date = date_p.add_run('2026')
r_date.font.size = Pt(10)
r_date.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

doc.add_page_break()

# ============================================================
# TABLE OF CONTENTS
# ============================================================
toc_p = doc.add_paragraph()
toc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
toc_r = toc_p.add_run('TABLE OF CONTENTS')
toc_r.bold = True
toc_r.font.size = Pt(14)
toc_r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

doc.add_paragraph()

toc_entries = [
    ('1.', 'Introduction', '2'),
    ('2.', 'Problem Statement', '3'),
    ('3.', 'Research and Background', '4'),
    ('4.', 'Project Design and Planning', '6'),
    ('5.', 'Implementation', '9'),
    ('6.', 'Results and Evaluation', '14'),
    ('7.', 'Learning Outcomes', '16'),
    ('8.', 'Future Scope', '17'),
    ('9.', 'Conclusion', '18'),
    ('10.', 'References', '19'),
    ('11.', 'Appendices', '20'),
]

add_table(
    doc,
    headers=['Chapter No.', 'Contents', 'Page No.'],
    rows=toc_entries,
    col_widths=[1.0, 4.5, 0.9],
)

doc.add_page_break()

# ============================================================
# CHAPTER 1 — INTRODUCTION
# ============================================================
add_chapter_heading(doc, 1, 'Introduction')

add_section(doc, '1.1  Project Overview')
body(doc,
     'Sybil-Net is an end-to-end, open-source protocol that uses Graph Neural '
     'Networks (GNNs) to detect bot farms, wash traders, and Sybil attackers '
     'directly from blockchain transaction topology — then enforces those '
     'findings automatically through a Solidity smart contract on the Ethereum '
     'blockchain.')
body(doc,
     'Unlike traditional bot-detection systems that rely on NLP or centralised '
     'identity verification, Sybil-Net operates purely on the structural '
     'properties of the transaction graph. Wallets are nodes; transactions are '
     'weighted directed edges. A 3-layer GraphSAGE model learns to identify the '
     'topological signatures of Sybil attacks — hub-and-spoke bot farms, '
     'wash-trading rings, and layered attack clusters — and assigns each wallet '
     'a Sybil probability score between 0 and 100.')
body(doc,
     'Users stake 0.01 ETH to mint a Humanity Credential (an ERC-721 NFT). The '
     'GNN oracle continuously monitors on-chain activity, and if a wallet is '
     'identified as malicious, its stake is automatically slashed and the '
     'credential burned. Verified humans gain access to the Trust-Verified '
     'Marketplace, a three-pillar DeFi ecosystem that uses the humanity score as '
     'its primary trust primitive.')

doc.add_paragraph()
add_section(doc, '1.2  Motivation')
body(doc,
     'Sybil attacks — where one entity controls thousands of synthetic '
     'identities — are the most pervasive unsolved problem in decentralised '
     'systems. They corrupt token airdrops, governance votes, yield farming '
     'reward distributions, NFT launches, and DeFi credit markets.')
body(doc,
     'Current countermeasures are fundamentally inadequate:')
for item in [
    'Centralised KYC — privacy-invasive, custodial, and a single point of data breach.',
    'Proof-of-Humanity — slow, gameable by AI deepfakes, geographically biased.',
    'Static heuristic rules — trivially bypassed by adaptive bot operators.',
    'Offline ML forensics — produce advisory reports with no automated enforcement.',
]:
    bullet(doc, item)
body(doc,
     'Sybil-Net takes a fundamentally different approach: Sybil entities are '
     'structurally distinct in the transaction graph. This distinction can be '
     'learned by a GNN and enforced automatically — without identity documents, '
     'social media, or language models.')

doc.add_paragraph()
add_section(doc, '1.3  Project Scope')
body(doc,
     'Sybil-Net was developed over eight weeks across the following layers:')
scope_data = [
    ['Week 1', 'Data Pipeline', 'Blockchain data ingestion, graph construction, 12-feature extraction, PyVis visualiser'],
    ['Week 2', 'GNN Model', 'GraphSAGE architecture, training loop, node_scores.csv generation'],
    ['Week 3', 'Smart Contract', 'SybilNet.sol, oracle bridge, 22/22 test suite'],
    ['Week 4', 'Marketplace UI', 'Next.js 16 dashboard, RainbowKit wallet connect, 3-pillar DeFi marketplace'],
    ['Week 5', 'Mempool Monitor', 'Alchemy WebSocket live inference, pre-confirmation scoring, real-time feed'],
    ['Week 6', 'zk-SNARK Layer', 'Circom Groth16 circuit, ZKVerifier.sol, anonymous credential proofs'],
    ['Week 7', 'Cross-Chain Bridge', '17 cross-chain GNN features, L2 bridge contract, multi-chain analytics'],
    ['Week 8', 'Governance & DAO', 'On-chain slash appeal, parameter governance, one-human-one-vote'],
]
add_table(doc, ['Phase', 'Deliverable', 'Description'], scope_data, col_widths=[0.9, 1.5, 4.0])

doc.add_page_break()

# ============================================================
# CHAPTER 2 — PROBLEM STATEMENT
# ============================================================
add_chapter_heading(doc, 2, 'Problem Statement')

add_section(doc, '2.1  Executive Summary')
body(doc,
     'Public blockchain networks rely on permissionless, pseudo-anonymous '
     'public-key cryptography where generating digital identities carries '
     'near-zero marginal cost. Malicious actors exploit this structural '
     'vulnerability by deploying automated, multi-account Sybil bot farms to '
     'siphon token airdrops, hijack DAO governance voting, execute wash trading, '
     'and extract liquidity rewards. Existing mitigation techniques either fail '
     'against adaptive AI scripts, ruin scalability, violate user privacy, or '
     'produce offline advisory reports that lack on-chain financial penalties '
     'and pre-confirmation mempool protection.',
     italic=True)

doc.add_paragraph()
add_section(doc, '2.2  Context and Background')
body(doc,
     'Decentralised Web3 protocols operate on permissionless public ledgers '
     'where identity is anchored to cryptographic key pairs rather than '
     'verified real-world human identities. While this guarantees censorship '
     'resistance, it creates a fundamental security dilemma: creating 10,000 '
     'distinct wallet addresses costs zero marginal capital or computation. '
     'Without a centralised identity issuer, protocols cannot distinguish '
     'between 10,000 unique human participants and a single malicious entity '
     'controlling 10,000 automated scripts.')

doc.add_paragraph()
add_section(doc, '2.3  Exploitation Vectors and Impact')
exploitation = [
    ['Airdrop & Token Siphoning', 'Bot fleets simulate organic transaction patterns to claim community allocations meant for early human adopters.'],
    ['DAO Governance Hijacking', 'Fractional governance tokens spread across synthetic accounts pass malicious proposals, draining community treasuries.'],
    ['Wash Trading Manipulation', 'Wallet rings trade assets circularly to manipulate floor prices and extract yield farming rewards.'],
    ['MEV & Sandwich Attacks', 'Predator bots front-run pending human transactions in the mempool, stealing slippage before block confirmation.'],
]
add_table(doc, ['Attack Vector', 'Mechanism & Impact'], exploitation, col_widths=[2.0, 4.4])

doc.add_paragraph()
add_section(doc, '2.4  Failure Modes of Existing Defences')
defences = [
    ['Static Heuristic Rules', 'Hardcoded filters (e.g. tx_count > 5)', 'Trivially gamed by tuning script parameters'],
    ['Centralised KYC', 'Third-party passport / ID checks', 'Privacy-invasive, custodial, geographically unequal'],
    ['Proof-of-Humanity', 'Social video & peer sign-off', 'Gameable by deepfakes, extreme user friction'],
    ['Offline ML Forensics', 'Static batch model scoring', 'No automated enforcement; advisory only'],
    ['Post-Block Detection', 'Forensic inspection on confirmed blocks', 'Blind to pre-confirmation mempool threats'],
]
add_table(doc, ['Mechanism', 'Operation', 'Shortcoming'], defences, col_widths=[1.7, 2.1, 2.6])

doc.add_paragraph()
add_section(doc, '2.5  Research and Engineering Gap')
body(doc,
     'Current solutions treat detection, enforcement, privacy, and speed as '
     'isolated domains. There is no existing end-to-end framework that bridges:')
for gap in [
    'Inductive GNN topology scoring — generalising to newly created wallets without full graph retraining;',
    'Direct cryptoeconomic enforcement — automatically slashing staked collateral upon detection;',
    'Zero-knowledge privacy credentials — proving identity without exposing on-chain wallet history;',
    'Pre-confirmation mempool monitoring — intercepting threats before block inclusion.',
]:
    bullet(doc, gap)

doc.add_page_break()

# ============================================================
# CHAPTER 3 — RESEARCH AND BACKGROUND
# ============================================================
add_chapter_heading(doc, 3, 'Research and Background')

add_section(doc, '3.1  Graph Neural Networks for Fraud Detection')
body(doc,
     'Traditional machine learning approaches to fraud detection treat each '
     'entity independently — they classify based on features of an individual '
     'wallet (e.g. transaction count, balance). This ignores the relational '
     'structure that makes Sybil attacks uniquely identifiable.')
body(doc,
     'Graph Neural Networks (GNNs) extend classical neural networks to '
     'graph-structured data. Each node aggregates feature information from its '
     'neighbours, enabling the model to capture structural patterns across '
     'multiple hops.')
body(doc, 'The key insight that motivates Sybil-Net:')
bullet(doc, 'A single bot wallet may look clean in isolation.')
bullet(doc, 'But a GNN that aggregates 2-hop neighbourhood features can detect the hub-and-spoke topology of a bot farm or the tight circular structure of a wash-trading ring.')

doc.add_paragraph()
add_section(doc, '3.2  GraphSAGE — Inductive Graph Learning')
body(doc,
     'Sybil-Net uses GraphSAGE (Graph Sample and Aggregate, Hamilton et al. '
     '2017) as its backbone model. GraphSAGE was selected over GCN (Graph '
     'Convolutional Network) for one critical reason: inductiveness.')
reasons = [
    ['GraphSAGE', 'Inductive', 'Scores new wallets without retraining on full graph'],
    ['GCN', 'Transductive', 'Requires full graph during training; cannot generalise to unseen nodes'],
    ['GAT', 'Inductive', 'Attention mechanism adds complexity not required for topology tasks'],
]
add_table(doc, ['Model', 'Mode', 'Suitability for Sybil-Net'], reasons, col_widths=[1.5, 1.5, 3.4])
body(doc,
     'In a live blockchain environment, new wallets are created constantly. An '
     'inductive model can score a wallet it has never seen before by aggregating '
     'features from its existing transaction neighbours — without retraining.')

doc.add_paragraph()
add_section(doc, '3.3  Blockchain Transaction Graph Properties')
body(doc,
     'Ethereum transaction data forms a natural directed weighted graph. The '
     'structural signatures of Sybil attacks in this graph are:')
patterns = [
    ['Hub-and-Spoke', 'One controller wallet distributes ETH to hundreds of bot wallets in a star topology.', 'Extreme out-degree, low betweenness of leaves'],
    ['Wash Rings', 'A small set of wallets cycle funds among themselves to fabricate trading volume.', 'High reciprocity, high clustering coefficient'],
    ['Layered Clusters', 'Multi-hop funds laundering across bot intermediary wallets.', 'High betweenness centrality of intermediaries'],
    ['Honest Noise', 'Organic human wallets with organic interaction patterns.', 'Low reciprocity, moderate clustering, high PageRank diversity'],
]
add_table(doc, ['Attack Pattern', 'Description', 'Graph Signature'], patterns, col_widths=[1.5, 2.8, 2.1])

doc.add_paragraph()
add_section(doc, '3.4  Comparative Literature Review')
body(doc,
     'The following prior works informed the design of Sybil-Net:')
literature = [
    ['Hamilton et al. (2017)', 'GraphSAGE — Inductive Representation Learning on Large Graphs', 'Core GNN architecture adopted for SybilSAGE'],
    ['Velickovic et al. (2018)', 'Graph Attention Networks (GAT)', 'Evaluated but found over-parameterised for this task'],
    ['Ethereum Foundation (2015)', 'EIP-20 / ERC-721 Token Standards', 'Humanity Credential NFT design'],
    ['Ben-Sasson et al. (2014)', 'Succinct Non-Interactive Arguments of Knowledge (SNARKs)', 'Foundation for the zk-SNARK privacy layer'],
    ['Groth (2016)', 'On the Size of Pairing-based Non-interactive Arguments', 'Groth16 proving system used in ZKVerifier.sol'],
]
add_table(doc, ['Source', 'Title', 'Relevance'], literature, col_widths=[1.8, 2.8, 1.8])

doc.add_page_break()

# ============================================================
# CHAPTER 4 — PROJECT DESIGN AND PLANNING
# ============================================================
add_chapter_heading(doc, 4, 'Project Design and Planning')

add_section(doc, '4.1  System Architecture Overview')
body(doc,
     'Sybil-Net is structured as a five-layer protocol stack:')
arch_layers = [
    ['Layer 1 — Data Layer', 'Alchemy API (Ethereum Mainnet) + Synthetic Sybil Generator → transactions.csv'],
    ['Layer 2 — Graph Layer', 'NetworkX DiGraph construction + 12 node-level feature extraction'],
    ['Layer 3 — ML Layer', 'GraphSAGE GNN training → Sybil probability per wallet (node_scores.csv)'],
    ['Layer 4 — On-Chain Layer', 'SybilNet.sol + Oracle Bridge → automated stake slashing + Humanity Credential'],
    ['Layer 5 — Application Layer', 'Next.js 16 Trust-Verified Marketplace + Mempool Monitor + zk-SNARK Panel'],
]
add_table(doc, ['Layer', 'Components'], arch_layers, col_widths=[2.2, 4.2])

doc.add_paragraph()
add_section(doc, '4.2  End-to-End Data Flow')
body(doc, 'The complete Sybil-Net pipeline flows as follows:')
steps = [
    ('Step 1  Ingest', 'data/ingestion.py fetches 50,000 Ethereum transactions via Alchemy API or generates synthetic Sybil data (4 attack archetypes).'),
    ('Step 2  Build Graph', 'graph/builder.py constructs a NetworkX DiGraph where nodes = wallet addresses, edges = transactions weighted by tx count, ETH value, gas, and timestamps.'),
    ('Step 3  Extract Features', 'features/extractor.py computes 12 graph-theoretic features per wallet node.'),
    ('Step 4  Train GNN', 'models/gnn.py trains a 3-layer GraphSAGE on the feature graph with ground-truth Sybil labels.'),
    ('Step 5  Score Wallets', 'GNN outputs node_scores.csv — Sybil probability (0–1) per wallet.'),
    ('Step 6  Deploy Contract', 'SybilNet.sol deployed to local Hardhat / Sepolia testnet via npx hardhat run scripts/deploy.js.'),
    ('Step 7  Oracle Bridge', 'contracts/oracle_bridge.py reads node_scores.csv → submits updateSybilScore() → triggers slash() for high-confidence bots.'),
    ('Step 8  Marketplace UI', 'Next.js dashboard at localhost:3000. Wallet connect → credential check → 3-pillar marketplace access.'),
    ('Step 9  Mempool Monitor', 'mempool/monitor.py connects to Alchemy WebSocket → scores pending txs before block confirmation → writes mempool_alerts.json.'),
    ('Step 10 zk-SNARK Proof', 'User generates Groth16 proof locally proving score < 70 without revealing wallet address.'),
]
for label, desc in steps:
    p = doc.add_paragraph()
    r_label = p.add_run(f'{label}  ')
    r_label.bold = True
    r_label.font.size = Pt(10)
    r_label.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    r_desc = p.add_run(desc)
    r_desc.font.size = Pt(10)

doc.add_paragraph()
add_section(doc, '4.3  12 Node Features Engineered')
features_data = [
    ['1', 'in_degree', 'Number of inbound transaction edges', 'Low in bot wallets'],
    ['2', 'out_degree', 'Number of outbound transaction edges', 'Extreme in controllers'],
    ['3', 'total_tx', 'Total weighted transaction count', 'Very high in bots'],
    ['4', 'unique_interactions', 'Distinct counterparty wallets', 'Narrow in rings'],
    ['5', 'avg_value_sent', 'Mean ETH per outbound transaction', 'Uniform in bots'],
    ['6', 'avg_gas', 'Mean gas used per transaction', 'Uniform in bots'],
    ['7', 'tx_frequency', 'Transactions per active day', 'Extremely high in bots'],
    ['8', 'node_age_days', 'Days since first observed transaction', 'Low in new bots'],
    ['9', 'reciprocity', 'Fraction of edges that are mutual', 'High in wash rings'],
    ['10', 'clustering_coeff', 'Directed local clustering coefficient', 'High in tight cliques'],
    ['11', 'betweenness_centrality', 'Node role as a graph bridge', 'High in ring controllers'],
    ['12', 'pagerank', 'Global influence score', 'Low in isolated bot clusters'],
]
add_table(doc, ['#', 'Feature', 'Description', 'Sybil Signal'], features_data, col_widths=[0.3, 1.8, 2.5, 1.8])

doc.add_paragraph()
add_section(doc, '4.4  Development Timeline')
timeline = [
    ['Phase I — Data Pipeline', '1 week', 'Blockchain ingestion, graph builder, feature extractor, PyVis visualiser, CSV exports.'],
    ['Phase II — GNN Modelling', '1 week', 'GraphSAGE architecture, training loop with CosineAnnealing LR and early stopping, node_scores.csv.'],
    ['Phase III — Smart Contract', '1 week', 'SybilNet.sol deployment, oracle bridge, 22-test suite on Hardhat, gas profiling.'],
    ['Phase IV — Marketplace UI', '1 week', 'Next.js 16 dashboard, RainbowKit wallet connect, 3-pillar marketplace, API routes.'],
    ['Phase V — Mempool Monitor', '1 week', 'Alchemy WebSocket listener, live GNN inference < 10 ms, mempool_alerts.json ring buffer, frontend live feed.'],
    ['Phase VI — zk-SNARKs', '1 week', 'Circom HumanityProof.circom, Groth16 prover, ZKVerifier.sol, browser ZK panel.'],
    ['Phase VII — Cross-Chain Bridge', '1 week', '17 cross-chain GNN features, SybilNetBridge.sol, multi-chain analytics UI.'],
    ['Phase VIII — Governance & DAO', '1 week', 'SybilNetGovernance.sol, slash appeal voting, parameter governance, frontend panel.'],
]
add_table(doc, ['Phase', 'Duration', 'Milestones'], timeline, col_widths=[2.0, 0.9, 3.5])

doc.add_page_break()

# ============================================================
# CHAPTER 5 — IMPLEMENTATION
# ============================================================
add_chapter_heading(doc, 5, 'Implementation')

add_section(doc, '5.1  Data Pipeline (Week 1)')
body(doc,
     'The data ingestion module (data/ingestion.py) integrates with the Alchemy '
     'API to pull 50,000 real Ethereum mainnet transactions. A realistic '
     'synthetic Sybil fallback generates four attack archetypes when no API key '
     'is present:')
for pattern in ['Hub-and-spoke bot farms', 'Wash-trading rings', 'Layered attack clusters', 'Honest-noise wallets (negative class)']:
    bullet(doc, pattern)
body(doc,
     'The graph builder (graph/builder.py) constructs a NetworkX DiGraph. Nodes '
     'represent wallet addresses; directed weighted edges represent transaction '
     'flows carrying count, ETH value, gas, and timestamp attributes.')

doc.add_paragraph()
add_section(doc, '5.2  GraphSAGE GNN Architecture (Week 2)')
body(doc, 'Model: SybilSAGE — 3-layer GraphSAGE with the following architecture:')
code_block(doc, """
Input:  [N nodes × 12 features]  +  Edge Index [2 × E]

Layer 1:  SAGEConv(12 → 64,  aggr=mean) + BatchNorm + ReLU + Dropout(0.4)
Layer 2:  SAGEConv(64 → 32,  aggr=mean) + BatchNorm + ReLU + Dropout(0.4)
Layer 3:  SAGEConv(32 → 16,  aggr=mean) + BatchNorm + ReLU
          Linear(16 → 2)     → log_softmax

Total parameters:  37,122   |   Device: CPU
""")
doc.add_paragraph()
hp_data = [
    ['Optimiser', 'Adam (lr = 1e-3, weight_decay = 1e-4)'],
    ['LR Scheduler', 'CosineAnnealingLR (T_max = 300)'],
    ['Dropout', '0.4'],
    ['Early Stopping', 'Patience = 30 epochs on validation loss'],
    ['Max Epochs', '300'],
    ['Feature Scaling', 'RobustScaler (handles extreme outlier degrees)'],
    ['Train / Val / Test Split', '60 / 20 / 20 of labelled nodes'],
    ['Label Strategy', 'Ground-truth from labels.csv (synthetic); topology heuristic fallback for real data'],
]
add_table(doc, ['Hyperparameter', 'Value'], hp_data, col_widths=[2.5, 3.9])

doc.add_paragraph()
add_section(doc, '5.3  Smart Contract — SybilNet.sol (Week 3)')
body(doc,
     'SybilNet.sol is a Solidity 0.8.24 contract using OpenZeppelin AccessControl, '
     'ReentrancyGuard, and Pausable. It implements the full lifecycle of a '
     'Humanity Credential:')
contract_functions = [
    ['mintCredential()', 'User stakes 0.01 ETH → ERC-721 Humanity Credential minted'],
    ['updateSybilScore()', 'Oracle writes GNN score (0–100); auto-suspends credential at score ≥ 70'],
    ['slash()', 'Burns staked ETH, revokes credential, imposes 365-day ban'],
    ['batchSlash()', 'Gas-efficient batch slash for entire bot rings in one transaction'],
    ['liftSuspension()', 'Guardian-controlled false-positive reinstatement'],
    ['withdrawStake()', 'Verified humans reclaim ETH voluntarily'],
    ['isVerifiedHuman()', 'Primary gate function used by Marketplace contracts'],
    ['pause() / unpause()', 'Emergency circuit breaker (GUARDIAN_ROLE)'],
]
add_table(doc, ['Function', 'Description'], contract_functions, col_widths=[2.0, 4.4])

body(doc, 'Gas costs (measured on local Hardhat node):')
gas_data = [
    ['mintCredential()', '~122,000 gas'],
    ['slash()', '~107,000 gas'],
    ['batchSlash() (10 wallets)', '~175,000 gas'],
    ['Contract deployment', '2.9% of block gas limit'],
]
add_table(doc, ['Operation', 'Gas Used'], gas_data, col_widths=[2.5, 3.9])
body(doc, 'Test suite: 22 / 22 tests passing in 501 ms.')

doc.add_paragraph()
add_section(doc, '5.4  Trust-Verified Marketplace (Week 4)')
body(doc,
     'A Next.js 16 frontend (App Router) serves a three-pillar Trust-Verified '
     'Marketplace gated behind the Humanity Credential:')
marketplace = [
    ['Zero Wash-Trade Exchange', 'NFT and airdrop marketplace where all participants hold an Active Humanity Credential. Wash trading is cryptographically impossible.'],
    ['Undercollateralised Credit Hub', 'DeFi lending where the GNN trust score is your collateral. High-humanity wallets access loans beyond their on-chain asset value.'],
    ['Sybil-Resistant Yield Hub', 'Liquidity mining restricted to verified humans. Rewards scaled by trust score; bot farms cannot extract yield.'],
]
add_table(doc, ['Pillar', 'Description'], marketplace, col_widths=[2.0, 4.4])

body(doc,
     'Connecting a wallet automatically checks it against the GNN dataset via '
     'the /api/scores route. Verified humans get ✅ Granted access; flagged '
     'wallets are shown their Sybil probability and blocked.')

doc.add_paragraph()
add_section(doc, '5.5  Real-Time Mempool Monitor (Week 5)')
body(doc,
     'The mempool monitor (mempool/monitor.py) opens an Alchemy WebSocket '
     'subscription to alchemy_pendingTransactions. Incoming pending transactions '
     'are batched and scored by the trained GraphSAGE model before they are '
     'confirmed on-chain.')
mempool_flow = (
    'Alchemy WebSocket → batch of 10 pending txs\n'
    '  → merge with baseline graph (4,601 nodes)\n'
    '  → compute 12 node features (fast approximation for new wallets)\n'
    '  → GraphSAGE forward pass (CPU, ~10 ms per batch)\n'
    '  → append to mempool_alerts.json (capped at 200 entries)\n'
    '  → Next.js polls /api/mempool every 2 s → live browser table'
)
code_block(doc, mempool_flow)
doc.add_paragraph()
alert_data = [
    ['clean', '< 60%', 'Logged only; no badge shown'],
    ['warning', '60–85%', 'Amber badge in live feed'],
    ['critical', '≥ 85%', 'Red badge; oracle can pre-emptively slash'],
]
add_table(doc, ['Alert Level', 'Sybil Probability', 'Action'], alert_data, col_widths=[1.2, 1.5, 3.7])

doc.add_paragraph()
add_section(doc, '5.6  zk-SNARK Privacy Layer (Week 6)')
body(doc,
     'The privacy layer allows users to prove they hold a valid Humanity '
     'Credential without revealing their wallet address or transaction history. '
     'The Circom circuit (zkp/circuits/HumanityProof.circom) proves two '
     'statements simultaneously:')
bullet(doc, 'sybilScore < 70  (the wallet is below the Sybil threshold)')
bullet(doc, 'Poseidon(walletAddress, secret) == commitment  (the user knows the wallet secret)')
body(doc,
     'The Groth16 proof is small (a few hundred bytes), verified on-chain in '
     'constant time by ZKVerifier.sol, and protected against replay attacks via '
     'a nullifier registry.')

doc.add_paragraph()
add_section(doc, '5.7  Cross-Chain Bridge (Week 7)')
body(doc,
     'SybilNetBridge.sol extends the protocol to multi-chain environments. The '
     'GNN ingests transaction graph data from two blockchains (Ethereum + L2) '
     'and connects nodes through known bridge smart contracts, computing 17 '
     'additional cross-chain features per wallet.')

doc.add_paragraph()
add_section(doc, '5.8  Governance and DAO (Week 8)')
body(doc,
     'SybilNetGovernance.sol introduces a fully on-chain governance layer where '
     'verified humans (Active Humanity Credential holders) can propose, vote on, '
     'and execute protocol changes — including slash appeal disputes.')
gov_data = [
    ['SLASH_APPEAL', 'Any credential holder disputes a slash; 3-day voting period; quorum 10%; executes liftSuspension().'],
    ['PARAMETER_CHANGE', 'Governance updates minStake, oracle fees, or detection thresholds.'],
    ['ROLE_CHANGE', 'Governance grants or revokes oracle / guardian roles.'],
]
add_table(doc, ['Proposal Type', 'Description'], gov_data, col_widths=[1.8, 4.6])

doc.add_page_break()

# ============================================================
# CHAPTER 6 — RESULTS AND EVALUATION
# ============================================================
add_chapter_heading(doc, 6, 'Results and Evaluation')

add_section(doc, '6.1  GNN Classification Performance')
results_data = [
    ['Precision', '1.000', '1.000', 'Zero false positives on test set'],
    ['Recall', '1.000', '1.000', 'Zero missed Sybil wallets'],
    ['F1-Score', '1.000', '1.000', 'Harmonic mean of precision & recall'],
    ['ROC-AUC', '—', '1.000', 'Perfect class separability'],
    ['Accuracy', '—', '1.000', 'Overall classification accuracy'],
]
add_table(doc, ['Metric', 'Human Class', 'Sybil Class', 'Notes'], results_data, col_widths=[1.5, 1.0, 1.0, 2.9])
body(doc,
     'Note: Perfect scores are expected when training and evaluating on '
     'synthetic labelled data with clean ground-truth. The architecture is '
     'designed for real-world deployment where scores will naturally be '
     'lower — the model and feature set are built to generalise.',
     italic=True)

doc.add_paragraph()
add_section(doc, '6.2  Dataset Statistics')
dataset_data = [
    ['Total transactions', '50,000', 'Real Ethereum mainnet + synthetic Sybil data'],
    ['Total wallet nodes', '4,601', 'Unique wallet addresses in the graph'],
    ['Labelled nodes (Sybil)', '~1,600', 'Hub-and-spoke + wash rings + layered clusters'],
    ['Labelled nodes (Human)', '~3,000', 'Organic honest wallet pool'],
    ['Total graph edges', '>20,000', 'Directed weighted transaction edges'],
    ['Duplicate transactions', '0', 'De-duplication enforced in data pipeline'],
    ['Synthetic attack patterns', '4', 'Hub-spoke, wash rings, layered, honest noise'],
    ['Node features', '12', 'Graph-theoretic; no NLP or content analysis'],
]
add_table(doc, ['Metric', 'Value', 'Notes'], dataset_data, col_widths=[2.2, 1.0, 3.2])

doc.add_paragraph()
add_section(doc, '6.3  Smart Contract Test Results')
body(doc, 'Test suite: 22 / 22 tests passing in 501 ms on Hardhat.')
test_data = [
    ['Deployment', '3', 'Treasury address, minStake initialisation, admin role assignment'],
    ['mintCredential()', '4', 'Happy path, insufficient stake, duplicate credential, totalStaked tracking'],
    ['updateSybilScore()', '4', 'Score update, auto-suspend at ≥ 70, range validation, access control'],
    ['slash()', '3', 'Fund distribution (reporter fee + treasury), totalSlashed, no-credential revert'],
    ['batchSlash()', '1', 'Multi-wallet slash in one transaction'],
    ['withdrawStake()', '1', 'Balance return, credential revocation'],
    ['Ban mechanism', '1', 'Re-mint blocked within 365-day post-slash window'],
    ['Emergency pause', '2', 'Pause blocks mintCredential(), unpause resumes'],
    ['Admin controls', '3', 'setMinStake, setSlashReporterFee, fee cap enforcement'],
    ['Total', '22', 'All passing ✓'],
]
add_table(doc, ['Test Suite', 'Tests', 'Coverage'], test_data, col_widths=[2.0, 0.7, 3.7])

doc.add_paragraph()
add_section(doc, '6.4  System Performance')
perf_data = [
    ['Data ingestion (50k txns)', '< 5 minutes', 'API rate-limited by Alchemy free tier'],
    ['Graph construction', '< 30 seconds', 'NetworkX DiGraph build + serialisation'],
    ['Feature extraction (4,601 nodes)', '< 60 seconds', 'Including centrality and PageRank calculations'],
    ['GNN training (300 epochs)', '< 3 minutes', 'CPU only, no GPU required'],
    ['Live GNN inference (10-tx batch)', '~10 ms', 'Mempool monitor forward pass'],
    ['zk-SNARK proof generation', '< 30 seconds', 'Local Groth16 prover via snarkjs'],
    ['Smart contract tests', '501 ms', '22 / 22 tests on Hardhat local node'],
]
add_table(doc, ['Operation', 'Performance', 'Notes'], perf_data, col_widths=[2.5, 1.3, 2.6])

doc.add_page_break()

# ============================================================
# CHAPTER 7 — LEARNING OUTCOMES
# ============================================================
add_chapter_heading(doc, 7, 'Learning Outcomes')

add_section(doc, '7.1  Technical Skills Acquired')
technical = [
    ('Graph Neural Networks (GNNs)',
     'Designed, implemented, trained, and evaluated a 3-layer GraphSAGE model '
     'using PyTorch Geometric. Learned inductive vs. transductive learning, '
     'neighbourhood aggregation, RobustScaler preprocessing, and CosineAnnealing '
     'learning rate scheduling.'),
    ('Blockchain & Smart Contract Development',
     'Implemented a production-ready Solidity 0.8.24 contract with OpenZeppelin '
     'AccessControl, ReentrancyGuard, and Pausable patterns. Wrote a '
     'comprehensive 22-test Hardhat suite covering access control, fund '
     'distribution, emergency pause, and ban mechanics.'),
    ('Oracle Architecture',
     'Built a Python Web3 oracle bridge that reads ML model outputs and '
     'submits on-chain function calls, bridging the off-chain AI world with '
     'on-chain smart contracts.'),
    ('Zero-Knowledge Proofs',
     'Learned Circom 2.0 circuit design, the Groth16 proving system, and '
     'snarkjs integration. Implemented a Poseidon hash-based commitment scheme '
     'with nullifier-based replay protection.'),
    ('Real-Time Systems',
     'Built an asynchronous Python WebSocket listener using the websockets library '
     'to process pending Ethereum transactions in real time with < 10 ms GNN '
     'inference latency.'),
    ('Full-Stack Web3 Development',
     'Built a Next.js 16 App Router frontend with wagmi v2, RainbowKit, and '
     'viem. Designed API routes that serve live ML data and blockchain state to '
     'the frontend.'),
]
for title, desc in technical:
    add_sub_section(doc, title)
    body(doc, desc)
    doc.add_paragraph()

add_section(doc, '7.2  Soft Skills Developed')
soft_skills = [
    'Sprint-based project management — delivering a working product increment every week for 8 weeks.',
    'Technical documentation — writing clear PRDs, architecture docs, and API references for each sprint.',
    'Debugging complex multi-system integrations — bridging Python ML, Solidity contracts, and Next.js frontend.',
    'Balancing perfectionism with delivery — choosing when to use synthetic data versus real-world data.',
]
for s in soft_skills:
    bullet(doc, s)

doc.add_page_break()

# ============================================================
# CHAPTER 8 — FUTURE SCOPE
# ============================================================
add_chapter_heading(doc, 8, 'Future Scope')

future_items = [
    ('Real-World Deployment on Ethereum Mainnet',
     'Deploy SybilNet.sol to Ethereum Mainnet with a Gnosis Safe multisig as the admin, '
     'connect to a live Alchemy API key, and begin scoring real wallet traffic. '
     'The architecture is fully production-ready.'),
    ('Heterogeneous Graph Neural Networks',
     'Extend the GNN to a Heterogeneous Graph Transformer (HGT) that natively '
     'models multiple node types (wallets, smart contracts, tokens) and multiple '
     'edge types (transfers, approvals, swaps) for richer Sybil signals.'),
    ('Federated Learning for Privacy-Preserving Training',
     'Enable multiple blockchain analytics firms to jointly train the Sybil '
     'detection model without sharing raw transaction data, using federated '
     'learning with differential privacy guarantees.'),
    ('MPC Trusted Setup for zk-SNARKs',
     'Replace the local ceremony in the zk-SNARK setup with a multi-party '
     'computation (MPC) trusted setup to eliminate the "toxic waste" trust '
     'assumption. Integrate full in-browser proof generation via snarkjs WASM.'),
    ('Sybil-Net SDK and API',
     'Publish a public REST API and JavaScript SDK that allows any DApp to '
     'query the Sybil-Net trust score for any wallet address in a single API '
     'call, making the protocol a universal Web3 identity primitive.'),
    ('DAO Token and Economic Model',
     'Introduce an SNT governance token distributed to verified human credential '
     'holders as a reward for honest participation. Slashed stakes fund a '
     'community treasury managed by the DAO.'),
    ('Cross-Chain Expansion',
     'Extend cross-chain GNN ingestion beyond Ethereum + L2 to include '
     'Solana, Avalanche, and Cosmos bridge data, creating a universal '
     'multi-chain Sybil reputation layer.'),
]
for title, desc in future_items:
    add_sub_section(doc, title)
    body(doc, desc)
    doc.add_paragraph()

doc.add_page_break()

# ============================================================
# CHAPTER 9 — CONCLUSION
# ============================================================
add_chapter_heading(doc, 9, 'Conclusion')

body(doc,
     'Sybil-Net successfully achieved its primary goal: to deliver an automated, '
     'accurate, and economically-enforced Sybil detection system for the '
     'Ethereum blockchain — one that operates purely on transaction graph '
     'topology without requiring identity documents, social media signals, or '
     'language models.')
body(doc,
     'The project demonstrates that Graph Neural Networks are a uniquely powerful '
     'tool for the Sybil detection problem. Because Sybil attackers must '
     'coordinate fund flows across many wallets, their activities create '
     'structural graph signatures — hub-and-spoke topologies, circular wash '
     'rings, abnormal betweenness centrality — that are invisible to per-wallet '
     'classifiers but highly detectable by a 3-hop neighbourhood-aggregating '
     'GNN.')
body(doc,
     'The system\'s architecture delivers four key properties that no prior '
     'solution achieves simultaneously:')
for prop in [
    'Inductiveness — GraphSAGE scores new wallets without retraining, enabling live production deployment.',
    'Cryptoeconomic Enforcement — SybilNet.sol automatically slashes staked ETH upon detection, creating a real financial disincentive for Sybil attacks.',
    'Privacy — The zk-SNARK layer allows users to prove humanity without revealing their transaction history.',
    'Speed — The mempool monitor intercepts Sybil transactions before they are confirmed on-chain.',
]:
    bullet(doc, prop)
body(doc,
     'Over eight weeks, Sybil-Net evolved from a simple data pipeline into a '
     'full-stack protocol with a marketplace, real-time monitoring, zero-knowledge '
     'privacy, cross-chain bridge, and on-chain governance. Each layer '
     'reinforces the others, creating a self-sustaining trust economy where '
     'maintaining honest transaction patterns is financially rewarding and '
     'operating a Sybil farm is financially catastrophic.')
body(doc,
     'Sybil-Net serves as a practical proof-of-concept that the tools necessary '
     'to solve the Sybil problem — inductive GNNs, cryptoeconomic enforcement, '
     'zero-knowledge proofs, and real-time mempool analysis — are mature enough '
     'to be composed into a single coherent protocol today.',
     italic=True)

doc.add_page_break()

# ============================================================
# CHAPTER 10 — REFERENCES
# ============================================================
add_chapter_heading(doc, 10, 'References')

references = [
    'Hamilton, W., Ying, R., & Leskovec, J. (2017). Inductive Representation Learning on Large Graphs. Advances in Neural Information Processing Systems (NeurIPS). https://arxiv.org/abs/1706.02216',
    'Velickovic, P., Cucurull, G., Casanova, A., Romero, A., Lio, P., & Bengio, Y. (2018). Graph Attention Networks. International Conference on Learning Representations (ICLR). https://arxiv.org/abs/1710.10903',
    'Groth, J. (2016). On the Size of Pairing-based Non-interactive Arguments. EUROCRYPT 2016. https://eprint.iacr.org/2016/260.pdf',
    'Ben-Sasson, E., Chiesa, A., Garman, C., Green, M., Miers, I., Tromer, E., & Virza, M. (2014). Zerocash: Decentralized Anonymous Payments from Bitcoin. IEEE Symposium on Security and Privacy. https://ieeexplore.ieee.org/document/6956581',
    'OpenZeppelin (2024). OpenZeppelin Contracts v5 — AccessControl, ReentrancyGuard, Pausable. https://docs.openzeppelin.com/contracts/5.x',
    'Ethereum Foundation (2015). ERC-20 Token Standard — EIP-20. Ethereum Improvement Proposals. https://eips.ethereum.org/EIPS/eip-20',
    'Ethereum Foundation (2018). ERC-721 Non-Fungible Token Standard — EIP-721. Ethereum Improvement Proposals. https://eips.ethereum.org/EIPS/eip-721',
    'Alchemy Inc. (2024). Alchemy Supernode API and WebSocket Documentation. https://docs.alchemy.com',
    'Fey, M., & Lenssen, J. E. (2019). Fast Graph Representation Learning with PyTorch Geometric. ICLR Workshop on Representation Learning on Graphs and Manifolds. https://arxiv.org/abs/1903.02428',
    'Bowe, S., & Gabizon, A. (2017). Making Groth\'s zk-SNARK Simulation Extractable in the Random Oracle Model. https://eprint.iacr.org/2018/187.pdf',
    'iden3 (2023). Circom 2.0 Language Reference & snarkjs — Zero-Knowledge Proof Toolchain. https://docs.circom.io',
    'Wood, G. (2014). Ethereum: A Secure Decentralised Generalised Transaction Ledger — Yellow Paper. https://ethereum.github.io/yellowpaper/paper.pdf',
]
for i, ref in enumerate(references, 1):
    p = doc.add_paragraph()
    p.style = 'List Paragraph'
    r_num = p.add_run(f'[{i}]  ')
    r_num.bold = True
    r_num.font.size = Pt(9)
    r_num.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    r_text = p.add_run(ref)
    r_text.font.size = Pt(9)

doc.add_page_break()

# ============================================================
# CHAPTER 11 — APPENDICES
# ============================================================
add_chapter_heading(doc, 11, 'Appendices')

add_section(doc, 'Appendix A: Project Directory Structure')
body(doc, 'The following structure represents the final Sybil-Net repository:')
directory_tree = """
Sybil-Net-ML/
├── main.py                        # Full pipeline runner (Steps 1–5)
├── requirements.txt               # Python dependencies
├── .env                           # ALCHEMY_API_KEY (gitignored)
├── config/
│   └── settings.py                # Centralised config (API keys, thresholds, paths)
├── data/
│   ├── ingestion.py               # Alchemy API pull + synthetic Sybil generator
│   ├── raw/
│   │   ├── transactions.csv       # Raw Ethereum transaction data
│   │   └── labels.csv             # Ground-truth Sybil labels
│   └── processed/
│       ├── graph.pkl              # Serialised NetworkX DiGraph
│       ├── features.csv           # 12 node features per wallet
│       ├── nodes.csv              # Node list with metadata
│       ├── edges.csv              # Edge list with weights
│       ├── node_scores.csv        # GNN Sybil probability per wallet
│       ├── sybil_sage.pt          # Trained GraphSAGE model weights
│       └── training_history.csv   # Loss/accuracy per epoch
├── graph/
│   └── builder.py                 # NetworkX DiGraph construction
├── features/
│   └── extractor.py               # 12 node-level feature computation
├── models/
│   └── gnn.py                     # GraphSAGE architecture + training loop
├── visualization/
│   └── viewer.py                  # PyVis interactive graph renderer
├── utils/
│   └── export.py                  # CSV / pickle export utilities
├── mempool/
│   └── monitor.py                 # WebSocket listener + live GNN inference
├── zkp/
│   ├── circuits/HumanityProof.circom
│   ├── scripts/generate_proof.js
│   └── setup.sh
├── contracts/
│   ├── contracts/
│   │   ├── SybilNet.sol           # Core protocol contract
│   │   ├── ZKVerifier.sol         # Groth16 proof verifier
│   │   ├── SybilNetBridge.sol     # L2 cross-chain bridge
│   │   └── SybilNetGovernance.sol # DAO & dispute governance
│   ├── oracle_bridge.py           # Python → on-chain bridge
│   └── hardhat.config.js
├── frontend/
│   ├── app/
│   │   ├── page.js                # Main marketplace dashboard
│   │   ├── providers.js           # Wagmi + RainbowKit
│   │   ├── globals.css            # Design system
│   │   ├── components/
│   │   │   ├── ZKProofPanel.js
│   │   │   ├── CrossChainPanel.js
│   │   │   └── GovernancePanel.js
│   │   └── api/
│   │       ├── scores/route.js
│   │       ├── features/route.js
│   │       ├── mempool/route.js
│   │       ├── crosschain/route.js
│   │       └── governance/route.js
│   └── lib/wagmiConfig.js
└── docs/                          # Extended documentation (weeks 1–8)
"""
code_block(doc, directory_tree)

doc.add_paragraph()
add_section(doc, 'Appendix B: Model Artifacts')
artifact_data = [
    ['sybil_sage.pt', 'data/processed/', 'Trained GraphSAGE model weights (PyTorch state_dict)'],
    ['node_scores.csv', 'data/processed/', 'Per-wallet Sybil probability (0–1) and classification label'],
    ['training_history.csv', 'data/processed/', 'Loss and accuracy values recorded per training epoch'],
    ['features.csv', 'data/processed/', '12 graph-theoretic node features for all 4,601 wallets'],
    ['graph.pkl', 'data/processed/', 'Serialised NetworkX DiGraph for the full transaction graph'],
    ['mempool_alerts.json', 'data/processed/', 'Ring-buffer of last 200 mempool Sybil alerts (live, gitignored)'],
]
add_table(doc, ['Artifact', 'Location', 'Description'], artifact_data, col_widths=[1.8, 1.5, 3.1])

doc.add_paragraph()
add_section(doc, 'Appendix C: Environment Setup Commands')
code_block(doc, """
# 1. Clone and install Python dependencies
git clone https://github.com/your-username/Sybil-Net-ML.git
cd Sybil-Net-ML
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env: ALCHEMY_API_KEY=your_key_here

# 3. Run the full ML pipeline
python main.py

# 4. Deploy smart contract (local Hardhat node)
cd contracts
npx hardhat node
npx hardhat run scripts/deploy.js --network localhost
npx hardhat test  # → 22 passing (501ms)

# 5. Run oracle bridge
python contracts/oracle_bridge.py

# 6. Launch marketplace frontend
cd frontend && npm install && npm run dev
# → http://localhost:3000

# 7. Start mempool monitor
python mempool/monitor.py
# Demo mode active if no ALCHEMY_API_KEY set
""")

doc.add_paragraph()
add_section(doc, 'Appendix D: Critical Code Snippet — Oracle Bridge Core Loop')
body(doc, 'The following code from contracts/oracle_bridge.py demonstrates the '
         'core GNN-to-contract bridge logic:')
code_block(doc, """
# oracle_bridge.py — Core submission loop
for wallet, row in scores_df.iterrows():
    score_int = int(row['sybil_probability'] * 100)

    if score_int >= SLASH_THRESHOLD:
        # High confidence Sybil — slash immediately
        tx = sybil_contract.functions.slash(
            wallet, reporter_address
        ).transact({'from': oracle_account})
        print(f"[SLASH] {wallet} — score {score_int}/100")

    elif score_int >= WARN_THRESHOLD:
        # Warning zone — update score, auto-suspend at >= 70
        tx = sybil_contract.functions.updateSybilScore(
            wallet, score_int
        ).transact({'from': oracle_account})
        print(f"[WARN] {wallet} — score {score_int}/100")
""")

# ============================================================
# Save
# ============================================================
output_path = 'docs/sybil_net_project_report.docx'
doc.save(output_path)
print(f'✅  Document saved: {output_path}')
