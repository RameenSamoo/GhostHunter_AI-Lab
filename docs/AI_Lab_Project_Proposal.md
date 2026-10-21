# AL-2002 Artificial Intelligence Lab — Project Proposal — Fall 2026

|  | FAST — NATIONAL UNIVERSITY OF COMPUTER AND EMERGING SCIENCES / FAST School of Computing · Karachi Campus · Department of Software Engineering / AL-2002 Artificial Intelligence (Laboratory) · Fall 2026 |
| --- | --- |

# PROJECT PROPOSAL

_Semester Lab Project · Weightage 1 mark_

## Group Information

|  | Name | Roll Number | Section | Role in the project |
| --- | --- | --- | --- | --- |
| Leader | Rameen Samoo | 24K-3050 | BSE-5B | Leader |
| Member 2 | Muhammad Abdullah | 24K-3104 | BSE-5B | Member |

| Project Title | Ghost Hunter: Tracking an Invisible Enemy |
| --- | --- |
| Project Idea | Idea No.  10th  from the Project Ideas list ☑	Own idea (needs approval) ☐ |
| Category | Part A — Game ☑	Part B — Applied / Data ☐ |
| GitHub Repository URL | https://github.com/RameenSamoo/GhostHunter_AI-Lab |
| Date of Submission | 22nd October |

### Project Title and Summary

Ghost Hunter: Tracking an Invisible Enemy is a grid-based game in which a ghost moves while remaining hidden from the player. The player cannot see the ghost’s exact location and receives only noisy distance readings from a sensor. A Hidden Markov Model (HMM) uses these readings and the ghost’s movement model to estimate the probability that the ghost is in each grid cell. The game displays these probabilities as a heatmap, allowing the player to see where the ghost is most likely to be. An AI hunter also moves toward the cell with the highest estimated probability. The project compares the player’s score with the AI hunter’s score to demonstrate how probabilistic reasoning can help locate a hidden target.

### Problem Statement and Motivation

Finding a moving object when its exact location cannot be observed is difficult because the available information is uncertain and may be inaccurate. In Ghost Hunter, the ghost moves around a grid, but its position is hidden. The sensor reports noisy distances rather than the exact cell, so a single reading may point toward several possible locations. The ghost may also move between readings, meaning that an earlier estimate can quickly become outdated. A player who relies on one reading or guesses may repeatedly search the wrong cells. Checking every possible location after every movement does not directly resolve the uncertainty because the ghost keeps moving and the sensor is noisy. The game therefore needs a method that combines previous beliefs, possible ghost movements, and new sensor readings. A Hidden Markov Model maintains a probability for each possible location and updates those probabilities as new evidence arrives. This project demonstrates how probabilistic reasoning can support decisions when an agent cannot directly observe the environment.

### Problem Formulation

### PEAS Description

| Component | Description for your project |
| --- | --- |
| Performance measure | Player and AI hunter scores, and whether the hunter identifies the ghost’s location. |
| Environment | A grid containing a hidden, moving ghost, the player, and the AI hunter. |
| Actuators | Player movement controls and AI hunter movement toward the most likely cell. |
| Sensors | A noisy distance sensor that provides distance readings without revealing the ghost’s exact location. |

### Environment and Agent Type

| Property | Classification — tick one |
| --- | --- |
| Observability | Fully observable ☐	Partially observable ☑ |
| Determinism | Deterministic ☐	Stochastic ☑ |
| Change over time | Static ☐	Dynamic ☑ |
| State and actions | Discrete ☑	Continuous ☐ |
| Agents | Single-agent ☐	Multi-agent / adversarial ☑ |
| Agent type | Simple reflex ☐  Model-based ☑  Goal-based ☐  Utility-based ☐  Learning ☐ |

### Problem Representation

| Element | Your representation |
| --- | --- |
| State representation | Ghost’s hidden grid cell, player’s cell, AI hunter’s cell, and the HMM belief probability for each grid cell. |
| Actions / moves | The ghost moves between grid cells; the player moves using controls; the AI hunter moves toward the cell with the highest belief probability. |
| Initial state | A grid is initialized, the ghost is placed in a hidden cell, and the initial belief is distributed across possible cells. |
| Goal or terminal test | A hunter locates the ghost according to the game’s capture rule; the game records the player and AI hunter scores for comparison. |
| Cost, utility, fitness or evaluation | Score earned by the player and AI hunter, with the score comparison used to evaluate their performance. |

### Proposed AI Approach

| # | Technique | Role in the project | Own code or library |
| --- | --- | --- | --- |
| 1 | Hidden Markov Model (HMM) belief tracking | Represents the probability of the ghost occupying each grid cell. | Own code |
| 2 | HMM belief update using transition and observation probabilities | Updates the belief map after possible ghost movement and each noisy distance reading. | Own code |
| 3 | Maximum-probability cell selection | Selects the cell with the highest current belief for the AI hunter to move toward. | Own code |
| B | Baseline: uniform belief / no belief updating | Provides a simple comparison against the HMM-based location estimate. | Own code |

### Explanation of the AI Approach:

The HMM is suitable because the ghost’s location is hidden and the sensor readings are noisy. The model maintains a belief distribution over the grid: each cell has a probability representing how likely the ghost is to be there. The transition model represents the possible movement of the ghost between cells, while the observation model represents how likely a reported distance is for each possible ghost location. After each movement and sensor reading, the belief is updated using these probabilities and normalized so that all cell probabilities sum to one. The heatmap visualizes the updated belief, with higher-probability cells appearing more likely to contain the ghost. The AI hunter selects the cell with the highest belief probability as its target. Its performance will be compared with a simple uniform-belief baseline using the same game conditions.

### Planned Class Design

GameGrid

Attributes: grid dimensions, player position, AI hunter position.

Methods: initialize the grid and provide valid movement options.

Relationship: used by the game and hunter components to represent the environment.

Ghost

Attributes: current hidden position and possible movement options.

Methods: move to a possible grid cell.

Relationship: moves within the grid and supplies the hidden state used by the simulation.

DistanceSensor

Attributes: sensor noise settings.

Methods: produce a noisy distance reading from the ghost’s position.

Relationship: supplies observations to the HMM.

HMMTracker

Attributes: transition probabilities, observation probabilities, and belief grid.

Methods: initialize beliefs, update beliefs from movement and sensor readings, and return the most likely cell.

Relationship: receives readings from DistanceSensor and supplies the AI hunter’s target and heatmap values.

HunterGame

Attributes: game state and player/AI scores.

Methods: run game turns, handle player movement, update the AI hunter, and record scores.

Relationship: coordinates GameGrid, Ghost, DistanceSensor, and HMMTracker.

### Scope

| # | Feature | Why it is essential |
| --- | --- | --- |
| 1 | Grid game with a hidden moving ghost | Provides the environment and hidden target for the project. |
| 2 | Noisy distance sensor | Gives the hunter uncertain observations instead of the ghost’s exact location. |
| 3 | HMM belief update shown as a heatmap | Demonstrates how the probability of each possible ghost location changes over time. |
| 4 | AI hunter that moves toward the most likely cell | Uses the HMM’s current belief to choose where to move. |
| 5 | Player-versus-AI hunter score comparison | Allows the performance of the human player and AI hunter to be compared. |

Out of Scope

The project will not include features beyond the five items listed in the agreed scope. It will not add extra game modes, online multiplayer, persistent leaderboards, additional sensor types, or unrelated gameplay systems.

### Data or Environment Source

| Source name and URL | Generated/simulated grid environment; no external URL is required |
| --- | --- |
| Type | Public dataset ☐	Web API ☐	Self-collected ☐	Generated / simulated ☑ |
| Access requirements | No key needed ☑	Free key required ☐	(Paid sources are not permitted) |
| Approximate size | A configurable grid with a hidden ghost, player and AI hunter; exact grid dimensions will be selected during implementation. |
| Licence / terms of use | No external dataset is used. The project’s own simulated environment and generated readings are used. |
| Offline fallback | The grid, ghost movements, and noisy distance readings are generated locally, so the game runs without a network connection. |

### Evaluation Plan

| What will be compared | HMM-based AI hunter and the simple uniform-belief baseline, alongside the player-versus-AI score comparison. |
| --- | --- |
| Metric(s) | Scores and success in locating the ghost. |
| Baseline | Uniform belief without HMM belief updates. |
| Test instances / test set | Simulated game runs using the same grid setup and equivalent starting conditions for each compared approach. |
| Number of runs and seed | Use repeated runs with recorded fixed seeds so that comparisons can be reproduced; the final number of runs will be set during implementation. |
| Planned charts (at least three) | Player and AI hunter scores; HMM belief over grid cells as a heatmap; comparison of HMM and baseline ghost-location success. |

### Division of Work

| Member | Modules / components owned | Approximate share |
| --- | --- | --- |
| Rameen Samoo | HMM belief tracking, transition/observation probabilities, and heatmap display | 50% |
| Muhammad Abdullah | Grid game, ghost movement, noisy distance sensor, AI hunter movement, and score comparison | 50% |

### Milestones and Timeline

| # | Milestone — what will be demonstrably working | Target date | Owner |
| --- | --- | --- | --- |
| 1 | Grid game runs with a hidden moving ghost and player movement. | Week 1 | Member 2 |
| 2 | Noisy distance sensor produces readings, and HMM belief updates correctly. | Week 2 | Group Leader |
| 3 | HMM probability heatmap and AI hunter movement toward the most likely cell work together. | Week 3 | Both |
| 4 | Player and AI hunter scores are recorded and compared against the baseline. | Week 4 | Both |
| 5 | Evaluation runs, charts, final integration, documentation, and repository cleanup are complete. | Week 5 | Both |

### Expected Outcome and Risks

The completed project will present a playable grid game in which the ghost moves without being directly visible. The player will receive noisy distance readings, while an HMM updates the probability of the ghost’s location and displays those probabilities as a heatmap. The AI hunter will use the most likely cell from this belief map to guide its movement. The game will record and compare the player’s and AI hunter’s scores, and the HMM approach will be evaluated against a uniform-belief baseline. Two main risks are incorrect probability updates and a heatmap that is difficult to interpret. The team will test belief normalization and individual updates, and adjust the heatmap’s visual scaling while keeping the agreed features unchanged.

| For office use — Lab Instructor |  |
| --- | --- |
| Proposal status | Approved ☐	Approved with changes ☐	Revision required ☐ |
| Comments |  |
| Signature and date |  |

---
_End of Project Proposal_
