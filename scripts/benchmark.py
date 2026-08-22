from time import perf_counter

from orelhao.main import run_once

start = perf_counter()
run_once()
print(f"Tempo total simulado: {perf_counter() - start:.3f}s")
