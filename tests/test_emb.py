from rag_index import search_query
res = search_query("Quina és la millor actuació dels Al·lots de Llevant?", k=5)
for meta, score in res:
    print(score, meta['meta'])
    print(meta['text'])
    print("-----")