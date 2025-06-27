from sentence_transformers import SentenceTransformer
SentenceTransformer('all-mpnet-base-v2')
from huggingface_hub import hf_hub_download
print(hf_hub_download.__defaults__)