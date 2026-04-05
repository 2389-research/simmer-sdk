---
Created by: Carlos Rivera
Created time: 2025-07-16T11:47:00
Type: Research
Attendees:
  - Carlos Rivera
  - Diana Park
---

### Applying Organization Theory to Specialized Agents

- Key insight: agent teams mirror human organizational structures
- Conway's Law applies to AI agent architectures
- Reviewed paper: "Scaling Laws for Agent Coordination" (Stanford, 2025)

### Framework Comparison

- LangChain: good for prototyping, poor for production
- CrewAI: interesting multi-agent patterns but immature
- Custom framework in Rust: highest performance, most maintenance
- Claude API with tool use: best balance of capability and simplicity

### Deployment Patterns

- Manager bot delegates to specialist agents
- Each agent has narrow tool access (principle of least privilege)
- Shared memory via Redis for cross-agent state
- Cost tracking per agent: averaging $0.03 per task completion
- Monthly infrastructure: $2,500 for 10-agent deployment on AWS
