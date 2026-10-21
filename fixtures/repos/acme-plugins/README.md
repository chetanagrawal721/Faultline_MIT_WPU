# acme-plugins

Plugin registry (Faultline fixture, Information severity). It looks plugins up on pydantic by name at run time, so no static reading can say which
pydantic API it touches, and its tests need a database driver that neither world installs, so execution cannot settle it.
