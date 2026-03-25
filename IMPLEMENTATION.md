# 📖 Recovery Version Translation LLM — Technical Plan

## Overview

This project builds a **domain-specific translation system** for:

* The *Recovery Version Bible*
* Living Stream Ministry (LSM) ministry materials

The goal is:

> **Faithful, consistent, and stylistically correct translation across multiple languages**

---

## 🧠 Core Insight

There are **two fundamentally different translation tasks**:

1. **Bible (Recovery Version)** → literal, structure-preserving
2. **Ministry materials** → meaning-preserving, natural language

These must be handled **separately**.

---

## 🏗️ System Architecture

### Base Model (shared)

Use a single base LLM:

* Mistral 7B (recommended)

---

### Adapter-Based Design (LoRA)

Train separate adapters:

#### 1. 📖 Bible Adapter

* trained ONLY on verse-aligned Bible data
* objective:

  * literal translation
  * strict terminology
  * preserve structure

---

#### 2. 📝 Ministry Adapter

* trained ONLY on ministry materials
* objective:

  * natural readability
  * preserve meaning + tone
  * allow light rephrasing

---

### Inference Flow

```python
mode = "bible"  # or "ministry"

if mode == "bible":
    load_adapter("bible_adapter")
else:
    load_adapter("ministry_adapter")
```

---

## 📊 Data Strategy

---

# 📖 Bible Dataset Pipeline

## Goal

High-quality **verse-aligned parallel dataset**

---

## Data Format (raw)

```json
{
  "id": "john_1_1",
  "source_lang": "en",
  "target_lang": "es",
  "source": "In the beginning was the Word...",
  "target": "En el principio era la Palabra..."
}
```

---

## Alignment Strategy

Use:

* book + chapter + verse

Example:

```
John 1:1 ↔ John 1:1
```

---

## Data Sources

* bilingual Bible editions
* PDFs
* websites

---

## Extraction Tools

* `pymupdf` (best for PDFs)
* `pdfplumber`
* `BeautifulSoup` (for websites)

---

## Cleaning Steps

* normalize punctuation
* remove extra whitespace
* ensure verse alignment is correct
* remove incomplete pairs

---

## Training Format (JSONL)

```json
{"instruction": "Translate the following verse into Spanish in a strictly literal and faithful manner, preserving structure and terminology.", "input": "In the beginning was the Word...", "output": "En el principio era la Palabra..."}
```

---

# 📝 Ministry Dataset Pipeline

## Goal

Paragraph-aligned dataset

---

## Data Format (raw)

```json
{
  "id": "msg_001",
  "source": "God's economy is...",
  "target": "La economía de Dios es..."
}
```

---

## Alignment Strategy

### Option 1 (simple)

* paragraph order matching

### Option 2 (better)

* embedding similarity matching

---

## Cleaning

* remove broken paragraphs
* ensure semantic alignment
* filter mismatched lengths

---

## Training Format

```json
{"instruction": "Translate the following text into Spanish in a natural and readable way, preserving the spiritual meaning and tone.", "input": "God's economy is...", "output": "La economía de Dios es..."}
```

---

# 🌍 Low-Resource Language Strategy

For languages without parallel data:

---

## 1. Zero-Shot Translation

Use trained model:

```text
Translate into Italian in the style of the Recovery Version Bible.
```

---

## 2. Synthetic Data Generation

### Step 1

Generate:

```
English → Italian
```

### Step 2

Clean:

* human review (partial)
* filtering

### Step 3

Fine-tune new adapter

---

## 3. Pivot Translation

Example:

```
Greek → English → Italian
```

---

## 4. Backtranslation (optional)

1. English → Italian
2. Italian → English
3. keep high-quality pairs

---

# 🏋️ Model Training

## Base Model

* Mistral 7B Instruct

---

## Fine-Tuning Method

Use:

* LoRA (Low-Rank Adaptation)

---

## Platform

Use:

* Tinker API (training)
* Hugging Face (base weights)

---

## Training Data Format

```json
{"instruction": "...", "input": "...", "output": "..."}
```

---

## Output of Training

From Tinker:

* LoRA adapter weights
* config

---

## Local Inference Setup

```python
from transformers import AutoModelForCausalLM
from peft import PeftModel

base_model = AutoModelForCausalLM.from_pretrained("mistralai/Mistral-7B-Instruct")
model = PeftModel.from_pretrained(base_model, "path_to_adapter")
```

---

# 🔑 Terminology System (Critical)

Maintain dictionary:

```json
{
  "economy of God": "economía de Dios",
  "dispensing": "impartición",
  "spirit": "espíritu",
  "soul": "alma"
}
```

---

## Enforcement

* post-processing replacement
* or prompt-level constraints

---

# ⚠️ Failure Modes

## 1. Inconsistency

→ fix with terminology system

## 2. Meaning Drift

→ fix with better prompts + review

## 3. Style Mixing

→ fix by separating adapters

---

# 🚀 Development Plan

## Phase 1

* build Bible dataset (1 book, e.g. John)
* train Bible adapter

---

## Phase 2

* build ministry dataset
* train ministry adapter

---

## Phase 3

* evaluate outputs
* fix terminology

---

## Phase 4

* expand to new languages
* use synthetic data

---

# 🧭 Final Architecture

* 1 base model
* multiple adapters:

  * Bible
  * ministry
  * (future) refinement

---

# 👍 Key Takeaways

* Separate Bible vs ministry tasks
* Use adapters for modularity
* Data quality is the most important factor
* Combine:

  * fine-tuning
  * terminology control
  * synthetic data expansion

---