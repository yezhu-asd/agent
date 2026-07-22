import sys
print("test 1: import numpy", flush=True)
import numpy
print(f"numpy version: {numpy.__version__}", flush=True)

print("test 2: import torch", flush=True)
import torch
print(f"torch version: {torch.__version__}", flush=True)
print(f"torch cuda: {torch.cuda.is_available()}", flush=True)

print("test 3: import FlagEmbedding", flush=True)
from FlagEmbedding import BGEM3FlagModel
print("FlagEmbedding imported OK", flush=True)
