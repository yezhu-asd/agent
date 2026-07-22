import sys
sys.path.insert(0, r'E:\wu\xidian\job\java\agent\CampusCare')
from config.model_provider import create_embedding_model
print('creating...', flush=True)
m = create_embedding_model()
print('encoding...', flush=True)
r = m.embed_query('test')
print(f'ok, dim={len(r)}', flush=True)
