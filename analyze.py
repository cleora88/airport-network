from pathlib import Path
import csv
import json
from collections import Counter, defaultdict
import random
import math
import os
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
SEED = 42

def read_data(name):
    with (ROOT / "data" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))

def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def load_data():
    airports = {int(r[0]): dict(id=int(r[0]), name=r[1], city=r[2], country=r[3],
                 code=r[4] if r[4] != r"\N" else r[5], lat=float(r[6]), lon=float(r[7]))
                for r in read_data("airports.dat") if r[12] == "airport"}
    raw = read_data("routes.dat")
    routes = defaultdict(set)
    audit = Counter(raw_records=len(raw), metadata_airports=len(airports),
                    exact_duplicate_records=len(raw)-len(set(map(tuple, raw))))
    for r in raw:
        if r[7] != "0":
            audit["nonstop_filter_excluded"] += 1
        elif not r[3].isdigit() or not r[5].isdigit() or int(r[3]) not in airports or int(r[5]) not in airports:
            audit["unmatched_endpoint_records"] += 1
        elif r[3] == r[5]:
            audit["self_loop_records"] += 1
        else:
            key = (int(r[3]), int(r[5]))
            if r[1].isdigit():
                routes[key].add(r[1])
            else:
                routes[key]
                audit["records_without_airline_id"] += 1
            audit["valid_nonstop_records"] += 1
    active = {i for edge in routes for i in edge}
    audit["catalog_airports_without_retained_route"] = len(airports) - len(active)
    audit["parallel_records_collapsed"] = audit["valid_nonstop_records"] - len(routes)
    return {i: airports[i] for i in sorted(active)}, routes, dict(audit)

def neo4j_analysis(airports, routes, graph):
    uri = os.getenv("AIRPORT_NEO4J_URI", "bolt://127.0.0.1:17687")
    user = os.getenv("AIRPORT_NEO4J_USER")
    auth = (user, os.environ["AIRPORT_NEO4J_PASSWORD"]) if user else None
    with GraphDatabase.driver(uri, auth=auth) as driver:
        with driver.session(database="neo4j") as session:
            def query(cypher, **params):
                return session.run(cypher, **params).data()
            def batch(cypher, rows):
                for i in range(0, len(rows), 2000):
                    query(cypher, rows=rows[i:i+2000])
            version = query("RETURN gds.version() AS version")[0]["version"]
            query("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Airport) REQUIRE a.id IS UNIQUE")
            batch("UNWIND $rows AS row MERGE (a:Airport {id:row.id}) SET a += row", list(airports.values()))
            batch("""UNWIND $rows AS row MATCH (a:Airport {id:row.a}),(b:Airport {id:row.b})
                     MERGE (a)-[r:ROUTE_TO]->(b) SET r.airlines=row.airlines""",
                  [dict(a=a,b=b,airlines=len(v)) for (a,b),v in routes.items()])
            batch("""UNWIND $rows AS row MATCH (a:Airport {id:row.a}),(b:Airport {id:row.b})
                     MERGE (a)-[:CONNECTED_TO]->(b)""",
                  [dict(a=min(a,b),b=max(a,b)) for a,b in graph.edges])
            audit = query("""MATCH (a:Airport)
                OPTIONAL MATCH (a)-[r:ROUTE_TO]->(b)
                RETURN count(DISTINCT a) AS nodes, count(r) AS routes,
                count(DISTINCT [a.id,b.id])-count(DISTINCT CASE WHEN b IS NULL THEN a.id END) AS unique_pairs,
                sum(CASE WHEN a=b THEN 1 ELSE 0 END) AS loops""")[0]
            audit["isolates"] = query("MATCH (a:Airport) WHERE NOT (a)-[:ROUTE_TO]-() RETURN count(a) AS n")[0]["n"]
            assert audit == dict(nodes=len(airports), routes=len(routes), unique_pairs=len(routes), loops=0, isolates=0), audit
            query("CALL gds.graph.drop('airports',false) YIELD graphName RETURN graphName")
            projection = query("""CALL gds.graph.project('airports','Airport',
                {CONNECTED_TO:{orientation:'UNDIRECTED'}})
                YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount""")[0]
            assert projection == dict(nodeCount=len(graph),relationshipCount=2*graph.number_of_edges())
            result = {}
            for name in ("louvain", "labelPropagation"):
                rows = query(f"""CALL gds.{name}.stream('airports', {{concurrency:1}})
                    YIELD nodeId,communityId RETURN gds.util.asNode(nodeId).id AS id,communityId""")
                result[name] = {r["id"]: r["communityId"] for r in rows}
                assert set(result[name]) == set(graph)
            rows = query("""CALL gds.betweenness.stream('airports',{concurrency:1})
                YIELD nodeId,score RETURN gds.util.asNode(nodeId).id AS id,score""")
            bet = {r["id"]: r["score"] for r in rows}
            assert set(bet) == set(graph)
            query("CALL gds.graph.drop('airports') YIELD graphName RETURN graphName")
            return result, bet, version, audit

def partition_stats(graph, labels):
    groups = defaultdict(set)
    for node, label in labels.items():
        groups[label].add(node)
    profiles = []
    for label, members in sorted(groups.items(), key=lambda item: (-len(item[1]),item[0])):
        countries = Counter(graph.nodes[n]["country"] for n in members)
        examples = sorted(members, key=lambda n: (-graph.degree[n], n))[:4]
        profiles.append(dict(community=label, size=len(members),
                             countries=" | ".join(f"{c}: {k}" for c,k in countries.most_common(5)),
                             examples=" | ".join(graph.nodes[n]["code"] for n in examples)))
    return dict(count=len(groups), modularity=nx.community.modularity(graph, list(groups.values())),
                sizes=[p["size"] for p in profiles], profiles=profiles[:5])

def plot(name, title, xlabel, ylabel):
    plt.title(title, loc="left", weight="bold")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(OUT / f"{name}.png", dpi=170)
    plt.close()

def cluster_features(rows):
    feature_names = ["degree", "betweenness", "triangles", "clustering"]
    node_features = pd.DataFrame.from_records(rows).set_index("id")[feature_names]
    node_features.to_csv(OUT / "node_features.csv")
    matrix = np.ascontiguousarray(node_features.to_numpy(dtype=float, copy=True))
    matrix[:, :3] = np.log1p(matrix[:, :3])
    features = StandardScaler().fit_transform(matrix)
    candidates = []
    for k in range(2, 9):
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(features)
        score = float(silhouette_score(features, model.labels_))
        candidates.append((k, score, float(model.inertia_), model.labels_))
    return candidates


def main():
    airports, routes, audit = load_data()
    directed = nx.DiGraph()
    directed.add_nodes_from(airports.items())
    directed.add_edges_from(routes)
    graph = directed.to_undirected()
    n,m = len(graph),graph.number_of_edges()
    assert 500 <= n <= 50000 and nx.number_of_selfloops(graph) == 0
    print(f"Cleaned {n} airports, {len(routes)} directed routes and {m} unordered pairs", flush=True)
    labels, bet, version, database_audit = neo4j_analysis(airports,routes,graph)
    print(f"Neo4j audit passed and GDS {version} algorithms ran", flush=True)
    components = sorted(nx.connected_components(graph),key=len,reverse=True)
    giant = graph.subgraph(components[0])
    rng = random.Random(SEED)
    sources = rng.sample(sorted(giant), min(128,len(giant)))
    def mean_distance(g, sample):
        total = count = 0
        for source in sample:
            dist = nx.single_source_shortest_path_length(g,source)
            total += sum(dist.values())
            count += len(dist)-1
        return total/count
    triangles = nx.triangles(graph)
    clustering = nx.clustering(graph)
    # Uniform G(n,m): a triangle needs three specified edges sampled without replacement.
    pairs = math.comb(n,2)
    expected = math.comb(n,3)*math.prod((m-i)/(pairs-i) for i in range(3))
    random_graph = nx.gnm_random_graph(n,m,seed=SEED)
    random_giant = random_graph.subgraph(max(nx.connected_components(random_graph), key=len))
    louvain = labels["louvain"]
    lp = labels["labelPropagation"]
    rows = []
    for node in graph:
        cross = [v for v in graph[node] if louvain[v] != louvain[node]]
        rows.append(dict(**airports[node], in_degree=directed.in_degree[node],out_degree=directed.out_degree[node],
                         degree=graph.degree[node],betweenness=bet[node],triangles=triangles[node],
                         clustering=clustering[node],louvain=louvain[node],label_propagation=lp[node],
                         cross_links=len(cross),cross_fraction=len(cross)/graph.degree[node],
                         external_communities=len({louvain[v] for v in cross})))
    keys = ["in_degree","out_degree","degree","betweenness"]
    rankings = {key: sorted(rows,key=lambda r:(-r[key],r["id"]))[:10] for key in keys}
    overlap = sorted({r["code"] for r in rankings["degree"]} & {r["code"] for r in rankings["betweenness"]})
    candidates = cluster_features(rows)
    k,sil,_,roles = max(candidates,key=lambda c:c[1])
    for row, role in zip(rows,roles):
        row["role"] = int(role)
    role_profiles = []
    role_overlap = []
    for role in range(k):
        members = [r for r in rows if r["role"] == role]
        role_profiles.append(dict(role=role,size=len(members),**{
            f"median_{key}":float(np.median([r[key] for r in members]))
            for key in ("degree","betweenness","triangles","clustering","cross_fraction")}))
        role_overlap.extend(dict(role=role,louvain=community,count=count)
                            for community,count in Counter(r["louvain"] for r in members).most_common())
    write_csv("airport_metrics.csv",rows)
    write_csv("role_community_overlap.csv",role_overlap)
    write_csv("role_profiles.csv",role_profiles)
    for key in keys:
        write_csv(f"top10_{key}.csv",rankings[key])
    for key in ("in_degree","out_degree"):
        freq = Counter(r[key] for r in rows)
        x = sorted(d for d in freq if d > 0)
        plt.scatter(x,[freq[d] for d in x],s=9,label=f"{key.replace('_',' ')} (zero: {freq[0]})")
    plt.xscale("log")
    plt.yscale("log")
    plt.legend()
    plot("degree","Direct route degree","Number of distinct directed neighbors","Number of airports")
    plt.scatter([r["degree"] for r in rows],[1+r["betweenness"] for r in rows],s=7,alpha=.32)
    plt.xscale("log")
    plt.yscale("log")
    for r in rankings["betweenness"][:3]:
        plt.annotate(r["code"],(r["degree"],1+r["betweenness"]),fontsize=8)
    plot("gateways","Degree and betweenness","Undirected degree","1 + GDS betweenness")
    stats = {name:partition_stats(graph,mapping) for name,mapping in labels.items()}
    groups_lp = defaultdict(set)
    groups_louvain = defaultdict(set)
    for node in graph:
        groups_lp[lp[node]].add(node)
        groups_louvain[louvain[node]].add(node)
    for profile in stats["louvain"]["profiles"]:
        group = groups_louvain[profile["community"]]
        label, score = max(((label, len(group & other)/len(group | other)) for label,other in groups_lp.items()),key=lambda item:item[1])
        profile["best_lp"] = label
        profile["jaccard"] = score
    for name, st in stats.items():
        plt.plot(range(1,1+len(st["sizes"])),st["sizes"],".-",label=name)
    plt.yscale("log")
    plt.legend()
    plot("community_sizes","Community sizes","Community rank by size","Airports")
    top = [p["community"] for p in stats["louvain"]["profiles"]]
    for group in [None,*top]:
        points = [r for r in rows if (r["louvain"] not in top if group is None else r["louvain"]==group)]
        plt.scatter([r["lon"] for r in points],[r["lat"] for r in points],s=5 if group is None else 9,
                    color="lightgray" if group is None else None,label="Other" if group is None else str(group))
    plt.legend(title="Louvain ID",fontsize=7)
    plot("community_map","Airport locations by Louvain community","Longitude","Latitude")
    plt.plot([c[0] for c in candidates],[c[1] for c in candidates],"o-")
    plot("silhouette","Choosing K for structural profiles","K","Mean silhouette")
    summary = dict(audit=audit,database=database_audit,gds_version=version,n=n,m=m,
                   directed_edges=len(routes),components=len(components),largest=len(giant),
                   strong_components=nx.number_strongly_connected_components(directed),
                   distance_sample=len(sources),mean_distance=mean_distance(giant,sources),
                   random_largest=len(random_giant),
                   random_mean_distance=mean_distance(random_giant,rng.sample(sorted(random_giant),min(128,len(random_giant)))),
                   triangles=sum(triangles.values())//3,expected_triangles=expected,
                   clustering=float(np.mean(list(clustering.values()))),random_clustering=nx.average_clustering(random_graph),
                   degree={key:dict(mean=float(np.mean([r[key] for r in rows])),max=max(r[key] for r in rows)) for key in keys[:3]},
                   overlap=overlap,spearman=float(spearmanr([r["degree"] for r in rows],[r["betweenness"] for r in rows]).statistic),
                   communities=stats,community_ari=adjusted_rand_score([louvain[i] for i in graph],[lp[i] for i in graph]),
                   kmeans=dict(k=k,silhouette=sil,candidates=[list(c[:3]) for c in candidates],
                               ari=adjusted_rand_score([r["louvain"] for r in rows],roles),profiles=role_profiles),
                   rankings=rankings,morocco=sorted([r for r in rows if r["country"]=="Morocco"],key=lambda r:-r["betweenness"]))
    (OUT / "summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Saved measured outputs to {OUT}", flush=True)

if __name__ == "__main__":
    main()


