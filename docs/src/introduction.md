# Introduction

This book records the evidence, methods, and results of reverse-engineering
*Captain Bible in the Dome of Darkness*. The supplied copy is a DOS program
whose main executable is `CB.EXE`. The work begins with a reproducible FreeDOS
virtual machine before moving to static and dynamic analysis.

Statements in this book should distinguish direct observations from
inferences. Commands and their important results are preserved in the
[progress log](progress-log.md).

## Current scope

The playable QEMU environment is complete. The current milestone is static
analysis of `CB.EXE`, assisted by QEMU memory snapshots where runtime evidence
is needed to recover the original post-decompression image. The initial pass
has identified the packer and run time, reconstructed the executable, mapped
startup and major support routines, and recovered the command-line, export,
input, and save paths.
