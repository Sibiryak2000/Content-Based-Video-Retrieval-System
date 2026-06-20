# Content-Based Video Retrieval System

An interactive content-based video retrieval (CBVR) system for finding short
segments of interest within a moderately large video collection (~200 videos,
~25 hours). It supports **Known-Item Search (KIS)** and **Visual Question
Answering (VQA)** queries in the context of the
[Video Browser Showdown (VBS)](https://www.videobrowsershowdown.org), and
submits results over REST to the **Distributed Retrieval Evaluation Server (DRES)**
for live scoring.

> Course project for *Image and Video Analysis with Deep Learning (IVADL)*,
> SS 2026 — Assignment 3.

## Overview

The system is split into a clear **offline / online** boundary:

- **Offline analysis pipeline (Python):** ingests the videos, derives shot
  segments from pre-computed TransNet2 boundaries, extracts keyframes, computes
  semantic embeddings with pretrained vision-language models, transcodes
  lightweight playback proxies, and builds a searchable vector index plus a
  meta-data database.
- **Online retrieval app:** a GUI front-end that answers text and similarity
  queries from the index in milliseconds, lets the user inspect and play
  shots/videos, and submits the selected segment to DRES with correct
  frame-to-millisecond timing.

Inference uses **pretrained** models on pre-extracted keyframes, so no training
is required and the heavy computation happens once, offline (CPU-friendly).

## Features

- Text-query search over video content (natural-language → shots/keyframes)
- Similarity search ("more like this") and content filtering / browsing
- Integrated video player for inspecting shots and full videos
- One-click, guarded submission to DRES (with confirmation safeguards)
- Reproducible offline preprocessing and indexing pipeline

## Tech Stack

- **Language:** Python
- **Models:** CLIP / BLIP / SigLIP, Vision Transformers, CNNs / R-CNNs (inference only)
- **Indexing:** FAISS / vector index + meta-data database
- **Media:** ffmpeg (transcoding, keyframe extraction)
- **GUI:** PySide6 / PyQt (Qt for Python) with Qt Multimedia video player
- **Evaluation:** DRES client generated from the OpenAPI specification

## Dataset

A subset of the **V3C-1** dataset (~200 videos, multiple resolutions) with
VIMEO upload meta-data, plus pre-computed **TransNet2** shot segmentation
(`scenes_v3c1_200.zip`) providing start/end frame boundaries.

## Architecture

```
Raw videos ──► Shot segmentation (TransNet2) ──► Keyframe extraction
                                                      │
        ┌─────────────────────────────────────────────┤
        ▼                                              ▼
  Embeddings (CLIP/SigLIP)                    ffmpeg proxies + thumbnails
        │                                              │
        ▼                                              ▼
  Vector index (FAISS) + meta-data DB  ◄────────────────┘
        │
        ▼
  Search service ──► GUI (search · inspect · play) ──► DRES submit (REST)
```

## Getting Started

> Note: dataset and DRES credentials are not included in this repository.

```bash
# 1. Set up the environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Run the offline pipeline (shots → keyframes → proxies → embeddings → index)
python -m pipeline.build_index --config config.yaml

# 3. Launch the GUI
python -m app.main
```

## Repository Structure

```
pipeline/   Offline preprocessing: shots, keyframes, transcoding, embeddings, indexing
index/      Vector index + meta-data store
search/     Online retrieval service / API
dres/       DRES OpenAPI client and submission logic
app/        PySide6 GUI (search, browsing, video player, submit)
docs/       Report and user documentation
```

## Acknowledgements

- V3C-1 dataset and TransNet2 shot segmentation
- [DRES](https://github.com/dres-dev/DRES) — Distributed Retrieval Evaluation Server
- The Video Browser Showdown community
