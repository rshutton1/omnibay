# OmniBay

A MechWarrior Online mech builder. Browse every variant, design loadouts
against the real game numbers, and import or export MWO loadout codes.

**https://rshutton1.github.io/omnibay/**

## Stack

- Python build-calculation engine, running in the browser via [Pyodide](https://pyodide.org)
- Vue 3 + Vite + TypeScript client
- Static site — no backend

## Development

```bash
cd frontend && npm install && npm run dev
```

Tests:

```bash
cd engine && python -m pytest
```

## Data

`data/` holds JSON extracted from a local MechWarrior Online install: 1,278
variants, 751 equipment items, 1,301 stock loadouts and 1,833 omnipods.
