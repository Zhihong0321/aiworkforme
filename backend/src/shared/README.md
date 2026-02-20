# `shared` Layer

Purpose: tiny cross-cutting primitives with minimal dependencies.

Allowed imports: only Python stdlib and `src.shared`.

Rule: if shared helpers grow domain-specific behavior, move them into a focused module in `domain` or `app`.
