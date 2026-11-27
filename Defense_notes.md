# Presentation and individual Q&A

## Speaking order

- Zouhair, 3:35, slides 1–5. Question, schema, cleaning, degree, paths and triangles.
- Malak, 3:00, slides 6–9. Top-ten rankings, bridging airports, algorithm comparison and five Louvain communities.
- Aymane, 3:25, slides 10–13. Five Label Propagation communities, K-means and the final insights.
- Total main presentation time is 10:00. Slide 14 holds role statistics for Q&A.

## Questions every member should be able to answer

1. **What does a route mean?** One listed nonstop connection in one direction. Several airline records can describe the same connection. Counts do not measure flight frequency.
2. **Why two graph views?** Directed routes preserve origins and destinations. A deduplicated undirected projection supports comparisons on one simple graph. Its paths can traverse a route in either direction.
3. **Why do average in-degree and out-degree match?** Each edge adds one to one departure airport's out-degree and one to one arrival airport's in-degree.
4. **What is the triangle baseline?** Draw exactly m of the possible airport pairs uniformly without replacement. Three specified pairs must all be drawn to form a triangle. Multiply their joint probability by the number of airport triples.
5. **What do shortest paths measure?** Number of legs in the modeled graph. The estimate averages distances from 128 sampled sources to the rest of the largest component.
6. **What does betweenness measure?** For each pair, it counts the fraction of shortest paths through an intermediate node, then adds those fractions.
7. **Why compare degree and cross-community links as well?** High betweenness can reflect a central role within a group. Links to airports in other communities make the interpretation specific to bridging.
8. **Why might Louvain and Label Propagation differ?** Louvain searches for a high-modularity partition. Label Propagation changes labels according to neighbors' labels. The methods can split and merge groups differently.
9. **What do modularity and ARI measure?** Modularity compares within-group links against degree-based expectations. ARI measures agreement between partitions and adjusts for chance.
10. **Why transform and scale the K-means inputs?** Log transformation reduces the skew of count-like measures. Standardization makes feature magnitudes comparable for Euclidean distance.
11. **What is the key dataset limitation?** OpenFlights describes a historical route snapshot. Geographic metadata help interpret communities, and the archive gives no passenger counts or current route schedule.
