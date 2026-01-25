# The Brimley Philosophy

## The Problem

Giving an AI Agent access to a database is usually a binary choice between **Safety** and **Flexibility**.

1. **The "Wild West" Approach:** You give the LLM a connection string and say, "Here is the schema, write your own SQL."
* *Pros:* Infinite flexibility.
* *Cons:* Hallucinations, dangerous queries (DROP TABLE), syntax errors, and prompt injection risks.


2. **The "Hardcoded" Approach:** You write a specific Python function for every single interaction.
* *Pros:* Safe and deterministic.
* *Cons:* Extremely high effort. You become the bottleneck.



## The Brimley Solution

Brimley strikes a pragmatic middle ground. It is a **"Defined SQL"** engine.

### 1. SQL is the Language of Data

We don't try to abstract databases away into ORMs or Python objects. SQL is the most expressive way to query data. Brimley treats **Parameterized SQL Templates** as first-class citizens.

* *The Human* defines the logic (SQL).
* *The AI* defines the inputs (Arguments).

### 2. Configuration > Code

Brimley tools are defined in **JSON/YAML**, not Python.

* This makes tools portable.
* This allows non-engineers to define tools.
* This allows tools to be hot-swapped without restarting the application.

### 3. Strict Validation (The Guardrails)

We do not trust the AI. Every input is validated against a rigorous schema (Pydantic) before it ever touches the database. If an Agent tries to pass a string into an integer field, Brimley stops it immediately.

### 4. Local First

Cloud databases are great, but local development is where speed happens. Brimley is optimized for **SQLite**. It allows you to build, test, and tear down Agent capabilities on your laptop in seconds, not minutes.
