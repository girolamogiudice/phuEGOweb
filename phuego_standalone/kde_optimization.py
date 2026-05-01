#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 30 10:22:35 2025

@author: tkoutsandreas
"""
import pandas as pd
import numpy as np
import collections
import operator
from scipy.spatial import distance
from sklearn.decomposition import NMF
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')



class KDEoptimization(object):
    
    
    def __init__(self, signatures_dict, isolated_nodes_dict):
        
        self.signatures_dict = signatures_dict
        self.isolated_nodes_dict = isolated_nodes_dict
        self.pagerank_vectors = {}
        self.jsd_distances = {}
        
        
    def calculate_node_weights(self, network, signature_nodes, isolated_nodes, 
                               isolated_nodes_weight=0.1):
        
        df = pd.DataFrame(data={'weight':0}, index=network.vs['name'])
        df = df.astype(object)
        for node, weight in dict(collections.Counter(signature_nodes)).items():
            df.loc[node, 'weight'] = weight
        for node in isolated_nodes:
            #weight = float(df.loc[node, 'weight'].values[0])
            weight = float(df.loc[node, 'weight'])

            df.loc[node, 'weight'] = weight+isolated_nodes_weight
        return df.weight.tolist()
    
    
    def calculate_pagerank_vectors(self, network, isolated_nodes_weight=0.1):
        
        for kde, signature_nodes in self.signatures_dict.items():
            if type(isolated_nodes_weight) == str:
                new_weight = float(kde)*0.5
            else:
                new_weight = isolated_nodes_weight
            isolated_nodes = self.isolated_nodes_dict[kde]
            vector = self.calculate_node_weights(network, signature_nodes,
                                                 isolated_nodes,
                                                 new_weight)
            pagerank = network.personalized_pagerank(reset = vector,
                                                     directed = False,
                                                     damping = 0.85,
                                                     weights = 'weight',
                                                     implementation='prpack')
            self.pagerank_vectors.update({kde:pagerank})
    
    
    def find_start_point(self):
        
        sizes = []
        for kde, signature in self.signatures_dict.items():
            sizes.append([kde, len(signature)])
        sizes = np.array(sizes)
        sizes = sizes[sizes[:,0].argsort(),]
        sizes = sizes[sizes[:,1] > 0,:] # non-empty signatures
        start_point = sizes[-1,0]
        return start_point
    
    
    def update_start_point(self, start_point=None, stop_point=0.01):
        
        if start_point == None:
            start_point = self.find_start_point()
        else:
            pass
        try:
            distances = self.jsd_distances[str(start_point)+'_'+str(stop_point)]
        except KeyError:
            distances = self.jsd_worker(start_point, stop_point)
        matrix = distances[:,0:2].copy()
        matrix = matrix[matrix[:,1] > 1e-3,:] # remove very low distances
        X = matrix[:,0].reshape(-1,1)
        y_true = matrix[:,1].reshape(-1,1)
        # linear model to get the residuals of distances
        lm_model = LinearRegression()
        lm_model.fit(X=X, y=y_true)
        y_pred = lm_model.predict(X=matrix[:,0].reshape(-1,1))
        res = abs(y_true - y_pred)
        # Zscore transformation of residuals - cutoff at 95%
        zscore = (res - np.mean(res))/np.std(res)
        new_matrix = np.hstack([zscore > 1.96, matrix])
        new_matrix = new_matrix[new_matrix[:,0] == 0,:]
        # This is the updated start point
        new_start_point = new_matrix[-1,1]
        return new_start_point
    
    
    def jsd_worker(self, start_point=None, stop_point=0.01):
        
        if start_point == None:
            start_point = self.find_start_point()
        else:
            pass
        pagerank_start = self.pagerank_vectors[start_point]
        pagerank_stop = self.pagerank_vectors[stop_point]
        distances = []
        for kde in sorted(self.pagerank_vectors.keys()):
            if kde >= start_point or kde <= stop_point:
                continue
            else:
                pagerank = self.pagerank_vectors[kde]
                distance_from_start = distance.jensenshannon(pagerank, pagerank_start, base=2)
                distance_from_stop = distance.jensenshannon(pagerank, pagerank_stop, base=2)
                distances.append([kde, distance_from_start, distance_from_stop])
        distances = np.array(distances)
        distances = np.nan_to_num(distances, 0)
        sum_jsd = distances[:,1:3].sum(axis=1).reshape(-1,1)
        distances = np.hstack([distances, sum_jsd])
        self.jsd_distances.update({str(start_point)+'_'+str(stop_point):distances})
        return distances
    
    
    def nmf_worker(self, start_point=None, stop_point=0.01):
    
        if start_point == None:
            start_point = self.find_start_point()
        else:
            pass
        pagerank_matrix = []
        indexes = []
        for kde in sorted(self.pagerank_vectors.keys()):
            if kde > start_point or kde < stop_point:
                continue
            pagerank_matrix.append(self.pagerank_vectors[kde])
            indexes.append(kde)
        pagerank_matrix = np.array(pagerank_matrix)
        model = NMF(n_components=3, init='random', random_state=1234)
        W = model.fit_transform(pagerank_matrix)
        components = [(en,i) for en,i in enumerate(list(W.argmax(axis=0)))]
        components = sorted(components, key=operator.itemgetter(1))
        selected_component = components[1][0]
        W = pd.DataFrame(W, index=indexes)
        return W, selected_component


