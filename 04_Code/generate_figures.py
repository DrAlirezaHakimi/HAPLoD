#!/usr/bin/env python3
from pathlib import Path
import sqlite3,csv,math,datetime,collections
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'03_Data_Release/database/haplod_v1.1.sqlite'
FIG=ROOT/'05_Figures'; FIG.mkdir(exist_ok=True)

con=sqlite3.connect(DB)
# track source TMI
track=con.execute('''SELECT ts.canonical_track_id,ts.hemisphere,ts.tmi_time,ts.tmi_lat,ts.tmi_lon,cm.source
FROM track_summary ts JOIN catalogue_membership cm USING(canonical_track_id)''').fetchall()
events=con.execute("SELECT event_id,event_date,lat,lon FROM event_catalogue WHERE source='Farjami_Kazemi_2024'").fetchall()
crit=con.execute('select source,subset,n_tracks,all_criteria_pass_pct from criteria_validation').fetchall()
cloud=con.execute('select distance_km,time_diff_min from impmct_cloud_era5_matches').fetchall()
rojo=con.execute('select distance_km,time_diff_min,matched from rojo_observation_matches').fetchall()
# overlap combos
combo=con.execute('''SELECT group_concat(source,' + ') combo, count(*) n FROM
(SELECT canonical_track_id,source FROM catalogue_membership ORDER BY canonical_track_id,source)
GROUP BY canonical_track_id''').fetchall()
con.close()

source_order=['Golubkin','Noer','Rojo','Smirnova','Yanase','Verezemskaya']
markers={'Golubkin':'o','Noer':'s','Rojo':'^','Smirnova':'D','Yanase':'v','Verezemskaya':'^','Farjami & Kazemi (2024)':'o'}

# Figure 1: maps + coverage
fig=plt.figure(figsize=(11.2,12.0))
gs=fig.add_gridspec(2,2,height_ratios=[1.2,0.8],hspace=0.30,wspace=0.12)
for j,hemi in enumerate(['NH','SH']):
    ax=fig.add_subplot(gs[0,j])
    if hemi=='NH':
        m=Basemap(projection='npstere',boundinglat=30,lon_0=180,resolution='l',round=True,ax=ax)
    else:
        m=Basemap(projection='spstere',boundinglat=-30,lon_0=180,resolution='l',round=True,ax=ax)
    m.drawmapboundary(linewidth=1.0)
    m.fillcontinents(color='0.90',lake_color='white',zorder=0)
    m.drawcoastlines(linewidth=0.65,color='0.2')
    m.drawparallels(([40,50,60,70,80] if hemi=='NH' else [-40,-50,-60,-70,-80]),linewidth=0.30,color='0.55')
    m.drawmeridians(np.arange(-180,181,45),linewidth=0.30,color='0.55')
    if hemi=='NH':
        for s in ['Golubkin','Noer','Rojo','Smirnova','Yanase']:
            rr=[r for r in track if r[1]=='NH' and r[5]==s]
            x,y=m([r[4] for r in rr],[r[3] for r in rr])
            m.scatter(x,y,s=20,alpha=.72,marker=markers[s],label=s,zorder=3)
        ax.set_title('(a) Northern Hemisphere track TMI locations',fontsize=11)
    else:
        rr=[r for r in track if r[1]=='SH' and r[5]=='Verezemskaya']
        x,y=m([r[4] for r in rr],[r[3] for r in rr]); m.scatter(x,y,s=18,alpha=.72,marker='^',label='Verezemskaya (2004)',zorder=3)
        x,y=m([r[3] for r in events],[r[2] for r in events]); m.scatter(x,y,s=8,alpha=.32,marker='o',label='Farjami & Kazemi (2000-2020)',zorder=2)
        ax.set_title('(b) Southern Ocean track and event locations',fontsize=11)
    # Required orientation, explicitly annotated.
    ax.text(.5,1.035,'180°',transform=ax.transAxes,ha='center',va='bottom',fontsize=9,fontweight='bold')
    ax.text(.5,-.045,'0°',transform=ax.transAxes,ha='center',va='top',fontsize=9,fontweight='bold')
    ax.text(.02,.50,'90°W',transform=ax.transAxes,ha='left',va='center',fontsize=8)
    ax.text(.98,.50,'90°E',transform=ax.transAxes,ha='right',va='center',fontsize=8)
    ax.legend(loc='lower left',fontsize=7.3,frameon=True)

ax=fig.add_subplot(gs[1,:])
coverage=[
('Yanase','1981-01-19','2010-03-06','track'),('Smirnova','1995-09-27','2009-04-19','track'),('Rojo','1999-12-19','2019-05-02','track'),('Farjami & Kazemi','2000-03-09','2020-11-17','event'),('Noer','2002-01-12','2011-03-31','track'),('Verezemskaya','2004-06-04','2004-09-30','track'),('Golubkin','2015-01-02','2017-12-19','track')]
for i,(name,a,b,kind) in enumerate(coverage):
    y=i
    da=datetime.datetime.fromisoformat(a); dbb=datetime.datetime.fromisoformat(b)
    ax.plot([da,dbb],[y,y],lw=(8 if kind=='event' else 6),solid_capstyle='butt')
    ax.text(da,y+.18,name,fontsize=8,ha='left')
ax.set_yticks([]); ax.set_xlabel('Source coverage'); ax.set_title('(c) Temporal coverage and granularity of the seven source catalogues',fontsize=11)
ax.grid(axis='x',linewidth=.3,alpha=.6)
ax.text(.01,.03,'Thicker bar = event-resolved Farjami & Kazemi layer; other bars = ERA5-matched track-resolved sources.',transform=ax.transAxes,fontsize=8)
fig.suptitle('HAPLoD v1.1 spatial and temporal source coverage',fontsize=13,y=.995)
fig.savefig(FIG/'f01_source_coverage_maps_timeline.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# Figure 2 workflow
fig,ax=plt.subplots(figsize=(10,6.3)); ax.set_axis_off()
def box(x,y,w,h,text):
    p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012,rounding_size=0.012',fill=False,linewidth=1.1); ax.add_patch(p)
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=9,wrap=True)
def arrow(x1,y1,x2,y2): ax.annotate('',xy=(x2,y2),xytext=(x1,y1),arrowprops=dict(arrowstyle='->',lw=1.0))
box(.03,.68,.23,.18,'Six ERA5-matched\ntrack catalogues\n22,317 source rows')
box(.03,.39,.23,.18,'Farjami & Kazemi\nevent catalogue\n1,073 day-precision events')
box(.03,.10,.23,.18,'Independent validation\nIMPMCT + Rojo satellite\nrecords')
box(.37,.68,.24,.18,'Track harmonization\nstandardize variables\nexact track-time reconciliation')
box(.37,.39,.24,.18,'Event normalization\npreserve day precision\nno synthetic track reconstruction')
box(.70,.56,.26,.22,'HAPLoD v1.1 release\ntrack layer + event layer\nprovenance + QC + metadata\nSQLite + CSV + code')
box(.70,.18,.26,.20,'Technical validation\ncriterion reproduction\ngeospatial checks\nsatellite-ERA5 agreement')
for a in [(.26,.77,.37,.77),(.26,.48,.37,.48),(.26,.19,.70,.28),(.61,.77,.70,.67),(.61,.48,.70,.63),(.83,.56,.83,.38)]: arrow(*a)
ax.text(.5,.965,'HAPLoD v1.1 construction and validation workflow',ha='center',va='top',fontsize=13)
ax.text(.5,.03,'Track- and event-resolved records are deliberately kept as separate analytical layers.',ha='center',fontsize=9)
fig.savefig(FIG/'f02_workflow.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# Figure 3 reconciliation and memberships
comb=collections.Counter()
for combo_str,n in combo: comb[combo_str]+=1
items=sorted(comb.items(),key=lambda x:x[1],reverse=True)
fig,axs=plt.subplots(1,2,figsize=(10.5,4.8))
axs[0].bar(['Source rows','Canonical rows'],[22317,18981]); axs[0].text(.5,20500,'3,336 exact duplicate\nsource rows reconciled',ha='center',fontsize=9)
axs[0].set_ylabel('Track time-step records'); axs[0].set_title('(a) Exact reconciliation')
labels=[k for k,v in items]; vals=[v for k,v in items]
axs[1].barh(range(len(vals)),vals); axs[1].set_yticks(range(len(vals)),labels=labels,fontsize=7); axs[1].invert_yaxis(); axs[1].set_xlabel('Canonical tracks'); axs[1].set_title('(b) Source-membership combinations')
fig.tight_layout(); fig.savefig(FIG/'f03_track_reconciliation_overlap.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# Figure 4 criteria reproduction
srcs=['Golubkin','Noer','Rojo','Smirnova','Yanase','Verezemskaya']
allp={s:np.nan for s in srcs}; labp={s:np.nan for s in srcs}
for s,subset,n,p in crit:
    if s in srcs:
        if subset=='all_candidates': allp[s]=p
        elif subset=='PL_track_positive': labp[s]=p
pub={'Golubkin':89,'Noer':82,'Rojo':86,'Smirnova':69,'Yanase':69}
x=np.arange(len(srcs)); w=.36
fig,ax=plt.subplots(figsize=(9.4,5.1)); ax.bar(x-w/2,[allp[s] for s in srcs],width=w,label='All source candidates'); ax.bar(x+w/2,[labp[s] for s in srcs],width=w,label='Source-labelled polar lows')
for i,s in enumerate(srcs):
    if s in pub: ax.scatter(i,pub[s],marker='D',s=35,label=('Published rounded retention' if i==0 else None),zorder=4)
ax.set_xticks(x,srcs,rotation=25,ha='right'); ax.set_ylabel('Tracks satisfying all four lifetime criteria (%)'); ax.set_ylim(0,105); ax.legend(fontsize=8); ax.set_title('Reproduction of the common Stoll (2022) track-level selection')
fig.tight_layout(); fig.savefig(FIG/'f04_track_criteria_validation.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# Figure 5 ECDF cloud/rojo
cd=np.array([r[0] for r in cloud if r[0] is not None],float); ct=np.array([abs(r[1]) for r in cloud if r[1] is not None],float)
rd=np.array([r[0] for r in rojo if r[2] and r[0] is not None],float); rt=np.array([abs(r[1]) for r in rojo if r[2] and r[1] is not None],float)
def ecdf(a):
 a=np.sort(a); return a,np.arange(1,len(a)+1)/len(a)
fig,axs=plt.subplots(1,2,figsize=(10,4.5))
for a,label in [(cd,'IMPMCT cloud features'),(rd,'Rojo candidate observations')]:
 xx,yy=ecdf(a); axs[0].plot(xx,yy,label=label)
axs[0].axvline(120,ls='--',lw=1); axs[0].set_xlim(0,400); axs[0].set_xlabel('Great-circle separation (km)'); axs[0].set_ylabel('Cumulative fraction'); axs[0].set_title('(a) Spatial agreement'); axs[0].legend(fontsize=8)
for a,label in [(ct,'IMPMCT cloud features'),(rt,'Rojo candidate observations')]:
 xx,yy=ecdf(a); axs[1].plot(xx,yy,label=label)
axs[1].axvline(60,ls='--',lw=1); axs[1].set_xlim(0,500); axs[1].set_xlabel('Absolute time difference (min)'); axs[1].set_ylabel('Cumulative fraction'); axs[1].set_title('(b) Temporal agreement')
fig.tight_layout(); fig.savefig(FIG/'f06_satellite_era5_validation.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# Figure 6 F-K climatology reproduction
annual=collections.Counter(datetime.date.fromisoformat(r[1]).year for r in events); monthly=collections.Counter(datetime.date.fromisoformat(r[1]).month for r in events)
fig,axs=plt.subplots(1,2,figsize=(10.5,4.3))
yrs=list(range(2000,2021)); axs[0].bar(yrs,[annual[y] for y in yrs]); axs[0].set_xlabel('Year'); axs[0].set_ylabel('Event count'); axs[0].set_title('(a) Annual event counts'); axs[0].tick_params(axis='x',rotation=60)
months=np.arange(1,13); axs[1].bar(months,[monthly[m] for m in months]); axs[1].set_xticks(months); axs[1].set_xlabel('Month'); axs[1].set_ylabel('Event count'); axs[1].set_title('(b) Monthly event counts')
fig.suptitle('Independent reproduction of Farjami & Kazemi (2024) Southern Ocean event climatology',fontsize=11.5)
fig.tight_layout(); fig.savefig(FIG/'f05_farjami_kazemi_reproduction.png',dpi=300,bbox_inches='tight'); plt.close(fig)
print('generated',len(list(FIG.glob('f*.png'))),'figures')
