# Contributing to SportsBench

Thanks for helping build the open benchmark for LLM sports prediction.

## Setup
```bash
git clone <your-fork>
cd sportsbench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python scripts/gen_demo.py   # regenerate the bundled sample if you change the generator
```

## Good first contributions
- **A new provider** (~30 lines): add a class in `src/sportsbench/providers/`, register it in
  `providers/__init__.py`. Most gateways are OpenAI‑compatible — just a preset `base_url`.
- **A new data source**: implement `upcoming()` and `results()` from
  `src/sportsbench/sources/base.py`.
- **A new sport / market**: 2‑way markets are already modelled in `brief.py`.

## Guidelines
- Keep the dependency footprint tiny (httpx, typer, rich, pyyaml, dotenv). No vendor SDKs.
- Everything that can be pure and tested, should be (see `grading/`, `odds.py`).
- Be honest in metrics and copy — losses stay in. That's the whole point.

## License
By contributing you agree your work is released under the project's [MIT License](LICENSE).
