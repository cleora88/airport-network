from pathlib import Path
from xml.sax.saxutils import escape
import os
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4

BASE = Path(__file__).resolve().parent
R = BASE / "results"
BLUE = HexColor("#153047")
TEAL = HexColor("#007D82")
GRAY = HexColor("#486173")
PALE = HexColor("#EAF2F4")
LOGO = Path(os.getenv("UIR_LOGO", str(BASE / "UIR_logo.png")))
TEAM = "Zouhair Eouichak, Malak Bartal and Aymane El Youssi"
SOURCE = "https://github.com/jpatokal/openflights/tree/master/data"
S = json.loads((R/"summary.json").read_text(encoding="utf-8"))
A = S["audit"]
L = S["communities"]["louvain"]
P = S["communities"]["labelPropagation"]
K = S["kmeans"]
top = S["rankings"]
fmt = lambda n: f"{n:,}"
overlap = ", ".join(S["overlap"])
match = len(S["overlap"])
by_degree = {r["id"]:i for i,r in enumerate(sorted(top["degree"],key=lambda r:(-r["degree"],r["id"])),1)}
bridge = next((r for r in top["betweenness"] if r["cross_links"] and r["id"] not in by_degree),top["betweenness"][0])
anchorage = next((r for r in top["betweenness"] if r["code"]=="ANC"),None)
cmn = next((r for r in S["morocco"] if r["code"]=="CMN"),None)

def para(text, size=10.5, color=BLUE, bold=False):
    return Paragraph(text,ParagraphStyle("p",fontName="Helvetica-Bold" if bold else "Helvetica",fontSize=size,
                                         leading=size*1.36,textColor=color,spaceAfter=8))
def fig(name, width=445):
    path = R/("schema-arrows.png" if name == "schema" else f"{name}.png")
    x,y = ImageReader(str(path)).getSize()
    return Image(str(path),width,width*y/x)

def table(rows,widths):
    t = Table([[para(escape(str(cell)),9,bold=i==0) for cell in row] for i,row in enumerate(rows)],
              colWidths=widths,repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),PALE),("ROWBACKGROUNDS",(0,1),(-1,-1),[white,HexColor("#F6F9FA")]),
                           ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),4),
                           ("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    return t

def schema(path):
    c=canvas.Canvas(str(path),pagesize=(700,195))
    c.setFillColor(PALE)
    for x,label in ((24,"Departure"),(505,"Arrival")):
        c.roundRect(x,30,170,135,12,stroke=0,fill=1)
        c.setFillColor(TEAL);c.setFont("Helvetica-Bold",15);c.drawString(x+13,140,":Airport")
        c.setFillColor(BLUE);c.setFont("Helvetica",12)
        for i,line in enumerate((label,"id, name, code","city, country","lat, lon")):
            c.drawString(x+13,117-18*i,line)
        c.setFillColor(PALE)
    c.setStrokeColor(TEAL);c.setFillColor(BLUE);c.setLineWidth(2)
    c.line(195,104,502,104);c.line(493,110,502,104);c.line(493,98,502,104)
    c.line(195,57,502,57)
    c.setFont("Helvetica-Bold",12)
    c.drawCentredString(349,122,"ROUTE_TO {airlines}")
    c.drawCentredString(349,69,"CONNECTED_TO (undirected view)")
    c.save()

def report():
    name=BASE/"Hubs_versus_Gateways_Report.pdf"
    story=[]
    def add(t): story.append(para(t))
    def heading(t): story.append(para(t,19,TEAL,True))
    def page(t):
        story.append(PageBreak());heading(t)
    if LOGO.is_file():
        x,y=ImageReader(str(LOGO)).getSize()
        im=Image(str(LOGO),170,170*y/x);im.hAlign="LEFT";story.append(im)
    story.append(Spacer(1,32))
    story.append(para("DATA MINING PROJECT",10,TEAL,True))
    story.append(para("Hubs versus Gateways",32,BLUE,True))
    story.append(para("Communities and strategic connections in the global airport network",16,GRAY))
    add(f"<b>{TEAM}</b><br/>TP B · Prof. BERKANI Safaa · 10 November 2026")
    heading("Q1 · Research question")
    add("Do the most connected airports also act as gateways between communities of the global airport network?")
    add("Direct connectivity measures how many airports can be reached in one step. Betweenness measures how often an airport lies on shortest paths between other airports. Their overlap helps distinguish airports that offer many destinations from those that also connect parts of the network.")
    heading("Main result")
    add(f"<b>{match} of the top 10 airports appear in both rankings.</b> Degree and betweenness have a Spearman rank correlation of {S['spearman']:.2f} across all airports. Community links and individual airport profiles explain where the rankings diverge.")
    add(f"Source: <link href='{SOURCE}' color='#007D82'>OpenFlights airport and route files</link>. The route archive is historical and was documented in June 2014. Input checksums are bundled with the analysis.")
    page("Part A · Building the graph")
    add("<b>Q2. Property graph.</b> Airport nodes carry ID, code, name, city, country and coordinates. ROUTE_TO records the ordered source and destination of a listed nonstop route. The airlines property counts distinct known airline IDs. Analysis uses unweighted edges.")
    add("The Cypher import also stores one CONNECTED_TO edge per unordered airport pair, ordered by airport ID. GDS projects those edges as undirected. An edge in the projected graph means a route exists in at least one direction. The schema below was created and verified in Arrows.app. CONNECTED_TO uses a canonical stored direction by airport ID and is projected as undirected for analysis.")
    story.append(fig("schema",470))
    add("A flat route table can preserve the raw attributes. Multi-leg paths, shared neighbors and communities must be reconstructed with joins or recursive queries. A separate airport catalog is needed to represent airports absent from the route table.")
    add("<b>Q3. Import and validation.</b> Python parses the two source files and prepares the rows. Cypher creates the uniqueness constraint and imports nodes and relationships in batches. A database query independently verifies the cleaned counts.")
    story.append(table([["Input and cleaning audit","Count"],
      ["Raw airline route records",fmt(A["raw_records"])],
      ["Exact duplicate rows",fmt(A["exact_duplicate_records"])],
      ["Excluded because the route was not nonstop",fmt(A["nonstop_filter_excluded"])],
      ["Excluded because an endpoint could not be matched",fmt(A["unmatched_endpoint_records"])],
      ["Removed self-loop records",fmt(A["self_loop_records"])],
      ["Valid records collapsed into existing ordered pairs",fmt(A["parallel_records_collapsed"])],
      ["Catalog airports without a retained route",fmt(A["catalog_airports_without_retained_route"])],
      ["Airports / directed routes / undirected pairs",f"{fmt(S['n'])} / {fmt(S['directed_edges'])} / {fmt(S['m'])}"]],[350,130]))
    add(f"The database contains zero duplicate directed pairs, self-loops and isolates. We retained {A['records_without_airline_id']} valid route records without a known airline ID in connectivity. Removing unused catalog entries defines the population as airports represented by retained routes. Missing endpoints may understate connectivity and can affect bridge rankings.")
    page("Part B · Connectivity and local structure")
    d=S["degree"]
    add(f"<b>Q4. Directed degree.</b> Mean in-degree and out-degree are both {d['in_degree']['mean']:.2f} because each directed route contributes one to each total. Maximum in-degree is {d['in_degree']['max']} and maximum out-degree is {d['out_degree']['max']}. The maxima far exceed the means, indicating a concentration of direct connections among a small set of airports.")
    story.append(fig("degree",380))
    story.append(table([["Rank","Incoming routes","Outgoing routes"]]+[[i+1,f"{a['code']} ({a['in_degree']})",f"{b['code']} ({b['out_degree']})"] for i,(a,b) in enumerate(zip(top["in_degree"],top["out_degree"]))],[55,212,212]))
    page("Part B · Distances, triangles and bridges")
    add(f"<b>Q5. Components and shortest paths.</b> The undirected view has {S['components']} components. Its largest contains {fmt(S['largest'])} airports ({100*S['largest']/S['n']:.1f}%). The directed graph has {S['strong_components']} strongly connected components. Using {S['distance_sample']} uniformly sampled source airports (seed 42), we measured paths to all other airports in the largest undirected component. The mean was <b>{S['mean_distance']:.2f} legs</b>. One uniform random graph with the same n and m averaged {S['random_mean_distance']:.2f} legs on its own largest component. The airport graph combines paths of a few legs with much greater clustering, consistent with small-world structure under this comparison. Reversing routes in the projection can shorten paths.")
    add(f"<b>Q6. Triangles and clustering.</b> We counted {fmt(S['triangles'])} triangles and measured mean local clustering of {S['clustering']:.3f}, assigning zero to degrees below two. In a uniform simple graph with fixed n and m, the expected triangle count is {S['expected_triangles']:,.1f}. For M = n(n-1)/2 possible edges, the expectation is C(n,3) times m(m-1)(m-2) / [M(M-1)(M-2)]. The observed count is {S['triangles']/S['expected_triangles']:.1f} times the baseline. The sampled random graph had mean clustering {S['random_clustering']:.3f}. Triadic closure is much more common in the archive. The baseline does not preserve airport degrees or geography.")
    add(f"<b>Q7. Betweenness.</b> GDS counts shortest paths that pass through each node, dividing credit among tied paths. Rankings below use the same undirected graph and break ties by airport ID. {match} of the top 10 overlap ({overlap or 'none'}).")
    story.append(table([["Rank","Degree (neighbors)","Betweenness (GDS score)"]]+[[i+1,f"{a['code']} ({a['degree']})",f"{b['code']} ({b['betweenness']:,.0f})"] for i,(a,b) in enumerate(zip(top["degree"],top["betweenness"]))],[55,212,212]))
    page("Part C · Community detection")
    add(f"<b>Q8. Partition sizes and modularity.</b> We ran both algorithms in Neo4j GDS {S['gds_version']} on the same undirected projection. We computed standard undirected modularity at resolution 1 for both partitions using the same edge set and degree-based null model.")
    story.append(table([["Method","Groups","Largest","Modularity"],["Louvain",L["count"],L["sizes"][0],f"{L['modularity']:.3f}"],["Label Propagation",P["count"],P["sizes"][0],f"{P['modularity']:.3f}"]],[200,85,85,110]))
    story.append(fig("community_sizes",400))
    add(f"<b>Q9. Agreement.</b> The adjusted Rand index (ARI) is {S['community_ari']:.3f}. ARI measures agreement between pairwise co-memberships after adjusting for chance. A score of 1 means identical partitions. Louvain greedily optimizes modularity while Label Propagation updates a node using its neighbors' labels. Their different objectives and tie behavior can produce groups of different sizes.")
    story.append(table([["Louvain ID","Closest LP ID","Jaccard overlap"]]+[[p["community"],p["best_lp"],f"{p['jaccard']:.2f}"] for p in L["profiles"]],[160,160,160]))
    add("Jaccard overlap divides the number of common members by the total number of distinct members. Each Louvain group is matched independently to its best Label Propagation group.")
    page("Part C · Geography of the largest groups")
    add("<b>Q10. The largest communities.</b> Country counts and representative high-degree airports provide descriptive labels. Country metadata serve as context for interpretation. No reference partition is supplied with the archive.")
    add("Louvain's five largest groups are centered on North America, Europe, East and Southeast Asia, South and West Asia, and South America. Label Propagation puts much of the world into one group and retains smaller clusters, including an Oceania group and an Argentina-centered group.")
    for label, group in (("Louvain",L),("Label Propagation",P)):
        story.append(para(label,12,TEAL,True))
        story.append(table([["ID","Size","Geographic profile (airport counts)","Airport codes"]]+[[p["community"],p["size"],p["countries"],p["examples"]] for p in group["profiles"]],[42,46,272,120]))
    page("Part C · Airports that connect communities")
    story.append(fig("community_map",420))
    add("<b>Q11. Bridge candidates.</b> The table combines betweenness and cross-community neighbors. A cross-link is an unordered pair whose endpoints have different Louvain labels.")
    story.append(table([["Airport","Degree","Cross-links","Other groups"]]+[[r["code"],r["degree"],r["cross_links"],r["external_communities"]] for r in top["betweenness"][:5]],[165,105,105,105]))
    add(f"{escape(bridge['name'])} ({bridge['code']}) links to {bridge['cross_links']} airports in {bridge['external_communities']} other Louvain communities, with {bridge['degree']} total neighbors. Cross-links describe direct connections across one inferred partition. Betweenness captures a separate shortest-path role.")
    if anchorage:
        add(f"Anchorage ranks third for betweenness with {anchorage['degree']} direct neighbors. Its {anchorage['cross_links']} cross-community links reach just {anchorage['external_communities']} other Louvain community. High betweenness can reflect a concentrated route out of a community even when an airport connects to relatively few other groups.")
    page("Part D3 · Structural roles")
    add(f"We built a pandas feature table and formed a feature vector for each airport with degree, betweenness, triangle count and local clustering. We applied log(1+x) to the three count-like features to reduce skew, then standardized all four. For each K from 2 through 8, we ran K-means with ten initializations and seed 42. K = {K['k']} gave the highest average silhouette ({K['silhouette']:.3f}).")
    story.append(fig("silhouette",390))
    story.append(table([["Role","Airports","Median degree","Median triangles","Median clustering"]]+[[p["role"],p["size"],f"{p['median_degree']:.0f}",f"{p['median_triangles']:.0f}",f"{p['median_clustering']:.2f}"] for p in K["profiles"]],[55,85,105,110,125]))
    add(f"Agreement with Louvain is ARI {K['ari']:.3f}. The low ARI indicates that features and connections produce substantially different groups. K-means compares numerical airport profiles, while Louvain groups airports by connections. The role/community cross-tabulation and raw-feature medians are provided in the results folder. Correlated features can give connectivity extra influence, and the silhouette favors compact groups in the standardized feature space.")
    page("Part E · What the network shows")
    add(f"<b>Q12. Do the largest hubs also serve as gateways?</b> The rankings overlap for {match} of 10 airports. Degree and betweenness correlate at {S['spearman']:.2f} across all airports. {bridge['code']} illustrates why rankings and community links both matter. It has {bridge['degree']} direct neighbors, including {bridge['cross_links']} outside its Louvain community. Betweenness uses the fewest flight legs on an undirected historical graph.")
    story.append(fig("gateways",410))
    add(f"<b>Insight 1. Do routes form more local groups than chance predicts?</b> We observed {fmt(S['triangles'])} triangles versus {S['expected_triangles']:,.1f} expected. The archived network contains more tightly linked triples than the uniform fixed-size baseline. The baseline ignores geographic and degree constraints.")
    add(f"<b>Insight 2. Do the community algorithms tell the same story?</b> Louvain finds {L['count']} groups and Label Propagation finds {P['count']}, with an ARI of {S['community_ari']:.3f}. This low score indicates substantially different community assignments. This compares one run per method on one graph representation.")
    if cmn:
        add(f"<b>Insight 3. How does Casablanca connect across the partition?</b> CMN has {cmn['degree']} neighbors, including {cmn['cross_links']} across {cmn['external_communities']} other Louvain communities. This gives a concrete measure of its gateway role in the archive. Routes describe available links at the time of the snapshot. Actual traffic and modern schedules are outside its coverage.")
    def footer(c,doc):
        c.setStrokeColor(PALE);c.line(49,39,545,39)
        c.setFont("Helvetica",8);c.setFillColor(GRAY);c.drawString(49,26,"UIR  /  Data Mining  /  TP B");c.drawRightString(545,26,str(doc.page))
    SimpleDocTemplate(str(name),pagesize=A4,leftMargin=55,rightMargin=55,topMargin=48,bottomMargin=54,
                      title="Hubs versus Gateways",author=TEAM).build(story,onFirstPage=footer,onLaterPages=footer)

def slides():
    c=canvas.Canvas(str(BASE/"Hubs_versus_Gateways_Slides.pdf"),pagesize=(960,540))
    def text(t,x,y,w,size=22,bold=False,color=BLUE):
        block=para(t,size,color,bold)
        _,h=block.wrap(w,500)
        block.drawOn(c,x,y-h)
        return y-h-17
    def image(path,x,y,w,h):
        c.drawImage(str(path),x,y,w,h,preserveAspectRatio=True,anchor="c",mask="auto")
    def slide(section,title,points,chart=None):
        c.setFillColor(HexColor("#F7FAFA"));c.rect(0,0,960,540,fill=1,stroke=0)
        c.setFillColor(TEAL);c.rect(0,532,960,8,fill=1,stroke=0)
        text(section,52,498,850,12,True,TEAL)
        bottom=text(title,52,467,855,31,True)
        if chart:
            image(R/("schema-arrows.png" if chart == "schema" else f"{chart}.png"),420,63,480,319)
        for point in points:
            bottom=text(point,52,bottom-4,355 if chart else 830,17 if chart else 20)
        c.setFont("Helvetica",10);c.setFillColor(GRAY)
        c.drawString(52,24,"UIR  /  Data Mining  /  TP B")
        c.drawRightString(907,24,str(c.getPageNumber()))
        c.showPage()
    def appendix(section,title,headers,rows,widths):
        c.setFillColor(HexColor("#F7FAFA"));c.rect(0,0,960,540,fill=1,stroke=0)
        c.setFillColor(TEAL);c.rect(0,532,960,8,fill=1,stroke=0)
        text(section,52,498,850,12,True,TEAL)
        y=text(title,52,466,850,31,True)
        grid=table([headers]+rows,widths)
        _,h=grid.wrap(850,380)
        assert y-h > 30
        grid.drawOn(c,52,y-h)
        c.showPage()
    slide("Q1  /  0:30  /  ZOUHAIR","Hubs versus Gateways",[TEAM,
      "Do the airports with the most direct connections also bridge airport communities?",
      "The question connects destination choice with the structure of regional connections. OpenFlights route archive, documented June 2014."])
    slide("Q2  /  0:50  /  ZOUHAIR","Airport nodes and two relationship types",[
      "Airport properties include ID, name, code, city, country and coordinates.",
      "ROUTE_TO preserves direction. Its airlines property counts distinct known airline IDs.",
      "Analysis uses unweighted routes and a simple undirected CONNECTED_TO projection.",
      "A single route table requires joins to recover paths and shared neighbors, and a separate catalog to represent isolated airports."],"schema")
    slide("Q3  /  0:40  /  ZOUHAIR","Cleaning defines the airport population",[
      f"Cypher imports {fmt(S['n'])} airports and {fmt(S['directed_edges'])} directed routes. The undirected view has {fmt(S['m'])} pairs.",
      f"From {fmt(A['raw_records'])} rows, exclude {A['nonstop_filter_excluded']} routes with stops, {A['unmatched_endpoint_records']} unmatched endpoint records and {A['self_loop_records']} self-loop.",
      f"Collapse {fmt(A['parallel_records_collapsed'])} parallel records. Exclude {fmt(A['catalog_airports_without_retained_route'])} catalog airports without retained routes.",
      "Loaded checks give zero duplicate pairs, loops and isolates. Missing endpoints may understate connectivity and change bridge rankings."])
    slide("Q4  /  0:45  /  ZOUHAIR","A few airports have many direct connections",[
      f"Mean incoming and outgoing degree {S['degree']['in_degree']['mean']:.2f}.",
      f"Maximum incoming degree {S['degree']['in_degree']['max']}. Maximum outgoing degree {S['degree']['out_degree']['max']}.",
      "The long tail and large gap between mean and maximum show a concentration of connections among hubs. Log axes show the tail."],"degree")
    slide("Q5–Q6  /  0:50  /  ZOUHAIR","Short paths coexist with dense local groups",[
      f"{S['components']} undirected components. The largest contains {fmt(S['largest'])} airports. There are {S['strong_components']} directed strong components.",
      f"128 uniformly sampled sources, seed 42, give a mean of {S['mean_distance']:.2f} legs to all other nodes in the largest component. Random comparison {S['random_mean_distance']:.2f}.",
      f"{fmt(S['triangles'])} triangles versus {S['expected_triangles']:,.1f} expected for a uniform simple graph with the same n and m. Mean local clustering {S['clustering']:.3f}, versus {S['random_clustering']:.3f} in one random graph.",
      "Few-leg paths and much higher clustering support a small-world interpretation. Symmetrization can shorten paths. The baseline ignores degrees and geography."])
    appendix("Q4, Q7  /  0:45  /  MALAK","Top airports by connections and betweenness",
      ["Rank","In-degree","Out-degree","Undirected degree","GDS betweenness"],
      [[i+1,*[f"{top[key][i]['code']} ({top[key][i][key]:,.0f})" for key in ("in_degree","out_degree","degree","betweenness")]] for i in range(10)],
      [60,185,185,185,205])
    slide("Q7, Q11  /  0:55  /  MALAK","Gateways and hubs overlap only partly",[
      f"{match}/10 airports appear in both undirected rankings. Spearman correlation {S['spearman']:.2f}.",
      f"LAX has {bridge['degree']} neighbors and {bridge['cross_links']} links into {bridge['external_communities']} other Louvain groups.",
      "Anchorage ranks third in betweenness with 34 neighbors. Its 10 cross-links reach one other community.",
      "These airports connect shortest routes across the network. Betweenness shares credit among tied paths. A few intergroup links can support a large bridging role."],"gateways")
    slide("Q8–Q9  /  0:40  /  MALAK","Community assignments have low agreement",[
      f"GDS Louvain gives {L['count']} groups, modularity {L['modularity']:.3f}.",
      f"GDS Label Propagation gives {P['count']} groups, modularity {P['modularity']:.3f}.",
      f"ARI {S['community_ari']:.3f} indicates low agreement. The largest LP group absorbs much of the network.",
      "Louvain improves modularity. Label Propagation follows neighbor labels. Their objectives and tie behavior explain different boundaries."],"community_sizes")
    appendix("Q10  /  0:40  /  MALAK","Five largest Louvain communities",
      ["Descriptive name","ID","Airports","Representative airports"],
      [[name,p["community"],p["size"],p["examples"]] for name,p in zip(
      ["North America","Europe","East and Southeast Asia","South and West Asia","South America"],L["profiles"])],
      [265,90,110,355])
    appendix("Q10  /  0:50  /  AYMANE","Five largest Label Propagation communities",
      ["Descriptive name","Airports","Leading countries","Examples"],
      [[name,p["size"],p["countries"],p["examples"]] for name,p in zip(
      ["Global core","Oceania","Canada and Greenland","Argentina and Uruguay","US regional cluster"],P["profiles"])],
      [145,70,430,175])
    slide("D3  /  1:00  /  AYMANE","Feature clusters differ from route communities",[
      "A pandas table holds degree, betweenness, triangles and local clustering. NumPy transforms the first three with log(1+x), then we standardize all four.",
      f"Ten initializations per K, seed 42. Highest silhouette {K['silhouette']:.3f} at K = {K['k']} among 2–8.",
      f"ARI {K['ari']:.3f} against Louvain indicates very low agreement. Similar numerical roles occur across connected communities.",
      "Country composition supplies descriptive context. The archive provides no ground-truth community partition."],"silhouette")
    slide("Q12  /  0:55  /  AYMANE","The biggest hubs are not always the gateways",[
      f"<b>Main answer.</b> Only {match} of the top 10 airports overlap. Degree and betweenness correlate at {S['spearman']:.2f}, while Anchorage demonstrates a gateway with fewer direct connections. Paths measure legs on the undirected historical graph.",
      f"<b>Do routes form more local groups than chance predicts?</b> {fmt(S['triangles'])} triangles versus {S['expected_triangles']:,.1f} expected. Airports form many more linked triples. The uniform baseline omits degree and geographic constraints.",
      f"<b>Do the community methods find the same groups?</b> ARI {S['community_ari']:.3f} indicates low agreement. LP merges many Louvain groups. This compares one run per method and one graph view."])
    slide("Q12  /  0:40  /  AYMANE","Casablanca connects across several communities",[
      f"<b>Does Casablanca bridge community boundaries?</b> CMN has {cmn['degree']} direct neighbors, with {cmn['cross_links']} links to airports in {cmn['external_communities']} other Louvain communities.",
      "It connects across several inferred groups in this archive. The finding describes the historical routes and depends on the chosen partition.",
      "OpenFlights supplies route availability. Passenger flows, schedules and connection times require additional data.",
      "Source — OpenFlights. Full source link is in the report."],"community_map")
    appendix("D3  /  Q&amp;A","Typical airport metrics by role cluster",
      ["Role","Airports","Degree","Betweenness","Triangles","Local clustering"],
      [[p["role"],p["size"],f"{p['median_degree']:.0f}",f"{p['median_betweenness']:,.0f}",f"{p['median_triangles']:.0f}",f"{p['median_clustering']:.2f}"] for p in K["profiles"]],
      [65,120,120,150,145,220])
    c.save()

if __name__ == "__main__":
    schema(R/"schema.pdf")
    if not (R/"schema.png").is_file():
        raise SystemExit("Render results/schema.pdf to results/schema.png, then rerun publish.py.")
    report()
    slides()



