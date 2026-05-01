# -*- coding: utf-8 -*-

import os
import sys
import shutil
import numpy as np
import math
from sklearn.neighbors import KernelDensity
from scipy.stats import fisher_exact
from pathlib import Path

# Check if folder path end with forward slash, if not, add it.
def add_trailing_slash(folder_path):
    if not folder_path.endswith('/'):
        folder_path = folder_path + '/'
    return folder_path


def load_zscores(path):
    zscores = {}
    with open(path) as f:
        for line in f:
            uni,mean, var = line.strip().split("\t")
            zscores[uni] = np.array([mean,var], dtype=float)
    return zscores


def load_semantic_similarity(sim_folder, seeds_pos, seeds_neg,graph_nodes):
    ssim = {}
    all_seeds = (set(seeds_pos) | set(seeds_neg)) & set(graph_nodes)

    for gene in all_seeds:
        ssim[gene] = {}
        path = (
            os.path.join(sim_folder, f"{gene}.txt")
            if os.path.isfile(os.path.join(sim_folder, f"{gene}.txt"))
            else os.path.join(sim_folder, f"{gene}_all.txt")
        )
        with open(path) as f:
            next(f)
            for line in f:
                _, target, score = line.strip().split("\t")
                ssim[gene][target] = float(score)

    return ssim

def _write_seed_nodes_txt(path: Path, proteins) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    proteins = sorted(set(proteins))
    path.write_text("\n".join(proteins) + ("\n" if proteins else ""))

def write_start_seeds(res_folder, seeds_pos, seeds_neg, seeds_layers, layout):
    """
    Writes <res_folder>/start_seeds.txt
    """
    from pathlib import Path

    res_folder = Path(res_folder)
    res_folder.mkdir(parents=True, exist_ok=True)

    out = res_folder / "start_seeds.txt"

    with open(out, "w") as f:
        f.write("direction\tlayer\tprotein\n")

        npos = int(layout.layers_per_direction["pos"])

        # positive layers
        for layer_idx, layer in enumerate(seeds_layers[:npos], start=1):
            for p in layer:
                f.write(f"increased\t{layer_idx}\t{p}\n")

        # negative layers
        for layer_idx, layer in enumerate(seeds_layers[npos:], start=1):
            for p in layer:
                f.write(f"decreased\t{layer_idx}\t{p}\n")
    _write_seed_nodes_txt(res_folder / "increased" / "seed_nodes.txt", seeds_pos.keys())
    _write_seed_nodes_txt(res_folder / "decreased" / "seed_nodes.txt", seeds_neg.keys())

def translate_kde_field(field):
    
    raise_error = None
    errors = [
        "kde_cutoff must be 'optimal' and/or float numbers within [0-0.99], written as a list (comma-separated) or as a range (min-max), rounded to two decimal places.",
        "Ranges for kde_cutoff must specify two distinct values (min-max), rounded to two decimal places, within [0–0.99].",
        "kde_cutoff includes a range of values but either the limits are not floats or they fall outside [0–0.99].",
        "Float values for kde_cutoff must be within range [0–0.99]."
    ]
    output = []
    
    dash_fields = field.split('-')
    if len(dash_fields) == 1:
        # no dash
        try:
            f1 = np.float64(field).round(2)
            if f1 > 0.99 or f1 < 0:
                raise_error = 3
            output = [f1]
        except ValueError:
            if field == 'optimal':
                output = [field]
            else:
                raise_error = 0
        finally:
            pass
    else: # there is a dash which means that there is a range of float values
        try:
            f1 = np.float64(dash_fields[0]).round(2)
            f2 = np.float64(dash_fields[1]).round(2)
            if f1 >= f2 or f1+0.01>f2:
                raise_error = 1
            elif f1 > 0.99 or f1 < 0 or f2 > 0.99 or f2 < 0:
                raise_error = 1
            else:
                output = list(np.arange(f1, f2+0.01, 0.01).round(2))
        except ValueError:
            raise_error = 2
        finally:
            pass
    
    if raise_error != None:
        sys.exit(errors[raise_error])
    
    return output


def load_gene_names(uniprot_to_gene_path):
	uniprot_to_gene={}
	f1=open(uniprot_to_gene_path,"r")
	seq=f1.readline()
	while(seq!=""):
		seq=seq.strip().split("\t")
		uniprot_to_gene[seq[0]]=seq[1].split(";")[0].strip()
		seq=f1.readline()
	return uniprot_to_gene


def denoise_square(G):
	weight=G.strength(G.vs, mode='all', loops=False, weights='weight')
	for i in G.es():
		node_A=i.tuple[0]
		node_B=i.tuple[1]
		den=math.sqrt(weight[node_A]*weight[node_B])
		num=i["weight"]
		G.es[i.index]["weight"]=num/den
	return (G)


def calc_kde(vector):
	obs = len(vector)
	sigma = np.std(vector, ddof=1)
	IQR = (np.percentile(vector, q=75) - np.percentile(vector, q=25)) / 1.3489795003921634
	sigma = min(sigma, IQR)
	if sigma > 0:
		bw= sigma * (obs * 3 / 4.0) ** (-1 / 5)
	else:
		IQR = (np.percentile(vector, q=99) - np.percentile(vector, q=1)) / 4.6526957480816815
		if IQR > 0:
			bw = IQR * (obs * 3 / 4.0) ** (-1 / 5)
	if bw:
		kde = KernelDensity(kernel = 'gaussian', bandwidth=bw).fit(vector.reshape(-1,1))
		grid = np.linspace(min(vector)-1,max(vector)+1,len(vector)*100).reshape(-1,1)
		log_dens = kde.score_samples(grid)
		pdf=np.exp(log_dens)
		grid=grid.ravel()
		normalization=sum(pdf.ravel())
		cdf=np.cumsum(pdf)/normalization
	else:
		onevec=np.ones(len(vector))
		return onevec,onevec

	return cdf,grid


def fisher_test(protein_list,threshold,component,path_def,starting_proteins,
                uniprot_to_gene,geneset_path, fname):
    protein=protein_list
    temp={}
    for ii in component:
        descr={}
        temp[ii]=[]
        f1=open(geneset_path+ii+"_descr.txt","r")
        seq=f1.readline()
        while (seq!=""):
            seq=seq.strip().split("\t")
            descr[seq[0]]=seq[1]
            seq=f1.readline()
        f1.close()
        f1=open(geneset_path+ii+".txt","r")
        seq=f1.readline()
        fisher={}
        fisher_count={}
        while(seq!=""):
            seq=seq.strip().split("\t")
            fisher[seq[0]]=seq[1:]
            seq=f1.readline()
        f1.close()
        f1=open(geneset_path+ii+"_count.txt","r")
        seq=f1.readline()
        while(seq!=""):
            seq=seq.strip().split("\t")
            fisher_count[seq[0]]=int(seq[1])
            seq=f1.readline()
        f1.close()
        fisherset={}
        fisherset_count=[]
        protein_annotation={}
        for i in protein:
            if i in fisher:
                for j in fisher[i]:
                    if j in protein_annotation:
                        protein_annotation[j].append(i)
                    else:
                        protein_annotation[j]=[]
                        protein_annotation[j].append(i)

                    if j in fisherset:
                        fisherset[j]=fisherset[j]+1
                    else:
                        fisherset[j]=1

            else:
                fisherset_count.append(i)


        totalfisher=len(fisher)
        numberofproteins=len(protein)-len(list(set(fisherset_count)))
        fisher={}
        fisher_value_ic={}
        fisher_value={}
        fisher_value_no={}
        lenfisherset=len(fisherset)
        for i in fisherset:

            a=fisherset[i]
            b=numberofproteins-a
            c=fisher_count[i]-a
            d=totalfisher-a-b-c
            table=[[a,b],[c,d]]
            
            fisher[i]=fisher_exact(table,alternative ="greater")[1]
            if fisher[i]<(threshold/lenfisherset):
                if fisher[i] in fisher_value:
                    fisher_value[fisher[i]].append(i)
                else:
                    fisher_value[fisher[i]]=[]
                    fisher_value[fisher[i]].append(i)

        
        # Allow input name.
        
        f2=open(path_def+fname+ii+"fisher.txt","w")
        # Add a header to the fisher output.
        f2.write("DB id"+"\t"+"adjusted_p"+"\t"+"nodes_in_the_network"+"\t"+"N_of_seed_nodes"+"\t"+"Description"+"\t"+"gene_names"+"\n")
        
        for i in sorted(fisher_value):
            for j in fisher_value[i]:
                temp_gene=[]
                for k in list(set(protein_list).intersection(set(protein_annotation[j]))):
                    temp_gene.append(uniprot_to_gene.get(k,k))
                f2.write(j+"\t"+str(i)+"\t"+str(fisherset[j])+"\t"+str(len(list(set(starting_proteins).intersection(set(protein_annotation[j])))))+"\t"+descr[j]+"\t"+"\t".join(temp_gene)+"\n")
