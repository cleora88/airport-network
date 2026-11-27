# Hubs versus Gateways

Zouhair Eouichak, Malak Bartal, Aymane El Youssi · TP B

Do airports with the most direct connections also connect the communities of the historical global airport network?

## Reproduce

1. Use a dedicated empty Neo4j 2025.08.0 database with GDS 2.21.0 enabled. For the isolated local run, the driver defaults to bolt://127.0.0.1:17687. To use Neo4j Desktop, set AIRPORT_NEO4J_URI, AIRPORT_NEO4J_USER and AIRPORT_NEO4J_PASSWORD in your shell. Never use an existing course database for this import.
2. Install dependencies with python -m pip install -r requirements.txt.
3. Run python analyze.py. The pipeline imports the graph with Cypher, checks database counts, and runs GDS Louvain, Label Propagation and betweenness. Python computes the remaining metrics, matplotlib charts and K-means. Pandas builds and exports the D3 node-feature table, and NumPy transforms its values. The outputs are in results/.
4. Import schema.arrows.json into Arrows.app to inspect the database schema. CONNECTED_TO is stored once per unordered pair and projected as undirected for the analytical view. ROUTE_TO preserves the direction in the archive.
5. Run python publish.py to rebuild the report and slides from the measured results. On another machine, place the UIR logo beside the script as UIR_logo.png or set UIR_LOGO to its path.

## Data

OpenFlights, historical route archive documented in June 2014. [Documentation](https://openflights.org/data) and [repository](https://github.com/jpatokal/openflights/tree/master/data). The airport and route data are available under the Open Database License. The files are bundled for reproduction. See data/SHA256SUMS.txt for the exact input snapshot. The airport catalog and route archive have different coverage.

Routes are unweighted for analysis. The airline count property counts distinct known airline IDs. Airport geography is descriptive metadata. Flight frequency, passenger counts, schedules and connection times are outside the scope of the archive.

## Outputs

- results/summary.json holds the analysis metadata and metrics.
- results/airport_metrics.csv lists per-airport measurements and partition assignments.
- results/top10_*.csv lists the ranking evidence.
- results/role_profiles.csv and role_community_overlap.csv support D3.
- Hubs_versus_Gateways_Report.pdf and Hubs_versus_Gateways_Slides.pdf are the two Connect deliverables.

- results/node_features.csv is the pandas feature table used by D3.
