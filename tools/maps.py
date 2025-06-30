import simplekml
import networkx as nx

line_style = simplekml.Style()
line_style.linestyle.width = 2
line_style.linestyle.color = simplekml.Color.salmon

point_style = simplekml.Style()
point_style.labelstyle.scale = 2
point_style.labelstyle.color = simplekml.Color.white
point_style.iconstyle.icon.href = 'https://app.diagrams.net/img/lib/clip_art/networking/Router_Icon_128x128.png'

node_coords = {}

kml = simplekml.Kml()
graph = nx.read_gml('BeyondTheNetwork.gml')
for name, properties in graph.nodes.items():
    try:
        point = kml.newpoint(name=name)
        coords = [(
            float(properties['Longitude']),
            float(properties['Latitude']),
        )]
        point.coords = coords
        node_coords[name] = coords
        point.style = point_style
    except KeyError:
        print(f'{name} not found')
        continue

for link in graph.edges():
    try:
        name = '{} - {}'.format(*link)
        line = kml.newlinestring(name=name)
        line.coords = [
            node_coords[link[0]][0],
            node_coords[link[1]][0],
        ]
        line.style = line_style
    except KeyError:
        print(f'{link} not found')
        continue

print(len(graph.nodes()))
print(len(graph.edges()))

kml.save('google_earth_export.kml')
