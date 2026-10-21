# Ghost Hunter: Tracking an Invisible Enemy

## Project Overview

**Ghost Hunter: Tracking an Invisible Enemy** is a grid-based game developed as a semester project for the **AL-2002 Artificial Intelligence Lab (Fall 2026)** at FAST-NUCES, Karachi Campus.

In this game, a ghost moves around a grid while remaining hidden from the player. A noisy distance sensor provides uncertain information about the ghost's location. A **Hidden Markov Model (HMM)** uses the ghost's possible movements and sensor readings to estimate the probability of the ghost being in each grid cell. These probabilities are displayed as a heatmap, and an AI hunter moves toward the cell with the highest estimated probability. The project will compare the player's score with the AI hunter's score and evaluate the HMM-based approach against a simple uniform-belief baseline.

## Team Members

| Name | Roll Number | Section | Responsibilities |
|---|---|---|---|
| Rameen Samoo (Group Leader) | 24K-3050 | BSE-5B | HMM belief tracking, transition and observation probabilities, and heatmap display. |
| Muhammad Abdullah | 24K-3104 | BSE-5B | Grid game, ghost movement, noisy distance sensor, AI hunter movement, and score comparison. |

## AI Techniques

- **Hidden Markov Model (HMM):** Maintains a probability distribution over possible ghost locations.
- **Belief Updating:** Updates the probabilities using the ghost's possible movements and noisy sensor observations.
- **Maximum-Probability Cell Selection:** Selects the cell with the highest estimated probability as the AI hunter's target.
- **Uniform-Belief Baseline:** Provides a simple alternative for comparing the HMM-based approach.

The core AI algorithms will be implemented using our own code.

## Planned Features

1. A grid-based game with a hidden, moving ghost.
2. A noisy distance sensor that provides uncertain readings.
3. An HMM belief map displayed as a heatmap.
4. An AI hunter that moves toward the most likely ghost location.
5. A player-versus-AI hunter score comparison.

Features outside this agreed scope, such as online multiplayer, persistent leaderboards, and additional sensor types, are not planned.

## Technologies

- **Programming Language:** Python
- **Game Development:** Pygame
- **Numerical Computation:** NumPy

## Environment and Data Source

The project will use a locally generated and simulated grid environment. The ghost's movements and noisy distance readings will be generated within the program. No external dataset, API key, or internet connection will be required to run the simulation.

## Evaluation Plan

The project will evaluate the HMM-based AI hunter against a uniform-belief baseline under equivalent starting conditions.

Planned evaluation measures include:

- Player and AI hunter scores.
- Success in locating the ghost.
- HMM belief distribution across grid cells.
- Comparison of ghost-location success between the HMM and baseline approaches.

Repeated experiments with recorded fixed random seeds will be used to support reproducible comparisons.

Planned visualizations include a player-versus-AI score comparison, an HMM belief heatmap, and a comparison of HMM and baseline ghost-location success.

## Repository Structure

The repository will be organized as follows:

```text
GhostHunter_AI-Lab/
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   ├── AI_Lab_Project_Proposal.pdf
│   ├── AI_Lab_Project_Proposal.md
│   ├── report.pdf
│   └── report.md
├── src/
├── data/
│   ├── raw/
│   └── processed/
└── outputs/
    ├── figures/
    └── results/
```

The report files and implementation-related contents will be added as the project progresses. Since the environment is simulated, external dataset files are not required.

## Installation and Execution

**Project status:** Proposal finalized; implementation has not started.

The installation and execution instructions will be updated after the source code and dependencies have been implemented and tested. The final README will provide the exact commands required to install dependencies, run the game, and reproduce the experiments.

## Known Limitations

- The ghost's exact location is hidden from the player.
- Distance sensor readings may be inaccurate because of simulated noise.
- The HMM estimates the ghost's location rather than directly observing it.
- Grid dimensions, sensor-noise settings, and the number of evaluation runs will be finalized during implementation.

## Project Repository

[Ghost Hunter — GitHub Repository](https://github.com/RameenSamoo/GhostHunter_AI-Lab)

---

**Course:** AL-2002 Artificial Intelligence Lab  
**Semester:** Fall 2026  
**Institution:** FAST-NUCES, Karachi Campus  
