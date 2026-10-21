# acme-bisect

A Faultline fixture for the minimisation recovery demonstration (the Incremental Witness twist).

The reference world pins nine packages. The consumer `bisect-svc` pins the same set with **eight** of them at other versions. Seven of
those changes are harmless; Werkzeug 2.2.3 -> 3.0.6 under Flask 2.2.2 breaks `import acme_bisect.web`. Finding that one package among the
eight is what the delta-debugging search does, and the demonstration interrupts it part of the way and resumes it.

Expected result: `fixtures/twist/bisect.yaml`.
