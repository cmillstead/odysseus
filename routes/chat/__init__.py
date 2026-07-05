"""routes/chat/ — Chat/Agent route domain package.

Submodules: routes (chat API routes) and helpers. The old flat paths
routes/chat_routes.py and routes/chat_helpers.py are sys.modules alias shims
over these submodules. Intentionally no eager re-exports (consumers use the old
flat paths via shims).
"""
