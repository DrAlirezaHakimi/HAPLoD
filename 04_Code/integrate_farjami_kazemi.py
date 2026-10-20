#!/usr/bin/env python3
"""Add the Farjami-Kazemi event-resolved layer to a HAPLoD v1.0 SQLite database.

This script intentionally does not convert day-precision event snapshots into hourly tracks.
"""
import argparse,csv,sqlite3

def main():
 p=argparse.ArgumentParser(); p.add_argument('--db',required=True); p.add_argument('--events',required=True); a=p.parse_args()
 con=sqlite3.connect(a.db); cur=con.cursor()
 cur.execute("CREATE TABLE IF NOT EXISTS event_catalogue (event_id TEXT PRIMARY KEY,source TEXT NOT NULL,event_date TEXT NOT NULL,time_precision TEXT,hemisphere TEXT,lon REAL,lat REAL,vort850_cyclonic_1e5_s1 REAL,slp_hpa REAL,sst_minus_t500_k REAL,theta500_minus_theta_sst_k REAL,theta_tropopause_k REAL,equivalent_diameter_km REAL,surface_wind_ms REAL,land_distance_km REAL,source_original_id TEXT,granularity TEXT,article_doi TEXT,dataset_doi TEXT)")
 with open(a.events,encoding='utf-8-sig') as f:
  for r in csv.DictReader(f):
   vals=(r['event_id'],r['source'],r['event_date'],r['time_precision'],r['hemisphere'],float(r['longitude_deg_e']),float(r['latitude_deg_n']),float(r['vort850_cyclonic_1e5_s1']),float(r['nearest_pressure_center_slp_hpa']) if r['nearest_pressure_center_slp_hpa'] else None,float(r['sst_minus_t500_k']),float(r['theta500_minus_theta_sst_k']),float(r['theta_tropopause_k']),float(r['equivalent_pl_diameter_km']),float(r['nearest_ge15ms_wind_ms']),float(r['distance_to_border_km']),r['depression_id'],r['granularity'],r['article_doi'],r['dataset_doi'])
   cur.execute('INSERT OR REPLACE INTO event_catalogue VALUES ('+','.join(['?']*19)+')',vals)
 con.commit(); print(cur.execute("select count(*) from event_catalogue where source='Farjami_Kazemi_2024'").fetchone()[0]); con.close()
if __name__=='__main__': main()
