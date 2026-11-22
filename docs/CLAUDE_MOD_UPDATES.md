# Raw server mod updates — launcher 0.1.36

Keep the existing UDP update negotiation, version fields and NSO chunk transport.
Serve the ordinary, complete mod NSO. Compatible builds no longer need a launcher
build-ID registration, a server-side profile database, an ELF upload or an
appended compatibility profile.

The launcher derives compatibility information from the downloaded binary:

- It identifies the supported legacy or native runtime ABI from actual imports
  and relocations.
- It locates camera memory-query callers by executable-code structure rather
  than fixed offsets or the NSO build ID.
- It recovers bounded switch-table targets using the shipped translator.
- It binds generated code and a local compatibility record to the exact NSO
  identity and SHA-256, then verifies isolated startup before activation.

The existing update version policy remains: newer validated builds apply, and
validated server downloads may replace a same-version build. Downgrades remain
blocked. The bundled initial mod remains normal 1.5.8 build 8, build ID
0124d3f6a48e67fefaa3ab4145bf24c26c42c3ff; it is not the private capture build.

Optional compatibility trailers and older native profile records remain readable.
Their identities, instructions and ABI must agree with the actual binary; they
cannot override discovery with another build's offsets. The optional
tools/lumiose/pack_mod_update.py utility remains available for those workflows.

This removes build-ID admission as a dependency. Changes to the supported runtime
ABI or instructions still require actual implementation support, as with any
recompiler. Preparation reports such errors and retains the previous active
version; it does not activate partially generated code.

The launcher also reads both captured output and its owned runtime log during
preparation, preventing successful startup from being reported as an empty-log
timeout. Logs from earlier attempts cannot satisfy the current test.

No relay command, Pokémon-slot selection, party assignment, server clock or
deployed server configuration is changed by this launcher release.
