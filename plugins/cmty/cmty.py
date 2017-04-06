##
# this is from https://github.com/kjahan/community
##
# !/usr/bin/env python
import csv
import sys

import networkx as nx

_DEBUG_ = False


# this method just reads the graph structure from the file
def buildG(G, file_, delimiter_):
    # construct the weighted version of the contact graph from cgraph.dat file
    # reader = csv.reader(open("/home/kazem/Data/UCI/karate.txt"), delimiter=" ")
    reader = csv.reader(open(file_), delimiter=delimiter_)
    for line in reader:
        if len(line) > 2:
            if float(line[2]) != 0.0:
                # line format: u,v,w
                G.add_edge(int(line[0]), int(line[1]), weight=float(line[2]))
        else:
            # line format: u,v
            G.add_edge(int(line[0]), int(line[1]), weight=1.0)


# keep removing edges from Graph until one of the connected components of Graph splits into two
# compute the edge betweenness
def CmtyGirvanNewmanStep(G):
    if _DEBUG_:
        print "Calling CmtyGirvanNewmanStep"
    init_ncomp = nx.number_connected_components(G)  # no of components
    ncomp = init_ncomp
    while ncomp <= init_ncomp:
        bw = nx.edge_betweenness_centrality(G, weight='weight')  # edge betweenness for G
        # find the edge with max centrality
        max_ = max(bw.values())
        # find the edge with the highest centrality and remove all of them if there is more than one!
        for k, v in bw.iteritems():
            if float(v) == max_:
                G.remove_edge(k[0], k[1])  # remove the central edge
        ncomp = nx.number_connected_components(G)  # recalculate the no of components


# compute the modularity of current split
def _GirvanNewmanGetModularity(G, deg_, m_):
    New_A = nx.adj_matrix(G)
    New_deg = {}
    New_deg = UpdateDeg(New_A, G.nodes())
    # Let's compute the Q
    comps = nx.connected_components(G)  # list of components
    # print 'No of communities in decomposed G: %d' % nx.number_connected_components(G)
    Mod = 0  # Modularity of a given partitionning
    for c in comps:
        EWC = 0  # no of edges within a community
        RE = 0  # no of random edges
        for u in c:
            EWC += New_deg[u]
            RE += deg_[u]  # count the probability of a random edge
        Mod += (float(EWC) - float(RE * RE) / float(2 * m_))
    Mod = Mod / float(2 * m_)
    if _DEBUG_:
        print "Modularity: %f" % Mod
    return Mod


def UpdateDeg(A, nodes):
    deg_dict = {}
    nodes = list(nodes)
    n = len(nodes)  # len(A) ---> some ppl get issues when trying len() on sparse matrixes!
    B = A.sum(axis=1)
    for i in range(n):
        deg_dict[nodes[i]] = B[i, 0]
    return deg_dict


import copy


# run GirvanNewman algorithm and find the best community split by maximizing modularity measure
def runGirvanNewman(G, Orig_deg, m_, mini_size=None):
    # let's find the best split of the graph
    BestQ = 0.0
    Q = 0.0
    clusters = []
    while True:
        CmtyGirvanNewmanStep(G)
        Q = _GirvanNewmanGetModularity(G, Orig_deg, m_);
        # print "Modularity of decomposed G: %f" % Q
        if Q >= BestQ:
            size_fit = True
            if mini_size != None and BestQ > 0.0:
                subgraphs = list(nx.connected_component_subgraphs(copy.deepcopy(G)))
                number_clusters = len(subgraphs)
                for i in range(number_clusters):
                    if mini_size >= len(list(subgraphs[i].nodes())):
                        size_fit = False
                        break
            if size_fit == True:
                BestQ = Q
                Bestcomps = nx.connected_components(G)  # Best Split
                #	print " BestQ",  BestQ
                BestG = copy.deepcopy(G)
            else:
                break
        if G.number_of_edges() == 0:
            break
        if Q < BestQ:
            break
    if BestQ > 0.0:
        # print "Max modularity (Q): %f" % BestQ
        # print "Graph communities:", Bestcomps
        # print "Max number of components: ",nx.number_connected_components(BestG)
        subgraphs = list(nx.connected_component_subgraphs(BestG))
        number_clusters = len(subgraphs)
        for i in range(number_clusters):
            temp = list(subgraphs[i].nodes())
            temp[:] = [x for x in temp]
            clusters.append(temp)
    else:
        clusters = list(G.nodes())
        print "Max modularity (Q): %f" % BestQ
    return clusters


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("Usage: %s <input graph>\n" % (argv[0],))
        return 1
    graph_fn = argv[1]
    G = nx.Graph()  # let's create the graph first
    buildG(G, graph_fn, ',')

    if _DEBUG_:
        print 'G nodes:', G.nodes()
        print 'G no of nodes:', G.number_of_nodes()

    n = G.number_of_nodes()  # |V|
    A = nx.adj_matrix(G)  # adjacenct matrix
    m_ = 0.0  # the weighted version for number of edges
    for i in range(0, n):
        for j in range(0, n):
            m_ += A[i, j]
    m_ = m_ / 2.0
    if _DEBUG_:
        print "m: %f" % m_

    # calculate the weighted degree for each node
    Orig_deg = {}
    Orig_deg = UpdateDeg(A, G.nodes())

    # run Newman alg
    runGirvanNewman(G, Orig_deg, m_)


def run_graph(G, mini_size=None):
    if _DEBUG_:
        print 'G nodes:', G.nodes()
        print 'G no of nodes:', G.number_of_nodes()

    n = G.number_of_nodes()  # |V|
    A = nx.adj_matrix(G)  # adjacenct matrix

    m_ = 0.0  # the weighted version for number of edges
    for i in range(0, n):
        for j in range(0, n):
            m_ += A[i, j]
    m_ = m_ / 2.0
    if _DEBUG_:
        print "m: %f" % m_

    # calculate the weighted degree for each node
    Orig_deg = {}
    Orig_deg = UpdateDeg(A, G.nodes())

    # run Newman alg
    return runGirvanNewman(G, Orig_deg, m_, mini_size)


if __name__ == "__main__":
    sys.exit(main(sys.argv))