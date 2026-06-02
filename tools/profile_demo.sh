#!/usr/bin/env bash
set -e

python -m src.cli examples/sprint7_demo.src -S -o profile_demo.asm
nasm -f elf64 profile_demo.asm -o profile_demo.o
gcc -no-pie profile_demo.o -o profile_demo_program

echo "time:"
/usr/bin/time -v ./profile_demo_program

if command -v perf >/dev/null 2>&1; then
  echo "perf stat:"
  perf stat ./profile_demo_program || true

  echo "perf record:"
  perf record -o perf.data ./profile_demo_program || true
  echo "Run: perf report -i perf.data"
else
  echo "perf not installed"
fi