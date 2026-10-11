"""H73 control decomposition: is the credit from the lane ranking or from the off-catalogue domain?"""
import sys, json, hashlib, numpy as np, rasterio
from pathlib import Path
from scipy import ndimage as ndi
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from gems61 import instruments as INST
CACHE=ROOT/'.cache'/'features73'
L=lambda n: np.load(CACHE/f'{n}.npy')
fp=L('footprint'); cat=L('catalogue'); corr=L('corr')
pool=np.load(CACHE/'pool_prod.npy') if (CACHE/'pool_prod.npy').exists() else None
import os
pool=np.load(CACHE/'pool_prod.npy')
ys=np.load(CACHE/'prod_ys.npy'); xs=np.load(CACHE/'prod_xs.npy')
with rasterio.open(ROOT/'data/external/sgmc_faults_100m.tif') as s: sgmc=(s.read(1)==1)
truth=INST.sgmc_off_catalogue(sgmc,cat,fp,buffer_px=3)
N=12000
mine=np.zeros(fp.shape,bool); mine[ys[:N],xs[:N]]=True
rng=np.random.default_rng(73073)
def sample(mask,n,seed):
    r=np.random.default_rng(seed); yy,xx=np.nonzero(mask)
    k=r.choice(yy.size,size=min(n,yy.size),replace=False); o=np.zeros(mask.shape,bool); o[yy[k],xx[k]]=True; return o
arms={'lane_ranked_12000':mine,'random_within_pool':sample(pool,N,73074),
      'random_within_footprint':sample(fp,N,73075),
      'sgmc_off_random_within_5px_corridor':sample(ndi.binary_dilation(truth,iterations=5)&fp&~ndi.binary_dilation(cat,iterations=2),N,73076)}
out={}
for k,m in arms.items():
    r=INST.global_dti(m.astype(np.float32),truth,fp,cat); r['dots']=int(m.sum()); out[k]=r
    print(k, 'credit/dot', r['credit_per_px'], 'proxyDTI', r['dti'], 'on_catalogue_dots', int((m&cat).sum()))
json.dump(dict(evidence_class='INSTRUMENT', run='h73-controls', n_truth=int(truth.sum()), mass=N,
  arms=out, champion_reference=json.load(open(ROOT/'evidence/h73b_emission.json'))['champion'],
  decomposition=dict(lane_increment=out['lane_ranked_12000']['credit_per_px']-out['random_within_pool']['credit_per_px'],
                     domain_increment=out['random_within_pool']['credit_per_px']-out['random_within_footprint']['credit_per_px']),
  meaning='lane_increment = value of the chi/k_sn amplitude-coherent ranking over chance WITHIN the same '
          'off-catalogue domain; domain_increment = value of the domain itself. Both are reported; only the '
          'sum is compared with the champion.'), open(ROOT/'evidence/h73b_controls.json','w'), indent=2)
