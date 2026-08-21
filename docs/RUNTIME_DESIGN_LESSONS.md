# Runtime Design Lessons

The runtime is intentionally conservative.

1. Use the MCP 2.x server API.
2. Pin the MCP runtime version.
3. Use a simple `src/` layout.
4. Derive data locations from `__file__`.
5. Keep DuckDB access inside analytical calls.
6. Do not rebuild persistent data during MCP startup.
7. Launch the server file directly during development.
8. Validate MCP locally before connecting an LLM client.
9. Add analytical sophistication only after the transport is proven.

> **The runtime should be boring; the research should be interesting.**
