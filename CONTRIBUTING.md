# Contributing

Write all commit messages, code comments, and docstrings in English. Documentation may have separate language editions; keep `README.md` in English and `README.zh-CN.md` in Chinese, with reciprocal links near the top.

Use concise commit messages that describe the change. Keep recorded experiment outputs distinct from new runs, and do not label a population successful unless independent validation confirms its size and every marginal count.

For Python changes, run `python -m unittest discover -s tests -v`. For documentation changes, check local links and confirm that commands and algorithm descriptions match the implementation.
