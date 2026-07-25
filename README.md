# FinSight AI 💡

**AI-powered financial intelligence on Monad Testnet**

> Built using IBM Bob · Made by Kavya Raval

FinSight AI transforms raw expense data into meaningful financial insights, then permanently records monthly Financial Memory Snapshots on the Monad Testnet blockchain.

---

## Features

| Feature | Description |
|---|---|
| 📤 **Upload** | Drag-and-drop CSV expense upload with validation |
| 📊 **Dashboard** | Interactive Plotly charts — categories, merchants, trends |
| 🤖 **AI Insights** | Spending personality, insights, recommendations & goal planner |
| 🔗 **Financial Memory** | AI snapshot generation + optional Monad Testnet storage |

---

## Quick Start

### 1. Clone / enter the project

```bash
cd finsight-ai
```

### 2. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI key:

```
OPENAI_API_KEY=sk-...
```

> The app works without an API key — a rule-based fallback generates insights automatically.

### 5. Run the app

```bash
streamlit run app/main.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## CSV Format

```
Date,Merchant,Amount,Description
2026-07-01,Starbucks,6.50,Coffee
2026-07-02,Uber,18.00,Ride
2026-07-05,Walmart,54.00,Groceries
```

A sample file is included at `data/sample_expenses.csv`.

---

## Blockchain Integration (Monad Testnet)

Blockchain features are **optional** and require:

1. **Install web3:** `pip install web3`
2. **Deploy the contract:**
   - Open `blockchain/FinSightAI.sol` in [Remix IDE](https://remix.ethereum.org)
   - Connect MetaMask to Monad Testnet (Chain ID: 10143, RPC: `https://testnet-rpc.monad.xyz`)
   - Compile with Solidity `^0.8.19` and deploy
   - Copy the deployed contract address
3. **Configure `.env`:**
   ```
   MONAD_RPC_URL=https://testnet-rpc.monad.xyz
   CONTRACT_ADDRESS=0x...
   PRIVATE_KEY=0x...
   WALLET_ADDRESS=0x...
   ```

### Monad Testnet Details

| Field | Value |
|---|---|
| Network Name | Monad Testnet |
| Chain ID | 10143 |
| RPC URL | `https://testnet-rpc.monad.xyz` |
| Explorer | `https://testnet.monadexplorer.com` |
| Faucet | `https://faucet.monad.xyz` |

---

## Project Structure

```
├── app/
│   └── main.py               # Streamlit app (4 pages)
├── services/
│   ├── expense_service.py    # CSV parsing, categorisation, analytics
│   └── ai_service.py         # LLM calls + rule-based fallbacks
├── blockchain/
│   ├── blockchain_service.py # Web3 / Monad integration (optional)
│   └── FinSightAI.sol        # Solidity smart contract
├── finsight-ai/
│   ├── app.py                # IBM watsonx.ai invoice tracker
│   ├── doc_processing.py
│   └── model_gateway.py
├── data/
│   └── sample_expenses.csv   # Demo data
├── utils/
├── assets/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Privacy

Only a **SHA-256 hash** of the snapshot text is stored on-chain — never any raw financial data.

---

## Tech Stack

- **Frontend:** Streamlit
- **Data:** pandas, Plotly
- **AI:** OpenAI API (gpt-4o-mini) with rule-based fallback
- **Blockchain:** Solidity + Web3.py + Monad Testnet

---

*Built using IBM Bob · Made by Kavya Raval*
