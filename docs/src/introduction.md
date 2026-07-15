# Introduction

This book records the evidence, methods, and results of reverse-engineering
*Captain Bible in the Dome of Darkness*. The supplied copy is a DOS program
whose main executable is `CB.EXE`. The work begins with a reproducible FreeDOS
virtual machine before moving to static and dynamic analysis.

Statements in this book should distinguish direct observations from
inferences. Commands and their important results are preserved in the
[progress log](progress-log.md).

## Current scope

The playable QEMU environment is complete. Static analysis has identified the
packer and run time, reconstructed the executable, mapped startup and major
support routines, and recovered the command-line, export, input, and save
paths. Dynamic analysis now uses a QEMU TCG plugin to trace game-originated
DOS and sound-driver calls without modifying `CB.EXE`, correlating file
activity and runtime addresses with the reconstructed program. The resource
container, graphics,
scene bytecode, audio, text, saves, maps, combat, conversation, and final
progression all have reproducible inspectors or archive-backed regressions.

The remaining work is intentionally narrower: interactive coverage of more
gameplay screens, focused input/save traces, and semantic names for fields that
the current evidence does not distinguish.
Those boundaries are recorded in PLAN and in the relevant system chapters.
