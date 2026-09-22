# AI prompting and engineering workflow

The project began with a manual trading process, not an AI-generated strategy. The technical challenge was to formalise that process into explicit software contracts and then implement a deterministic automation system.

AI was used as an engineering collaborator for:

1. translating natural-language requirements into module responsibilities;
2. drafting and refining contract boundaries before implementation;
3. implementation support, code review and debugging hypotheses;
4. identifying incomplete wiring, state-ownership gaps and validation cases;
5. comparing deterministic logs and verification outputs after changes.

Prompts and specifications were refined when an output was ambiguous, incomplete or inconsistent with the intended contract. AI suggestions were not automatically trusted: deterministic behaviour, code inspection, audit output and human review remained the final control points.

There is no runtime LLM dependency in the engine.

## Historical development captures

The project also retained private contemporaneous progress material. The two public-safe captures below illustrate the workflow without reproducing private strategy rules or operational account details.

![AI-assisted integration research](../assets/historical/historical-ai-research.jpg)

*AI-assisted requirements research for using equivalent external-data inputs in forward runs and backtests.*

![AI-assisted execution-design discussion](../evidence/historical-ai-execution-design.jpg)

*AI-assisted reasoning about a multi-terminal execution abstraction. Operational identifiers, paths and private implementation details are removed.*
