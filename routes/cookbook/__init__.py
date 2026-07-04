"""routes/cookbook/ — co-located Cookbook route domain package.

Submodules: routes (cookbook API routes), helpers, output. The old flat
paths routes/cookbook_routes.py, routes/cookbook_helpers.py,
routes/cookbook_output.py are sys.modules alias shims over these submodules.
Intentionally no eager re-exports (consumers use the old flat paths via shims).
"""
