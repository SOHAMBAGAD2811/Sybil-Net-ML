# Sybil-Net

Sybil-Net is a Graph Neural Network Based Decentralized Reputation Protocol. This repository contains the data pipeline and network topology foundation (Week 1).

## Features

- **Data Ingestion**: Fetch blockchain transaction data (or generate dummy data if no API key is provided).
- **Graph Construction**: Convert transactions into a directed graph using `networkx`.
- **Feature Extraction**: Calculate node-level features like degree and PageRank for later GNN training.
- **Dataset Export**: Save datasets as nodes/edges CSVs and a serialized graph pickle file.
- **Visualization**: Generate an interactive HTML graph visualization using `pyvis`.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the complete pipeline:
   ```bash
   python main.py
   ```

## Directory Structure

- `data/`: Raw and processed data.
- `graph/`: Graph construction logic.
- `features/`: Node feature extraction.
- `visualization/`: Visualization tools.
- `utils/`: Dataset export scripts.
- `config/`: Settings and configurations.
