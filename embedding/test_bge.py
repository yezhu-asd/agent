import time, sys
t0 = time.time()
print(f"[{time.time()-t0:.1f}s] importing FlagEmbedding...")
try:
    from FlagEmbedding import BGEM3FlagModel
    print(f"[{time.time()-t0:.1f}s] import OK")
except Exception as e:
    print(f"[{time.time()-t0:.1f}s] import FAILED: {e}")
    sys.exit(1)

print(f"[{time.time()-t0:.1f}s] loading model...")
try:
    model = BGEM3FlagModel(r"E:\wu\xidian\job\java\agent\models\bge-m3", use_fp16=False, device="cpu")
    print(f"[{time.time()-t0:.1f}s] model loaded")
except Exception as e:
    print(f"[{time.time()-t0:.1f}s] load FAILED: {e}")
    sys.exit(1)

print(f"[{time.time()-t0:.1f}s] encoding...")
result = model.encode("嗓子疼怎么办", max_length=512)
print(f"[{time.time()-t0:.1f}s] done, dim={len(result['dense_vecs'])}")
